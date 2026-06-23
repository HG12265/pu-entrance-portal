import datetime
from typing import Optional
from sqlalchemy import Column, Integer, String, Float, Text, Boolean, DateTime, Date, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from app.database import Base

class Admin(Base):
    __tablename__ = "admins"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(100), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    name = Column(String(150), nullable=False)

class Course(Base):
    __tablename__ = "courses"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(50), unique=True, index=True, nullable=False)  # e.g., MCA, MSC_CS, MSC_DS
    name = Column(String(255), nullable=False)
    seat_count = Column(Integer, default=30)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Relationships
    applications = relationship("StudentApplication", back_populates="course", cascade="all, delete-orphan")
    confirmations = relationship("AdmissionConfirmation", back_populates="course", cascade="all, delete-orphan")
    community_seats = relationship("CourseCommunitySeat", back_populates="course", cascade="all, delete-orphan")

class CourseCommunitySeat(Base):
    __tablename__ = "course_community_seats"

    id = Column(Integer, primary_key=True, index=True)
    course_id = Column(Integer, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    community_code = Column(String(50), nullable=False)  # OC, BC, BCM, MBC, SC, SCA, ST
    community_name = Column(String(100), nullable=False)
    seat_count = Column(Integer, nullable=False, default=0)
    display_order = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    # Relationships
    course = relationship("Course", back_populates="community_seats")

    # Constraints
    __table_args__ = (
        UniqueConstraint('course_id', 'community_code', name='_course_community_uc'),
    )

class Candidate(Base):
    __tablename__ = "candidates"

    id = Column(Integer, primary_key=True, index=True)
    mobile_number = Column(String(20), index=True, nullable=False)  # Normalized 10-digit primary link
    full_name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=True)
    community = Column(String(50), nullable=True)
    date_of_birth = Column(Date, nullable=True)
    raw_common_details_json = Column(Text, nullable=True)
    has_verified_details = Column(Boolean, default=False)
    verified_at = Column(DateTime, nullable=True)
    admitted_course_id = Column(Integer, ForeignKey("courses.id", ondelete="SET NULL"), nullable=True)
    admission_confirmed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    # Relationships
    applications = relationship("StudentApplication", back_populates="candidate", cascade="all, delete-orphan")
    attempts = relationship("ExamAttempt", back_populates="candidate", cascade="all, delete-orphan")
    confirmations = relationship("AdmissionConfirmation", back_populates="candidate", cascade="all, delete-orphan")
    admitted_course = relationship("Course", foreign_keys=[admitted_course_id])

class StudentApplication(Base):
    __tablename__ = "student_applications"

    id = Column(Integer, primary_key=True, index=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False)
    course_id = Column(Integer, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    application_number = Column(String(100), unique=True, index=True, nullable=False)
    mobile_number = Column(String(20), index=True, nullable=False)
    full_name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=True)
    community = Column(String(50), nullable=True)
    ug_marks = Column(Float, nullable=True)  # Student's UG score/percentage
    raw_details_json = Column(Text, nullable=True)
    import_batch_id = Column(Integer, ForeignKey("import_batches.id", ondelete="SET NULL"), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    # Constraints
    __table_args__ = (
        UniqueConstraint('candidate_id', 'course_id', name='_candidate_course_uc'),
    )

    # Relationships
    candidate = relationship("Candidate", back_populates="applications")
    course = relationship("Course", back_populates="applications")
    import_batch = relationship("ImportBatch", back_populates="applications")

    @property
    def course_code(self) -> Optional[str]:
        return self.course.code if self.course else None

    @property
    def course_name(self) -> Optional[str]:
        return self.course.name if self.course else None

    @property
    def quota(self) -> Optional[str]:
        if self.raw_details_json:
            try:
                import json
                data = json.loads(self.raw_details_json)
                return data.get("quota")
            except:
                pass
        return None

class ImportBatch(Base):
    __tablename__ = "import_batches"

    id = Column(Integer, primary_key=True, index=True)
    course_id = Column(Integer, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    filename = Column(String(255), nullable=False)
    uploaded_by_admin_id = Column(Integer, ForeignKey("admins.id", ondelete="SET NULL"), nullable=True)
    total_rows = Column(Integer, default=0)
    inserted_count = Column(Integer, default=0)
    updated_count = Column(Integer, default=0)
    skipped_count = Column(Integer, default=0)
    error_count = Column(Integer, default=0)
    errors_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Relationships
    course = relationship("Course")
    admin = relationship("Admin")
    applications = relationship("StudentApplication", back_populates="import_batch")

class AdmissionConfirmation(Base):
    __tablename__ = "admission_confirmations"

    id = Column(Integer, primary_key=True, index=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False)
    course_id = Column(Integer, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    confirmed_by_admin_id = Column(Integer, ForeignKey("admins.id", ondelete="SET NULL"), nullable=True)
    confirmed_at = Column(DateTime, default=datetime.datetime.utcnow)
    status = Column(String(50), default="confirmed")  # confirmed / cancelled
    notes = Column(Text, nullable=True)

    # Relationships
    candidate = relationship("Candidate", back_populates="confirmations")
    course = relationship("Course", back_populates="confirmations")
    admin = relationship("Admin")

class Exam(Base):
    __tablename__ = "exams"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    total_questions = Column(Integer, default=30)
    duration_minutes = Column(Integer, default=30)
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=False)
    result_visibility = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Relationships
    questions = relationship("Question", back_populates="exam", cascade="all, delete-orphan")
    attempts = relationship("ExamAttempt", back_populates="exam", cascade="all, delete-orphan")

class Question(Base):
    __tablename__ = "questions"

    id = Column(Integer, primary_key=True, index=True)
    exam_id = Column(Integer, ForeignKey("exams.id", ondelete="CASCADE"), nullable=False)
    question_text = Column(Text, nullable=False)
    option_a = Column(String(255), nullable=False)
    option_b = Column(String(255), nullable=False)
    option_c = Column(String(255), nullable=False)
    option_d = Column(String(255), nullable=False)
    correct_option = Column(String(10), nullable=False)  # A, B, C, D
    marks = Column(Float, default=1.0)
    image_url = Column(String(500), nullable=True)
    option_a_image_url = Column(String(500), nullable=True)
    option_b_image_url = Column(String(500), nullable=True)
    option_c_image_url = Column(String(500), nullable=True)
    option_d_image_url = Column(String(500), nullable=True)
    part_code = Column(String(50), nullable=True)  # A, B, C, D
    part_name = Column(String(255), nullable=True)
    part_order = Column(Integer, nullable=True)
    source_s_no = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Relationships
    exam = relationship("Exam", back_populates="questions")
    answers = relationship("StudentAnswer", back_populates="question", cascade="all, delete-orphan")

class ExamAttempt(Base):
    __tablename__ = "exam_attempts"

    id = Column(Integer, primary_key=True, index=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False)
    exam_id = Column(Integer, ForeignKey("exams.id", ondelete="CASCADE"), nullable=False)
    started_at = Column(DateTime, default=datetime.datetime.utcnow)
    submitted_at = Column(DateTime, nullable=True)
    total_questions = Column(Integer, default=0)
    correct_answers = Column(Integer, default=0)
    wrong_answers = Column(Integer, default=0)
    score = Column(Float, default=0.0)
    percentage = Column(Float, default=0.0)
    is_submitted = Column(Boolean, default=False)
    is_disqualified = Column(Boolean, default=False, server_default="0")
    question_order_json = Column(Text, nullable=True)

    # New exam resume, violation, and reopen fields
    status = Column(String(50), nullable=False, default="active")  # active, submitted, auto_submitted, admin_reopened, force_submitted
    violation_count = Column(Integer, nullable=False, default=0)
    submitted_reason = Column(String(500), nullable=True)
    submit_source = Column(String(100), nullable=True)  # manual, auto_tab_violation, time_over, admin_force
    elapsed_seconds_at_submit = Column(Integer, nullable=False, default=0)
    reopened_by_admin_id = Column(Integer, ForeignKey("admins.id", ondelete="SET NULL"), nullable=True)
    reopened_at = Column(DateTime, nullable=True)
    reopen_reason = Column(String(500), nullable=True)
    reopen_count = Column(Integer, nullable=False, default=0)
    last_activity_at = Column(DateTime, nullable=True)
    current_question_index = Column(Integer, nullable=True)
    time_extension_minutes = Column(Integer, nullable=False, default=0)

    # Constraints
    __table_args__ = (
        UniqueConstraint('candidate_id', 'exam_id', name='_candidate_exam_attempt_uc'),
    )

    # Relationships
    candidate = relationship("Candidate", back_populates="attempts")
    exam = relationship("Exam", back_populates="attempts")
    answers = relationship("StudentAnswer", back_populates="attempt", cascade="all, delete-orphan")
    reopened_by_admin = relationship("Admin", foreign_keys=[reopened_by_admin_id])

class StudentAnswer(Base):
    __tablename__ = "student_answers"

    id = Column(Integer, primary_key=True, index=True)
    attempt_id = Column(Integer, ForeignKey("exam_attempts.id", ondelete="CASCADE"), nullable=False)
    question_id = Column(Integer, ForeignKey("questions.id", ondelete="CASCADE"), nullable=False)
    selected_option = Column(String(10), nullable=True)  # A, B, C, D, or None
    is_correct = Column(Boolean, nullable=True)
    marks_obtained = Column(Float, default=0.0)
    updated_at = Column(DateTime, nullable=True, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    # Relationships
    attempt = relationship("ExamAttempt", back_populates="answers")
    question = relationship("Question", back_populates="answers")

    __table_args__ = (
        UniqueConstraint('attempt_id', 'question_id', name='_attempt_question_uc'),
    )

class ExamAttemptEventLog(Base):
    __tablename__ = "exam_attempt_event_logs"

    id = Column(Integer, primary_key=True, index=True)
    attempt_id = Column(Integer, ForeignKey("exam_attempts.id", ondelete="CASCADE"), nullable=False)
    candidate_id = Column(Integer, ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False)
    event_type = Column(String(50), nullable=False)  # answer_saved, tab_violation, auto_submitted, manual_submitted, admin_reopened, resumed, heartbeat
    event_message = Column(String(500), nullable=False)
    metadata_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Relationships
    attempt = relationship("ExamAttempt")
    candidate = relationship("Candidate")

