import io
from dataclasses import dataclass
from typing import Sequence

import qrcode
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas


@dataclass(frozen=True)
class MarksheetSubjectLine:
    code: str
    name: str
    credits: str
    internal_marks: str
    external_marks: str
    total: str
    max_total: str
    grade: str
    grade_point: str
    status: str


@dataclass(frozen=True)
class MarksheetData:
    result_id: str
    student_name: str
    enrollment_no: str
    department_name: str
    course_name: str
    semester_number: int
    academic_year: str
    sgpa: str
    cgpa: str
    overall_status: str
    result_hash_sha256: str
    blockchain_tx_hash: str
    block_number: int | None
    published_at_iso: str
    verify_url: str
    subjects: Sequence[MarksheetSubjectLine]


def generate_marksheet_pdf(data: MarksheetData) -> bytes:
    """Generates an official A4 PDF marksheet with an embedded blockchain-verification QR code."""
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    pdf.setTitle(f"Official Marksheet - {data.enrollment_no} - Sem {data.semester_number}")

    # Header band
    pdf.setFillColor(colors.HexColor("#0F172A"))
    pdf.rect(0, height - 34 * mm, width, 34 * mm, fill=1, stroke=0)

    pdf.setFillColor(colors.white)
    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(18 * mm, height - 15 * mm, "OFFICIAL ACADEMIC TRANSCRIPT / MARKSHEET")
    pdf.setFont("Helvetica", 10)
    pdf.drawString(
        18 * mm,
        height - 23 * mm,
        f"{data.department_name}  |  {data.course_name}  |  Academic Year {data.academic_year}",
    )
    pdf.setFont("Helvetica-Oblique", 8.5)
    pdf.drawString(
        18 * mm,
        height - 29 * mm,
        "Cryptographically anchored on-chain for tamper-evident public verification",
    )

    # Student metadata box
    y = height - 46 * mm
    pdf.setFillColor(colors.HexColor("#0F172A"))
    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(18 * mm, y, f"Student Name: {data.student_name}")
    pdf.drawString(115 * mm, y, f"Enrollment No: {data.enrollment_no}")
    y -= 6 * mm
    pdf.setFont("Helvetica", 9.5)
    pdf.drawString(18 * mm, y, f"Semester: {data.semester_number}")
    pdf.drawString(115 * mm, y, f"Result ID: {data.result_id}")
    y -= 6 * mm
    pdf.drawString(18 * mm, y, f"Published At (IST): {data.published_at_iso}")
    pdf.drawString(115 * mm, y, f"Overall Status: {data.overall_status}")

    # Subject marks table header
    y -= 12 * mm
    pdf.setFillColor(colors.HexColor("#E2E8F0"))
    pdf.rect(16 * mm, y - 2 * mm, width - 32 * mm, 8 * mm, fill=1, stroke=0)
    pdf.setFillColor(colors.HexColor("#0F172A"))
    pdf.setFont("Helvetica-Bold", 8.5)

    cols = [18, 36, 98, 113, 128, 144, 162, 176]
    headers = ["Code", "Subject", "Cr", "Int", "Ext", "Total", "Grade", "GP"]
    for x_mm, label in zip(cols, headers):
        pdf.drawString(x_mm * mm, y + 0.8 * mm, label)

    y -= 8 * mm
    pdf.setFont("Helvetica", 8.5)
    for row in data.subjects:
        if y < 65 * mm:
            pdf.showPage()
            y = height - 25 * mm
            pdf.setFont("Helvetica", 8.5)

        pdf.drawString(cols[0] * mm, y, row.code)
        pdf.drawString(cols[1] * mm, y, row.name[:34])
        pdf.drawString(cols[2] * mm, y, row.credits)
        pdf.drawString(cols[3] * mm, y, row.internal_marks)
        pdf.drawString(cols[4] * mm, y, row.external_marks)
        pdf.drawString(cols[5] * mm, y, f"{row.total}/{row.max_total}")
        pdf.drawString(cols[6] * mm, y, row.grade)
        pdf.drawString(cols[7] * mm, y, row.grade_point)

        pdf.setStrokeColor(colors.HexColor("#CBD5E1"))
        pdf.line(16 * mm, y - 2.2 * mm, width - 16 * mm, y - 2.2 * mm)
        y -= 7 * mm

    # Summary strip
    y -= 5 * mm
    pdf.setFillColor(colors.HexColor("#F8FAFC"))
    pdf.rect(16 * mm, y - 6 * mm, width - 32 * mm, 12 * mm, fill=1, stroke=1)
    pdf.setFillColor(colors.HexColor("#0F172A"))
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(22 * mm, y - 1.5 * mm, f"Semester SGPA: {data.sgpa}")
    pdf.drawString(82 * mm, y - 1.5 * mm, f"Cumulative CGPA: {data.cgpa}")
    pdf.drawString(148 * mm, y - 1.5 * mm, f"Result: {data.overall_status}")

    # Blockchain Verification Box + QR Code
    box_top = 56 * mm
    pdf.setStrokeColor(colors.HexColor("#334155"))
    pdf.rect(16 * mm, 16 * mm, width - 32 * mm, box_top - 16 * mm, fill=0, stroke=1)

    qr = qrcode.QRCode(version=2, box_size=6, border=2)
    qr.add_data(data.verify_url)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    qr_buf = io.BytesIO()
    qr_img.save(qr_buf, format="PNG")
    qr_buf.seek(0)

    pdf.drawImage(ImageReader(qr_buf), width - 52 * mm, 20 * mm, width=32 * mm, height=32 * mm)

    pdf.setFont("Helvetica-Bold", 9.5)
    pdf.drawString(20 * mm, 49 * mm, "BLOCKCHAIN VERIFICATION PROOF")
    pdf.setFont("Helvetica", 8)
    pdf.drawString(20 * mm, 42 * mm, f"SHA-256 Digest: {data.result_hash_sha256}")
    pdf.drawString(20 * mm, 36 * mm, f"On-Chain Tx Hash: {data.blockchain_tx_hash}")
    pdf.drawString(
        20 * mm,
        30 * mm,
        f"Block Number: {data.block_number if data.block_number is not None else 'Pending'}",
    )
    pdf.drawString(20 * mm, 23 * mm, f"Scan QR or verify online: {data.verify_url}")

    pdf.showPage()
    pdf.save()
    buffer.seek(0)
    return buffer.getvalue()
