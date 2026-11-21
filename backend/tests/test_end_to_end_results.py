from decimal import Decimal

import pytest
from eth_tester import EthereumTester, PyEVMBackend
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from web3 import EthereumTesterProvider, Web3

from app.blockchain.compiler import ABI_OUTPUT_PATH, compile_result_registry
from app.core.security import create_access_token
from app.db.session import get_db
from app.main import create_app
from app.models.result import Mark
from app.models.user import User
from app.services.blockchain_service import BlockchainService
from app.services.result_service import get_blockchain_service
from tests.conftest import (
    TEST_ADMIN_PW,
    TEST_FACULTY_PW,
    TEST_STUDENT1_PW,
    TEST_STUDENT2_PW,
)


async def _login(client: AsyncClient, email: str, password: str) -> dict:
    resp = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()


@pytest.mark.asyncio
async def test_full_result_lifecycle_with_live_evm_pdf_and_tamper_detection(seeded_db: AsyncSession):
    # Deploy real compiled ResultRegistry.sol onto PyEVM
    compiled = compile_result_registry(export_abi=True)
    tester = EthereumTester(backend=PyEVMBackend())
    w3 = Web3(EthereumTesterProvider(tester))
    owner = w3.eth.accounts[0]
    factory = w3.eth.contract(abi=compiled["abi"], bytecode=compiled["bytecode"])
    tx_hash = factory.constructor().transact({"from": owner})
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    blockchain_service = BlockchainService(
        w3=w3,
        contract_address=receipt["contractAddress"],
        deployer_key="",
        sender_address=owner,
        abi_path=ABI_OUTPUT_PATH,
    )

    app = create_app()

    async def _override_db():
        yield seeded_db

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_blockchain_service] = lambda: blockchain_service

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        admin_auth = await _login(client, "admin@university.edu", TEST_ADMIN_PW)
        faculty_auth = await _login(client, "faculty@university.edu", TEST_FACULTY_PW)
        student1_auth = await _login(client, "student1@university.edu", TEST_STUDENT1_PW)
        student2_auth = await _login(client, "student2@university.edu", TEST_STUDENT2_PW)

        admin_hdr = {"Authorization": f"Bearer {admin_auth['access_token']}"}
        faculty_hdr = {"Authorization": f"Bearer {faculty_auth['access_token']}"}
        student1_hdr = {"Authorization": f"Bearer {student1_auth['access_token']}"}
        student2_hdr = {"Authorization": f"Bearer {student2_auth['access_token']}"}

        # 1. Admin bulk CSV import (2 valid rows + 1 invalid row)
        csv_content = (
            "email,full_name,role,password,enrollment_no\n"
            "csv.student@university.edu,Riya Joshi,student,CsvPass@2026!,ENR2026CS099\n"
            "csv.faculty@university.edu,Prof. Amit Dave,faculty,CsvPass@2026!,\n"
            "bad.student@university.edu,No Enroll,student,CsvPass@2026!,\n"
        )
        csv_resp = await client.post(
            "/api/v1/admin/users/bulk-csv",
            headers=admin_hdr,
            files={"file": ("users.csv", csv_content.encode("utf-8"), "text/csv")},
        )
        assert csv_resp.status_code == 200, csv_resp.text
        csv_data = csv_resp.json()
        assert csv_data["created_count"] == 2
        assert len(csv_data["errors"]) == 1
        assert "enrollment_no" in csv_data["errors"][0]["error"]

        # 2. Faculty lists assigned subjects (4 seeded subjects)
        roster_resp = await client.get("/api/v1/faculty/subjects", headers=faculty_hdr)
        assert roster_resp.status_code == 200, roster_resp.text
        rosters = roster_resp.json()
        assert len(rosters) == 4
        semester_id = rosters[0]["subject"]["semester_id"]

        # Map students
        s1_id = student1_auth["user"]["id"]
        s2_id = student2_auth["user"]["id"]

        # 3. Validation check: exceeding max_internal (30) is rejected with 422
        first_sub_id = rosters[0]["subject"]["id"]
        invalid_mark_resp = await client.put(
            f"/api/v1/faculty/subjects/{first_sub_id}/marks",
            headers=faculty_hdr,
            json={"entries": [{"student_id": s1_id, "internal_marks": 35, "external_marks": 60}]},
        )
        assert invalid_mark_resp.status_code == 422

        # 4. Faculty enters marks for all 4 subjects and submits each for review
        score_plan = [
            ((28, 64), (24, 56)),  # CS101: S1=92 (O, 10), S2=80 (A+, 9)
            ((26, 60), (22, 52)),  # CS102: S1=86 (A+, 9), S2=74 (A, 8)
            ((25, 55), (20, 48)),  # CS103: S1=80 (A+, 9), S2=68 (B+, 7)
            ((27, 63), (18, 42)),  # CS104: S1=90 (O, 10), S2=60 (B+, 7)
        ]
        for roster, (s1_scores, s2_scores) in zip(rosters, score_plan):
            sub_id = roster["subject"]["id"]
            put_resp = await client.put(
                f"/api/v1/faculty/subjects/{sub_id}/marks",
                headers=faculty_hdr,
                json={
                    "entries": [
                        {
                            "student_id": s1_id,
                            "internal_marks": s1_scores[0],
                            "external_marks": s1_scores[1],
                        },
                        {
                            "student_id": s2_id,
                            "internal_marks": s2_scores[0],
                            "external_marks": s2_scores[1],
                        },
                    ]
                },
            )
            assert put_resp.status_code == 200, put_resp.text

            submit_resp = await client.post(
                f"/api/v1/faculty/subjects/{sub_id}/submit",
                headers=faculty_hdr,
            )
            assert submit_resp.status_code == 200, submit_resp.text
            assert submit_resp.json()["status"] == "under_review"

        # 5. Locked after submission: faculty cannot edit submitted marks -> 409 Conflict
        locked_resp = await client.put(
            f"/api/v1/faculty/subjects/{first_sub_id}/marks",
            headers=faculty_hdr,
            json={"entries": [{"student_id": s1_id, "internal_marks": 29, "external_marks": 65}]},
        )
        assert locked_resp.status_code == 409

        # 6. Student sees "under_review" before Admin publishes (no leaked subject scores)
        pre_pub = await client.get("/api/v1/student/results", headers=student1_hdr)
        assert pre_pub.status_code == 200
        assert pre_pub.json()["semesters"][0]["result_status"] == "under_review"
        assert pre_pub.json()["semesters"][0]["subjects"] == []

        # 7. Admin One-Click Live Publish -> DB lock + On-chain hash + AuditLog
        pub_resp = await client.post(
            f"/api/v1/admin/semesters/{semester_id}/publish",
            headers=admin_hdr,
        )
        assert pub_resp.status_code == 200, pub_resp.text
        pub_data = pub_resp.json()
        assert pub_data["published_count"] == 2

        s1_published = next(r for r in pub_data["results"] if r["student_id"] == s1_id)
        assert s1_published["blockchain_tx_hash"].startswith("0x")
        assert s1_published["block_number"] >= 1
        # S1 SGPA: (4*10 + 4*9 + 3*9 + 3*10) / 14 = 133 / 14 = 9.50
        assert Decimal(s1_published["sgpa"]) == Decimal("9.50")
        assert Decimal(s1_published["cgpa"]) == Decimal("9.50")

        # 8. Student dashboard now shows full published results
        post_pub = await client.get("/api/v1/student/results", headers=student1_hdr)
        assert post_pub.status_code == 200
        s1_dash = post_pub.json()
        assert Decimal(s1_dash["latest_cgpa"]) == Decimal("9.50")
        assert s1_dash["semesters"][0]["result_status"] == "published"
        assert len(s1_dash["semesters"][0]["subjects"]) == 4

        result_id = s1_published["id"]

        # 9. Official QR-embedded PDF marksheet download works for owner and blocks other students
        pdf_resp = await client.get(
            f"/api/v1/student/results/{result_id}/pdf",
            headers=student1_hdr,
        )
        assert pdf_resp.status_code == 200
        assert pdf_resp.headers["content-type"] == "application/pdf"
        assert pdf_resp.content.startswith(b"%PDF-")
        assert len(pdf_resp.content) > 2500

        other_pdf_resp = await client.get(
            f"/api/v1/student/results/{result_id}/pdf",
            headers=student2_hdr,
        )
        assert other_pdf_resp.status_code == 403

        # 10. Public Verifier (NO Auth Header!) -> VERIFIED ON-CHAIN
        verify_resp = await client.get(f"/api/v1/verify/{result_id}")
        assert verify_resp.status_code == 200, verify_resp.text
        v_data = verify_resp.json()
        assert v_data["verification_status"] == "VERIFIED ON-CHAIN"
        assert v_data["is_valid"] is True
        assert v_data["recomputed_hash_sha256"] == v_data["on_chain_hash_sha256"]
        assert v_data["block_number"] >= 1
        assert v_data["on_chain_timestamp"] > 0

        # 11. Tamper Detection: directly alter a mark in SQL and re-verify publicly
        mark_row = (
            await seeded_db.execute(
                select(Mark).where(Mark.student_id == User.id, User.email == "student1@university.edu")
            )
        ).scalars().first()
        mark_row.internal_marks = Decimal("30.00")
        mark_row.total = Decimal(str(mark_row.internal_marks)) + Decimal(str(mark_row.external_marks))
        await seeded_db.commit()

        tampered_resp = await client.get(f"/api/v1/verify/{result_id}")
        assert tampered_resp.status_code == 200
        t_data = tampered_resp.json()
        assert t_data["verification_status"] == "TAMPERED / INVALID"
        assert t_data["is_valid"] is False
        assert t_data["recomputed_hash_sha256"] != t_data["on_chain_hash_sha256"]

        # 12. Admin Audit Logs recorded marks, submissions, CSV imports, and publishing
        audit_resp = await client.get("/api/v1/admin/audit-logs?limit=50", headers=admin_hdr)
        assert audit_resp.status_code == 200
        actions = {log["action"] for log in audit_resp.json()}
        assert "MARK_CREATED" in actions
        assert "MARKS_SUBMITTED" in actions
        assert "RESULT_PUBLISHED" in actions
        assert "USER_BULK_IMPORTED" in actions

    app.dependency_overrides.clear()


def test_websocket_connection_and_heartbeat():
    app = create_app()
    sync_client = TestClient(app)

    # Invalid JWT closes with policy violation
    with pytest.raises(Exception):
        with sync_client.websocket_connect("/ws/results?token=invalid-jwt"):
            pass

    # Valid JWT establishes live session and responds to ping
    import uuid

    uid = uuid.uuid4()
    token, _ = create_access_token(uid, "student")
    with sync_client.websocket_connect(f"/ws/results?token={token}") as ws:
        hello = ws.receive_json()
        assert hello["event"] == "CONNECTION_ESTABLISHED"
        assert hello["user_id"] == str(uid)
        assert hello["role"] == "student"

        ws.send_text("ping")
        pong = ws.receive_json()
        assert pong == {"event": "PONG"}


@pytest.mark.asyncio
async def test_ws_manager_delivers_live_result_published_event():
    """Verifies ConnectionManager pushes RESULT_PUBLISHED events directly to subscribed students."""
    from app.services.ws_manager import ConnectionManager

    received: list[dict] = []

    class _LoopbackSocket:
        async def accept(self):
            return None

        async def send_json(self, data: dict):
            received.append(data)

    mgr = ConnectionManager()
    sock = _LoopbackSocket()
    await mgr.connect(sock, user_id="student-live-1", role="student")
    assert mgr.active_count() == 1

    await mgr.send_to_user(
        "student-live-1",
        {
            "event": "RESULT_PUBLISHED",
            "result_id": "res-live-001",
            "sgpa": "9.50",
            "cgpa": "9.50",
        },
    )
    assert len(received) == 1
    assert received[0]["event"] == "RESULT_PUBLISHED"
    assert received[0]["sgpa"] == "9.50"

    mgr.disconnect(sock, user_id="student-live-1", role="student")
    assert mgr.active_count() == 0

