import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.result import MarkStatus


# --- Academic Structure ---
class DepartmentCreate(BaseModel):
    code: str = Field(min_length=2, max_length=32)
    name: str = Field(min_length=2, max_length=255)


class DepartmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    code: str
    name: str
    created_at: datetime


class CourseCreate(BaseModel):
    department_id: uuid.UUID
    code: str = Field(min_length=2, max_length=32)
    name: str = Field(min_length=2, max_length=255)
    duration_semesters: int = Field(default=8, ge=1, le=12)


class CourseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    department_id: uuid.UUID
    code: str
    name: str
    duration_semesters: int
    created_at: datetime


class SemesterCreate(BaseModel):
    course_id: uuid.UUID
    number: int = Field(ge=1, le=12)
    academic_year: str = Field(min_length=4, max_length=32)
    is_active: bool = True


class SemesterResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    course_id: uuid.UUID
    number: int
    academic_year: str
    is_active: bool
    created_at: datetime


class SubjectCreate(BaseModel):
    semester_id: uuid.UUID
    faculty_id: Optional[uuid.UUID] = None
    code: str = Field(min_length=2, max_length=32)
    name: str = Field(min_length=2, max_length=255)
    credits: Decimal = Field(gt=0, le=20)
    max_internal: Decimal = Field(default=Decimal("30.00"), ge=0, le=500)
    max_external: Decimal = Field(default=Decimal("70.00"), ge=0, le=500)
    passing_marks: Decimal = Field(default=Decimal("40.00"), ge=0, le=500)


class SubjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    semester_id: uuid.UUID
    faculty_id: Optional[uuid.UUID]
    code: str
    name: str
    credits: Decimal
    max_internal: Decimal
    max_external: Decimal
    passing_marks: Decimal
    created_at: datetime


class EnrollmentCreate(BaseModel):
    student_id: uuid.UUID
    semester_id: uuid.UUID
    course_id: uuid.UUID


class EnrollmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    student_id: uuid.UUID
    semester_id: uuid.UUID
    course_id: uuid.UUID
    enrolled_at: datetime


# --- Faculty Marks Entry ---
class MarkEntryItem(BaseModel):
    student_id: uuid.UUID
    internal_marks: Decimal = Field(ge=0)
    external_marks: Decimal = Field(ge=0)


class BatchMarksUpsertRequest(BaseModel):
    entries: list[MarkEntryItem] = Field(min_length=1)


class MarkResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    student_id: uuid.UUID
    subject_id: uuid.UUID
    semester_id: uuid.UUID
    internal_marks: Decimal
    external_marks: Decimal
    total: Decimal
    grade: Optional[str]
    grade_point: Optional[Decimal]
    status: MarkStatus
    entered_by: uuid.UUID
    updated_at: datetime


class FacultyStudentMarkRow(BaseModel):
    student_id: uuid.UUID
    student_name: str
    enrollment_no: Optional[str]
    internal_marks: Optional[Decimal] = None
    external_marks: Optional[Decimal] = None
    total: Optional[Decimal] = None
    grade: Optional[str] = None
    grade_point: Optional[Decimal] = None
    status: Optional[MarkStatus] = None


class FacultySubjectRosterResponse(BaseModel):
    subject: SubjectResponse
    semester_number: int
    academic_year: str
    students: list[FacultyStudentMarkRow]


class SubmitSubjectMarksResponse(BaseModel):
    subject_id: uuid.UUID
    submitted_count: int
    status: MarkStatus


# --- Admin Bulk CSV & Audit & Publish ---
class BulkCsvError(BaseModel):
    row: int
    email: Optional[str] = None
    error: str


class BulkCsvImportResponse(BaseModel):
    created_count: int
    errors: list[BulkCsvError]


class AuditLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    actor_id: Optional[uuid.UUID]
    action: str
    entity_type: str
    entity_id: str
    old_value_json: Optional[dict[str, Any]]
    new_value_json: Optional[dict[str, Any]]
    timestamp: datetime


class PublishedResultResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    student_id: uuid.UUID
    semester_id: uuid.UUID
    sgpa: Decimal
    cgpa: Decimal
    result_hash_sha256: str
    blockchain_tx_hash: Optional[str]
    block_number: Optional[int]
    published_at: datetime
    published_by: uuid.UUID


class SemesterPublishResponse(BaseModel):
    semester_id: uuid.UUID
    published_count: int
    results: list[PublishedResultResponse]


# --- Student Dashboard ---
class StudentSubjectResult(BaseModel):
    subject_code: str
    subject_name: str
    credits: Decimal
    internal_marks: Decimal
    external_marks: Decimal
    total: Decimal
    max_total: Decimal
    grade: Optional[str]
    grade_point: Optional[Decimal]
    status: MarkStatus


class StudentSemesterResult(BaseModel):
    semester_id: uuid.UUID
    semester_number: int
    academic_year: str
    course_name: str
    result_status: str  # "draft" | "under_review" | "published"
    result_id: Optional[uuid.UUID] = None
    sgpa: Optional[Decimal] = None
    cgpa: Optional[Decimal] = None
    overall_status: Optional[str] = None
    result_hash_sha256: Optional[str] = None
    blockchain_tx_hash: Optional[str] = None
    block_number: Optional[int] = None
    published_at: Optional[datetime] = None
    subjects: list[StudentSubjectResult] = []


class StudentDashboardResponse(BaseModel):
    student_id: uuid.UUID
    full_name: str
    enrollment_no: Optional[str]
    latest_cgpa: Optional[Decimal]
    semesters: list[StudentSemesterResult]


# --- Public Verifier ---
class PublicVerificationResponse(BaseModel):
    result_id: uuid.UUID
    verification_status: str  # "VERIFIED ON-CHAIN" or "TAMPERED / INVALID"
    is_valid: bool
    student_name: str
    enrollment_no: Optional[str]
    course_name: str
    department_name: str
    semester_number: int
    academic_year: str
    sgpa: Decimal
    cgpa: Decimal
    recomputed_hash_sha256: str
    on_chain_hash_sha256: str
    blockchain_tx_hash: Optional[str]
    block_number: Optional[int]
    on_chain_timestamp: int
    published_at: datetime
    subjects: list[StudentSubjectResult]
