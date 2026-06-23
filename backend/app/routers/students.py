import re
import datetime
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional
from app.database import get_db
from app.models import Candidate, StudentApplication, ExamAttempt, Admin, Course
from app.schemas import StudentLoginRequest, StudentLoginResponse, StudentVerificationRequest, CandidateBase, StudentApplicationBase
from app.auth import get_current_admin, get_current_candidate, create_access_token
from app.limiter import limiter
from app.config import settings
from app.utils.mobile import normalize_mobile

router = APIRouter(prefix="/api/v1/students", tags=["Students"])

@router.post("/login", response_model=StudentLoginResponse)
@limiter.limit("10/minute")
def student_login(request: Request, payload: StudentLoginRequest, db: Session = Depends(get_db)):
    generic_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid application number or mobile number."
    )

    # 1. Query application
    app_record = db.query(StudentApplication).filter(
        StudentApplication.application_number == payload.application_number.strip()
    ).first()

    if not app_record:
        raise generic_error

    # 2. Check mobile matches normalized form
    input_mobile_norm = normalize_mobile(payload.mobile_number)
    db_mobile_norm = normalize_mobile(app_record.mobile_number)

    if input_mobile_norm != db_mobile_norm:
        raise generic_error

    # 3. Load Candidate
    candidate = db.query(Candidate).options(joinedload(Candidate.applications)).filter(Candidate.id == app_record.candidate_id).first()
    if not candidate:
        raise generic_error

    # 4. Determine attempt status
    # Standard query for primary exam
    attempt = db.query(ExamAttempt).filter(
        ExamAttempt.candidate_id == candidate.id
    ).first()

    attempt_status = "new"
    attempt_id = None

    if attempt:
        attempt_id = attempt.id
        if attempt.is_submitted:
            attempt_status = "submitted"
        else:
            attempt_status = "resume"

    # 5. Generate secure JWT student access token
    token_data = {
        "candidate_id": candidate.id,
        "role": "student",
        "token_type": "student_exam"
    }
    access_token = create_access_token(
        data=token_data,
        expires_delta=timedelta(minutes=settings.STUDENT_TOKEN_EXPIRE_MINUTES)
    )

    # 6. Load all applications for the candidate
    apps_list = db.query(StudentApplication).options(joinedload(StudentApplication.course)).filter(
        StudentApplication.candidate_id == candidate.id
    ).all()

    # Format Candidate and Application dict structures to match schemas
    candidate_data = CandidateBase.model_validate(candidate)
    apps_data = [StudentApplicationBase.model_validate(ap) for ap in apps_list]

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "candidate": candidate_data,
        "applications": apps_data,
        "attempt_status": attempt_status,
        "attempt_id": attempt_id
    }

@router.post("/verify-details")
@limiter.limit("10/minute")
def verify_details(
    request: Request,
    payload: StudentVerificationRequest,
    current_candidate: Candidate = Depends(get_current_candidate),
    db: Session = Depends(get_db)
):
    if not payload.confirm_details:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You must confirm that your details are correct."
        )

    current_candidate.has_verified_details = True
    current_candidate.verified_at = datetime.datetime.utcnow()
    db.commit()

    return {"status": "verified"}

@router.get("", response_model=List[CandidateBase])
def list_candidates(
    current_admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    # Returns all candidates for admin dashboard
    return db.query(Candidate).all()

@router.get("/applications", response_model=List[StudentApplicationBase])
def list_student_applications(
    current_admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    # Returns all applications for admin dashboard
    return db.query(StudentApplication).all()
