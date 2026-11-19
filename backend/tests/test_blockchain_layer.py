import pytest
from eth_tester import EthereumTester, PyEVMBackend
from web3 import EthereumTesterProvider, Web3

from app.blockchain.compiler import ABI_OUTPUT_PATH, compile_result_registry
from app.services.blockchain_service import (
    BlockchainService,
    compute_result_hash,
    hex_hash_to_bytes32,
)


@pytest.fixture(scope="module")
def compiled_registry():
    return compile_result_registry(export_abi=True)


@pytest.fixture
def live_evm_registry(compiled_registry):
    """Deploys the real compiled ResultRegistry.sol onto an in-process PyEVM chain."""
    tester = EthereumTester(backend=PyEVMBackend())
    w3 = Web3(EthereumTesterProvider(tester))
    owner = w3.eth.accounts[0]
    non_owner = w3.eth.accounts[1]
    new_owner = w3.eth.accounts[2]

    contract_factory = w3.eth.contract(
        abi=compiled_registry["abi"],
        bytecode=compiled_registry["bytecode"],
    )
    tx_hash = contract_factory.constructor().transact({"from": owner})
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    contract_address = receipt["contractAddress"]

    service = BlockchainService(
        w3=w3,
        contract_address=contract_address,
        deployer_key="",
        sender_address=owner,
        abi_path=ABI_OUTPUT_PATH,
    )
    return {
        "w3": w3,
        "service": service,
        "owner": owner,
        "non_owner": non_owner,
        "new_owner": new_owner,
        "contract_address": contract_address,
    }


def test_canonical_sha256_hash_is_deterministic_and_tamper_sensitive():
    payload_a = {
        "student_enrollment_no": "ENR2026CS001",
        "semester": 1,
        "sgpa": "9.14",
        "subjects": [
            {"code": "CS101", "total": 91, "grade": "O"},
            {"code": "CS102", "total": 85, "grade": "A+"},
        ],
    }
    payload_b = {
        "subjects": [
            {"grade": "O", "code": "CS101", "total": 91},
            {"total": 85, "grade": "A+", "code": "CS102"},
        ],
        "sgpa": "9.14",
        "semester": 1,
        "student_enrollment_no": "ENR2026CS001",
    }
    tampered = {**payload_a, "sgpa": "9.15"}

    hash_a = compute_result_hash(payload_a)
    hash_b = compute_result_hash(payload_b)
    hash_tampered = compute_result_hash(tampered)

    assert len(hash_a) == 64
    assert hash_a == hash_b
    assert hash_a != hash_tampered
    assert len(hex_hash_to_bytes32(hash_a)) == 32


def test_contract_deploy_store_and_verify_on_evm(live_evm_registry):
    service: BlockchainService = live_evm_registry["service"]
    owner = live_evm_registry["owner"]
    assert service.is_connected() is True
    assert ABI_OUTPUT_PATH.exists()

    result_id = "res-2026-sem1-enr2026cs001"
    authentic_payload = {
        "result_id": result_id,
        "enrollment_no": "ENR2026CS001",
        "sgpa": "9.25",
        "cgpa": "9.25",
    }
    authentic_hash = compute_result_hash(authentic_payload)

    receipt = service.store_result_hash(result_id, authentic_hash)
    assert receipt.tx_hash.startswith("0x")
    assert receipt.block_number >= 1
    assert receipt.timestamp > 0
    assert receipt.result_hash_sha256 == authentic_hash

    # Verify authentic payload -> valid
    verified = service.verify_result_hash(result_id, authentic_hash)
    assert verified.is_valid is True
    assert verified.exists is True
    assert verified.stored_hash_sha256 == authentic_hash
    assert verified.block_number == receipt.block_number
    assert verified.published_by == Web3.to_checksum_address(owner)

    # Verify tampered payload -> invalid
    tampered_hash = compute_result_hash({**authentic_payload, "sgpa": "9.99"})
    tampered_check = service.verify_result_hash(result_id, tampered_hash)
    assert tampered_check.is_valid is False
    assert tampered_check.exists is True
    assert tampered_check.stored_hash_sha256 == authentic_hash

    # Verify non-existent result_id -> invalid and exists=False
    missing_check = service.verify_result_hash("non-existent-id", authentic_hash)
    assert missing_check.is_valid is False
    assert missing_check.exists is False


def test_contract_enforces_only_owner_write_and_immutability(live_evm_registry):
    w3 = live_evm_registry["w3"]
    service: BlockchainService = live_evm_registry["service"]
    non_owner = live_evm_registry["non_owner"]
    contract_address = live_evm_registry["contract_address"]

    result_hash = compute_result_hash({"student": "ENR2026CS002", "sgpa": "8.75"})

    # Non-owner cannot write to ResultRegistry
    non_owner_service = BlockchainService(
        w3=w3,
        contract_address=contract_address,
        deployer_key="",
        sender_address=non_owner,
        abi_path=ABI_OUTPUT_PATH,
    )
    with pytest.raises(Exception):
        non_owner_service.store_result_hash("res-unauth", result_hash)

    # Owner writes once -> succeeds
    service.store_result_hash("res-immutable", result_hash)

    # Second write to same result_id -> reverts (immutable)
    with pytest.raises(Exception):
        service.store_result_hash("res-immutable", result_hash)

    # Zero hash -> reverts
    with pytest.raises(Exception):
        service.store_result_hash("res-zero", "0" * 64)


def test_contract_ownership_transfer(live_evm_registry):
    w3 = live_evm_registry["w3"]
    service: BlockchainService = live_evm_registry["service"]
    owner = live_evm_registry["owner"]
    new_owner = live_evm_registry["new_owner"]
    contract_address = live_evm_registry["contract_address"]

    tx_hash = service.contract.functions.transferOwnership(new_owner).transact({"from": owner})
    w3.eth.wait_for_transaction_receipt(tx_hash)

    assert service.contract.functions.owner().call() == Web3.to_checksum_address(new_owner)

    # Old owner can no longer store hashes
    sample_hash = compute_result_hash({"test": "ownership-transfer"})
    with pytest.raises(Exception):
        service.store_result_hash("res-old-owner", sample_hash)

    # New owner can store hashes
    new_owner_service = BlockchainService(
        w3=w3,
        contract_address=contract_address,
        deployer_key="",
        sender_address=new_owner,
        abi_path=ABI_OUTPUT_PATH,
    )
    receipt = new_owner_service.store_result_hash("res-new-owner", sample_hash)
    assert receipt.block_number >= 1
    assert new_owner_service.verify_result_hash("res-new-owner", sample_hash).is_valid is True
