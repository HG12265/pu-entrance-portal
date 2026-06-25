from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Dict, Any, Literal
from datetime import datetime, date

# Token Schemas
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None
    role: Optional[str] = None
    token_type: Optional[str] = None

# Admin Schemas
class AdminBase(BaseModel):
    username: str
    name: str

class AdminCreate(AdminBase):
    password: str

class AdminResponse(AdminBase):
    id: int
    class Config:
        from_attributes = True

# Candidate and Student Application Schemas
class StudentApplicationBase(BaseModel):
    id: int
    candidate_id: int
    course_id: int
    application_number: str
    mobile_number: str
    full_name: str
    email: Optional[str] = None
    community: Optional[str] = None
    ug_marks: Optional[float] = None
    raw_details_json: Optional[str] = None
    course_code: Optional[str] = None
    course_name: Optional[str] = None
    quota: Optional[str] = None
    is_active: bool
    created_at: datetime
    class Config:
        from_attributes = True

class CandidateBase(BaseModel):
    id: int
    mobile_number: str
    full_name: str
    email: Optional[str] = None
    community: Optional[str] = None
    date_of_birth: Optional[date] = None
    has_verified_details: bool
    verified_at: Optional[datetime] = None
    admitted_course_id: Optional[int] = None
    admission_confirmed_at: Optional[datetime] = None
    applications: List[StudentApplicationBase] = []
    class Config:
        from_attributes = True

# Student Login and Session payloads
class StudentLoginRequest(BaseModel):
    application_number: str
    mobile_number: str

class StudentLoginResponse(BaseModel):
    access_token: str
    token_type: str
    candidate: CandidateBase
    applications: List[StudentApplicationBase]
    attempt_status: str  # "new", "resume", "submitted"
    attempt_id: Optional[int] = None

class StudentVerificationRequest(BaseModel):
    confirm_details: bool

# Course Schemas
class CourseBase(BaseModel):
    id: int
    code: str
    name: str
    seat_count: int
    is_active: bool
    created_at: datetime
    class Config:
        from_attributes = True

class CourseCreate(BaseModel):
    code: str
    name: str
    seat_count: int = 30
    is_active: bool = True

class CourseUpdate(BaseModel):
    seat_count: int
    is_active: Optional[bool] = True

class CourseCommunitySeatBase(BaseModel):
    id: int
    course_id: int
    community_code: str
    community_name: str
    seat_count: int
    display_order: int
    class Config:
        from_attributes = True

class CourseCommunitySeatUpdate(BaseModel):
    community_code: str
    seat_count: int

# Exam Schemas
class ExamBase(BaseModel):
    name: str
    total_questions: int = Field(30, ge=1)
    duration_minutes: int = Field(30, ge=1)
    start_date: datetime
    end_date: datetime
    result_visibility: bool = True

class ExamCreate(ExamBase):
    pass

class ExamResponse(ExamBase):
    id: int
    created_at: datetime
    class Config:
        from_attributes = True

# Question Schemas
class QuestionBase(BaseModel):
    question_text: str
    option_a: str
    option_b: str
    option_c: str
    option_d: str
    correct_option: str = Field(..., pattern="^[A-Da-d]$")
    marks: float = 1.0
    image_url: Optional[str] = None
    option_a_image_url: Optional[str] = None
    option_b_image_url: Optional[str] = None
    option_c_image_url: Optional[str] = None
    option_d_image_url: Optional[str] = None
    part_code: Optional[str] = None
    part_name: Optional[str] = None
    part_order: Optional[int] = None
    source_s_no: Optional[int] = None

class QuestionCreate(QuestionBase):
    pass

class QuestionResponse(QuestionBase):
    id: int
    exam_id: int
    created_at: datetime
    class Config:
        from_attributes = True

class QuestionResponseForStudent(BaseModel):
    id: int
    exam_id: int
    question_text: str
    option_a: str
    option_b: str
    option_c: str
    option_d: str
    marks: float
    image_url: Optional[str] = None
    option_a_image_url: Optional[str] = None
    option_b_image_url: Optional[str] = None
    option_c_image_url: Optional[str] = None
    option_d_image_url: Optional[str] = None
    part_code: Optional[str] = None
    part_name: Optional[str] = None
    part_order: Optional[int] = None
    source_s_no: Optional[int] = None
    class Config:
        from_attributes = True

# Student Answer Schemas
class StudentAnswerSave(BaseModel):
    question_id: int
    selected_option: Optional[Literal["A", "B", "C", "D", "a", "b", "c", "d", ""]] = None

class StudentAnswerResponse(BaseModel):
    id: int
    attempt_id: int
    question_id: int
    selected_option: Optional[str]
    is_correct: Optional[bool]
    marks_obtained: float
    class Config:
        from_attributes = True

# Detailed score representation for students upon submission
class ExamSubmitResultResponse(BaseModel):
    attempt_id: int
    mobile_number: str
    student_name: str
    degrees: List[str]
    total_questions: int
    attempted_questions: int
    correct_answers: int
    wrong_answers: int
    score: float
    percentage: float
    ug_percentage: float
    entrance_percentage: float
    final_percentage: float
    result_visibility: bool

# Leaderboard / Course Ranking Schemas for Admin Dashboard
class CourseRankingEntry(BaseModel):
    rank: int              # Active rank (rank after exclusions)
    original_rank: int     # Original rank (rank before exclusions)
    active_rank: int       # Active rank or -1 if excluded
    id: int                # Attempt ID
    candidate_id: int
    application_number: str
    student_name: str
    degrees: List[str]
    community: str
    ug_percentage: Optional[float] = None
    score: float           # Exam marks
    percentage: float      # Exam percentage
    correct_answers: int
    wrong_answers: int
    total_questions: int
    submitted_at: Optional[datetime] = None
    is_eligible: bool      # active_rank <= seat_count
    confirmation_status: str  # "Eligible", "Waitlisted", "Confirmed"
    excluded_reason: Optional[str] = None # e.g. "Admitted to MCA"
    raw_community: str
    normalized_community: str
    open_competition_rank: int
    community_rank: int
    community_seat_count: int
    final_selection_bucket_code: str
    final_selection_bucket_name: str
    community_eligibility_status: str
    entrance_score: float
    entrance_total_marks: float
    entrance_percentage: float
    entrance_weighted_score: float
    ug_weighted_score: Optional[float] = None
    final_score: Optional[float] = None
    final_score_breakdown_text: Optional[str] = None

# Counseling Confirm Request
class CounsellingConfirmRequest(BaseModel):
    candidate_id: int
    course_id: int
