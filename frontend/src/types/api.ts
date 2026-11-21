export type UserRole = "admin" | "faculty" | "student";
type MarkStatus = "draft" | "under_review" | "published";

export interface User {
  id: string;
  email: string;
  full_name: string;
  role: UserRole;
  enrollment_no: string | null;
  is_active: boolean;
  created_at: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
  user: User;
}

export interface Department {
  id: string;
  code: string;
  name: string;
  created_at: string;
}

export interface Course {
  id: string;
  department_id: string;
  code: string;
  name: string;
  duration_semesters: number;
  created_at: string;
}

export interface Semester {
  id: string;
  course_id: string;
  number: number;
  academic_year: string;
  is_active: boolean;
  created_at: string;
}

export interface Subject {
  id: string;
  semester_id: string;
  faculty_id: string | null;
  code: string;
  name: string;
  credits: string;
  max_internal: string;
  max_external: string;
  passing_marks: string;
  created_at: string;
}

interface FacultyStudentMarkRow {
  student_id: string;
  student_name: string;
  enrollment_no: string | null;
  internal_marks: string | null;
  external_marks: string | null;
  total: string | null;
  grade: string | null;
  grade_point: string | null;
  status: MarkStatus | null;
}

export interface FacultySubjectRoster {
  subject: Subject;
  semester_number: number;
  academic_year: string;
  students: FacultyStudentMarkRow[];
}

interface BulkCsvError {
  row: number;
  email: string | null;
  error: string;
}

export interface BulkCsvImportResponse {
  created_count: number;
  errors: BulkCsvError[];
}

export interface AuditLog {
  id: string;
  actor_id: string | null;
  action: string;
  entity_type: string;
  entity_id: string;
  old_value_json: Record<string, unknown> | null;
  new_value_json: Record<string, unknown> | null;
  timestamp: string;
}

interface PublishedResult {
  id: string;
  student_id: string;
  semester_id: string;
  sgpa: string;
  cgpa: string;
  result_hash_sha256: string;
  blockchain_tx_hash: string | null;
  block_number: number | null;
  published_at: string;
  published_by: string;
}

export interface SemesterPublishResponse {
  semester_id: string;
  published_count: number;
  results: PublishedResult[];
}

interface StudentSubjectResult {
  subject_code: string;
  subject_name: string;
  credits: string;
  internal_marks: string;
  external_marks: string;
  total: string;
  max_total: string;
  grade: string | null;
  grade_point: string | null;
  status: MarkStatus;
}

export interface StudentSemesterResult {
  semester_id: string;
  semester_number: number;
  academic_year: string;
  course_name: string;
  result_status: MarkStatus;
  result_id: string | null;
  sgpa: string | null;
  cgpa: string | null;
  overall_status: string | null;
  result_hash_sha256: string | null;
  blockchain_tx_hash: string | null;
  block_number: number | null;
  published_at: string | null;
  subjects: StudentSubjectResult[];
}

export interface StudentDashboardResponse {
  student_id: string;
  full_name: string;
  enrollment_no: string | null;
  latest_cgpa: string | null;
  semesters: StudentSemesterResult[];
}

export interface PublicVerificationResponse {
  result_id: string;
  verification_status: "VERIFIED ON-CHAIN" | "TAMPERED / INVALID";
  is_valid: boolean;
  student_name: string;
  enrollment_no: string | null;
  course_name: string;
  department_name: string;
  semester_number: number;
  academic_year: string;
  sgpa: string;
  cgpa: string;
  recomputed_hash_sha256: string;
  on_chain_hash_sha256: string;
  blockchain_tx_hash: string | null;
  block_number: number | null;
  on_chain_timestamp: number;
  published_at: string;
  subjects: StudentSubjectResult[];
}

export interface LiveWsEvent {
  event: "CONNECTION_ESTABLISHED" | "PONG" | "MARKS_SUBMITTED" | "STATUS_UPDATED" | "RESULT_PUBLISHED";
  [key: string]: unknown;
}
