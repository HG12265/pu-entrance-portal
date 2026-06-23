import re
import io
import json
import datetime
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, status, Request, UploadFile, File, Query
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Dict, Any, List, Optional
from app.database import get_db
from app.models import Admin, Course, Candidate, StudentApplication, ImportBatch, AdmissionConfirmation, Exam, Question, ExamAttempt
from app.schemas import AdminResponse, Token, CourseBase, CourseUpdate, CounsellingConfirmRequest
from app.auth import create_access_token, get_current_admin, verify_password, get_password_hash
from app.limiter import limiter
from app.utils.mobile import normalize_mobile
from app.utils.names import are_names_equivalent

router = APIRouter(prefix="/api/v1/auth", tags=["Admin Auth"])

# Helper functions for validation
def clean_header_string(header: str) -> str:
    h = str(header).lower()
    # Remove dots, brackets, percentage symbols, hyphens, slashes
    h = re.sub(r'[\.\(\)%\-\/]', ' ', h)
    h = re.sub(r'\s+', ' ', h).strip()
    return h

def normalize_header(col_name: str) -> str:
    cleaned = clean_header_string(col_name)
    
    exact_mappings = {
        # Ignored columns
        "s no": "ignore",
        "sno": "ignore",
        "sl no": "ignore",
        "slno": "ignore",
        "serial no": "ignore",
        "serialno": "ignore",
        "sr no": "ignore",
        "srno": "ignore",
        "serial number": "ignore",
        "serialnumber": "ignore",
        "no": "ignore",
        
        # Course name
        "degree course": "course_name",
        "degreecourse": "course_name",
        "degree": "course_name",
        "course": "course_name",
        
        # Application No
        "application no": "application_number",
        "applicationno": "application_number",
        "application number": "application_number",
        "applicationnumber": "application_number",
        "app no": "application_number",
        "appno": "application_number",
        "app number": "application_number",
        "appnumber": "application_number",
        
        # Student Name
        "student name": "full_name",
        "studentname": "full_name",
        "applicant name": "full_name",
        "applicantname": "full_name",
        "name": "full_name",
        "full name": "full_name",
        "fullname": "full_name",
        
        # DOB
        "dob": "date_of_birth",
        "date of birth": "date_of_birth",
        "dateofbirth": "date_of_birth",
        "birth date": "date_of_birth",
        "birthdate": "date_of_birth",
        
        # Community
        "community": "community",
        "category": "community",
        
        # Quota
        "quota": "quota",
        
        # Email
        "e mail": "email",
        "email": "email",
        "email id": "email",
        "emailid": "email",
        "mail id": "email",
        "mailid": "email",
        
        # Mobile
        "mobile no": "mobile_number",
        "mobileno": "mobile_number",
        "mobile number": "mobile_number",
        "mobilenumber": "mobile_number",
        "phone": "mobile_number",
        "phone number": "mobile_number",
        "phonenumber": "mobile_number",
        "contact number": "mobile_number",
        "contactnumber": "mobile_number",
        
        # UG Marks
        "percentage": "ug_marks",
        "ug percentage": "ug_marks",
        "ugpercentage": "ug_marks",
        "ug": "ug_marks",
        "ug %": "ug_marks",
        "ug%": "ug_marks",
        "marks percentage": "ug_marks",
        "markspercentage": "ug_marks",
        
        # UG Degree
        "ug degree": "ug_degree",
        "ugdegree": "ug_degree",
        "degree name": "ug_degree",
        "degreename": "ug_degree",
        "qualification": "ug_degree"
    }
    
    # Do exact match first
    if cleaned in exact_mappings:
        return exact_mappings[cleaned]
        
    no_spaces = cleaned.replace(" ", "")
    if no_spaces in exact_mappings:
        return exact_mappings[no_spaces]
        
    # Safe fallbacks (non-ambiguous containing queries)
    # Note: We do not check for "name" alone to avoid mapping unknown columns to full_name.
    if "application no" in cleaned or "application number" in cleaned:
        return "application_number"
    if "student name" in cleaned or "applicant name" in cleaned or "full name" in cleaned:
        return "full_name"
    if "mobile number" in cleaned or "contact number" in cleaned:
        return "mobile_number"
    if "date of birth" in cleaned:
        return "date_of_birth"
    if "email" in cleaned:
        return "email"
    if "ug percentage" in cleaned or "marks percentage" in cleaned:
        return "ug_marks"
    if "ug degree" in cleaned:
        return "ug_degree"
    if "quota" in cleaned:
        return "quota"
    if "community" in cleaned or "category" in cleaned:
        return "community"
        
    return cleaned

def normalize_course_text(text: str) -> str:
    t = str(text).lower()
    t = t.replace(".", "")
    t = re.sub(r'[\/\-_]', ' ', t)
    t = re.sub(r'\s+', ' ', t).strip()
    return t

def map_course_to_code(course_str: str) -> Optional[str]:
    if not course_str or pd.isna(course_str):
        return None
    normalized = normalize_course_text(course_str)
    
    # Normalized aliases lookup
    mapping = {
        # MSC_CS
        "msc computer science": "MSC_CS",
        "msc cs": "MSC_CS",
        "master of science computer science": "MSC_CS",
        "master of science in computer science": "MSC_CS",
        "m sc computer science": "MSC_CS",
        
        # MCA
        "mca": "MCA",
        "master of computer applications": "MCA",
        "master of computer application": "MCA",
        
        # MSC_DS
        "msc data science": "MSC_DS",
        "msc ds": "MSC_DS",
        "master of science data science": "MSC_DS",
        "master of science in data science": "MSC_DS",
    }
    
    if normalized in mapping:
        return mapping[normalized]
        
    flat = normalized.replace(" ", "")
    mapping_flat = {k.replace(" ", ""): v for k, v in mapping.items()}
    if flat in mapping_flat:
        return mapping_flat[flat]
        
    return None

def course_mismatch(course_obj, val: str) -> bool:
    if not val or pd.isna(val) or str(val).strip() == "":
        return False
        
    val_str = str(val).strip()
    mapped_code = map_course_to_code(val_str)
    if mapped_code is not None:
        return mapped_code != course_obj.code
        
    # Fallback to simple matching if not in predefined aliases
    v_norm = normalize_course_text(val_str)
    c_name_norm = normalize_course_text(course_obj.name)
    c_code_norm = normalize_course_text(course_obj.code)
    
    if v_norm == c_code_norm or v_norm == c_name_norm:
        return False
        
    # Substring check
    if v_norm in c_name_norm or c_name_norm in v_norm:
        return False
        
    # Initials check (e.g. Master of Computer Applications -> MCA)
    c_words = v_norm.split()
    initials = "".join([w[0] for w in c_words if w])
    if initials == c_code_norm:
        return False
        
    return True


def name_mismatch(n1: str, n2: str) -> bool:
    return not are_names_equivalent(n1, n2)

@router.post("/login", response_model=Token)
@limiter.limit("5/minute")
def login_for_access_token(request: Request, form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    admin = db.query(Admin).filter(Admin.username == form_data.username).first()
    if not admin or not verify_password(form_data.password, admin.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    # Include admin specific JWT payload properties
    token_data = {
        "sub": admin.username,
        "role": "admin",
        "token_type": "admin"
    }
    access_token = create_access_token(data=token_data)
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/me", response_model=AdminResponse)
def read_admin_me(current_admin: Admin = Depends(get_current_admin)):
    return current_admin

@router.get("/dashboard-stats")
def get_dashboard_stats(current_admin: Admin = Depends(get_current_admin), db: Session = Depends(get_db)):
    total_candidates = db.query(Candidate).count()
    total_applications = db.query(StudentApplication).count()
    total_exams = db.query(Exam).count()
    total_questions = db.query(Question).count()
    total_submissions = db.query(ExamAttempt).filter(ExamAttempt.is_submitted == True).count()
    total_active_attempts = db.query(ExamAttempt).filter(ExamAttempt.is_submitted == False).count()

    # Submissions by course code
    course_counts = db.query(
        Course.code, func.count(StudentApplication.id)
    ).join(
        StudentApplication, StudentApplication.course_id == Course.id
    ).group_by(Course.code).all()
    course_stats = {code: count for code, count in course_counts}

    # Community distribution
    community_counts = db.query(
        Candidate.community, func.count(Candidate.id)
    ).group_by(Candidate.community).all()
    community_stats = {comm if comm else "OC": count for comm, count in community_counts}

    # Average scores
    avg_score = db.query(func.avg(ExamAttempt.score)).filter(ExamAttempt.is_submitted == True).scalar()
    avg_score = round(float(avg_score), 2) if avg_score is not None else 0.0

    return {
        "totals": {
            "candidates": total_candidates,
            "applications": total_applications,
            "exams": total_exams,
            "questions": total_questions,
            "submissions": total_submissions,
            "active_attempts": total_active_attempts,
            "average_score": avg_score
        },
        "by_degree": course_stats,
        "by_community": community_stats
    }

# Excel Application Upload Endpoint
@router.post("/applications/upload")
async def upload_applications(
    course_id: int,
    file: Optional[UploadFile] = File(None),
    init_filename: Optional[str] = Query(None),
    current_admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Selected course not found.")

    # 1. Resolve file content source
    filename = "unknown"
    contents = None
    
    if file:
        filename = file.filename
        contents = await file.read()
    elif init_filename:
        filename = init_filename
        # Check backend/student-data folder
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        file_path = os.path.join(base_dir, "student-data", init_filename)
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail=f"Initial seed file '{init_filename}' not found in student-data.")
        with open(file_path, "rb") as f:
            contents = f.read()
    else:
        raise HTTPException(status_code=400, detail="Please upload a file or specify a seed filename.")

    # 2. Parse Excel using Pandas
    try:
        if filename.endswith(".csv"):
            df = pd.read_csv(io.BytesIO(contents))
        else:
            df = pd.read_excel(io.BytesIO(contents))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to read file: {e}")

    if df.empty:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    # Track original columns
    detected_cols = list(df.columns)
    
    # Normalize headers
    mapped_cols = []
    ignored_cols = []
    for col in df.columns:
        norm = normalize_header(col)
        mapped_cols.append(norm)
        if norm == "ignore":
            ignored_cols.append(col)
            
    df.columns = mapped_cols

    # Drop ignored columns
    if "ignore" in df.columns:
        df = df.drop(columns=["ignore"], errors="ignore")

    # Filter out completely blank/empty rows before required column checks & row iteration
    non_blank_mask = ~df.apply(lambda s: s.apply(lambda x: pd.isna(x) or str(x).strip() == "")).all(axis=1)
    blank_rows_skipped = len(non_blank_mask) - non_blank_mask.sum()
    df = df[non_blank_mask]

    required_fields = ["application_number", "full_name", "mobile_number"]
    missing_required = [f for f in required_fields if f not in df.columns]
    
    if missing_required:
        raise HTTPException(
            status_code=400,
            detail={
                "message": f"Required column(s) {', '.join(missing_required)} is/are missing.",
                "detected_columns": detected_cols,
                "missing_required_columns": missing_required,
                "ignored_columns": ignored_cols,
                "blank_rows_skipped": int(blank_rows_skipped)
            }
        )

    if df.empty:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Uploaded file contains only blank or ignored rows.",
                "detected_columns": detected_cols,
                "missing_required_columns": [],
                "ignored_columns": ignored_cols,
                "blank_rows_skipped": int(blank_rows_skipped)
            }
        )

    inserted_count = 0
    updated_count = 0
    skipped_count = 0
    error_count = 0
    errors = []
    warnings = []

    # Create import batch run entry
    batch = ImportBatch(
        course_id=course.id,
        filename=filename,
        uploaded_by_admin_id=current_admin.id,
        total_rows=len(df)
    )
    db.add(batch)
    db.flush()

    for idx, row in df.iterrows():
        row_num = idx + 2
        try:
            app_no = str(row["application_number"]).strip()
            name = str(row["full_name"]).strip()
            mobile = normalize_mobile(str(row["mobile_number"]))
            
            if not app_no or not name or not mobile:
                skipped_count += 1
                errors.append(f"Row {row_num}: Application Number, Name, or Mobile cannot be empty.")
                continue

            email = str(row["email"]).strip() if "email" in df.columns and not pd.isna(row["email"]) else None
            community = str(row["community"]).strip() if "community" in df.columns and not pd.isna(row["community"]) else "OC"
            
            ug_val = None
            if "ug_marks" in df.columns and not pd.isna(row["ug_marks"]):
                try:
                    ug_val = float(row["ug_marks"])
                except:
                    pass

            dob_val = None
            if "date_of_birth" in df.columns and not pd.isna(row["date_of_birth"]):
                try:
                    val = row["date_of_birth"]
                    if isinstance(val, (datetime.datetime, datetime.date)):
                        dob_val = val
                    else:
                        dob_val = datetime.datetime.strptime(str(val).strip(), "%Y-%m-%d").date()
                except:
                    pass

            # Course mismatch warning
            if "course_name" in df.columns and not pd.isna(row["course_name"]):
                course_val = str(row["course_name"]).strip()
                if course_val != "" and course_mismatch(course, course_val):
                    warnings.append(
                        f"Row {row_num}: Course Mismatch - Row lists course as {course_val}, but batch uploaded for {course.name}"
                    )

            # Store extra unknown / database-unsupported columns in raw_details
            extra_details = {}
            for col in df.columns:
                if col not in ["application_number", "full_name", "mobile_number", "email", "community", "ug_marks", "date_of_birth"]:
                    val = row[col]
                    extra_details[col] = str(val) if not pd.isna(val) else None

            raw_details_str = json.dumps(extra_details)

            # Check if application_number exists globally
            existing_app = db.query(StudentApplication).filter(
                StudentApplication.application_number == app_no
            ).first()

            if existing_app:
                # ── Check if any critical details changed for re-verification reset ──
                # Critical fields: Name, Email, Community, DOB, UG Marks
                dob_match = True
                if dob_val is not None:
                    # fetch candidate
                    cand = db.query(Candidate).filter(Candidate.id == existing_app.candidate_id).first()
                    if cand and cand.date_of_birth != dob_val:
                        dob_match = False
                
                name_changed = name_mismatch(existing_app.full_name, name)
                email_changed = (existing_app.email != email)
                comm_changed = (existing_app.community != community)
                ug_changed = (existing_app.ug_marks != ug_val)

                if name_changed or email_changed or comm_changed or ug_changed or not dob_match:
                    # Reset candidate verification
                    candidate = db.query(Candidate).filter(Candidate.id == existing_app.candidate_id).first()
                    if candidate and candidate.has_verified_details:
                        candidate.has_verified_details = False
                        candidate.verified_at = None
                        warnings.append(
                            f"Row {row_num}: Candidate details changed for Application {app_no}. Verification status reset to False (attempts preserved)."
                        )

                # Update application record
                existing_app.full_name = name
                existing_app.email = email
                existing_app.community = community
                existing_app.mobile_number = mobile
                existing_app.ug_marks = ug_val
                existing_app.raw_details_json = raw_details_str
                existing_app.import_batch_id = batch.id
                
                # Update Candidate common fields
                candidate = db.query(Candidate).filter(Candidate.id == existing_app.candidate_id).first()
                if candidate:
                    candidate.full_name = name
                    if candidate.mobile_number != mobile:
                        warnings.append(
                            f"Row {row_num}: Uploaded mobile '{mobile}' differs from Candidate's registered mobile '{candidate.mobile_number}'."
                        )
                    if email:
                        candidate.email = email
                    if community:
                        candidate.community = community
                    if dob_val:
                        candidate.date_of_birth = dob_val

                updated_count += 1
            else:
                # Find Candidate by normalized mobile
                candidate = db.query(Candidate).filter(Candidate.mobile_number == mobile).first()
                
                if candidate:
                    # Check if name is mismatched (mismatch warning)
                    if name_mismatch(candidate.full_name, name):
                        warnings.append(
                            f"Row {row_num}: possible_duplicate_mobile_name_mismatch - Mobile '{mobile}' already links to candidate '{candidate.full_name}', but row lists applicant name as '{name}'."
                        )
                else:
                    # Create new candidate
                    candidate = Candidate(
                        mobile_number=mobile,
                        full_name=name,
                        email=email,
                        community=community,
                        date_of_birth=dob_val,
                        has_verified_details=False
                    )
                    db.add(candidate)
                    db.flush()

                # Add application record
                app_entry = StudentApplication(
                    candidate_id=candidate.id,
                    course_id=course.id,
                    application_number=app_no,
                    mobile_number=mobile,
                    full_name=name,
                    email=email,
                    community=community,
                    ug_marks=ug_val,
                    raw_details_json=raw_details_str,
                    import_batch_id=batch.id
                )
                db.add(app_entry)
                inserted_count += 1

        except Exception as row_error:
            error_count += 1
            errors.append(f"Row {row_num}: processing failed due to {str(row_error)}")

    # Update batch summary counts
    batch.inserted_count = inserted_count
    batch.updated_count = updated_count
    batch.skipped_count = skipped_count
    batch.error_count = error_count
    batch.errors_json = json.dumps({"errors": errors, "warnings": warnings})
    db.commit()

    return {
        "status": "success" if not errors else "partial_success",
        "batch_id": batch.id,
        "total_rows": len(df),
        "inserted_count": inserted_count,
        "updated_count": updated_count,
        "skipped_count": skipped_count,
        "error_count": error_count,
        "warnings": warnings,
        "errors": errors,
        "detected_columns": detected_cols,
        "missing_required_columns": missing_required,
        "ignored_columns": ignored_cols,
        "blank_rows_skipped": int(blank_rows_skipped)
    }

# Counselling Confirmation Endpoints
@router.post("/counselling/confirm")
def confirm_counselling(
    payload: CounsellingConfirmRequest,
    current_admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    candidate = db.query(Candidate).filter(Candidate.id == payload.candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found.")
        
    course = db.query(Course).filter(Course.id == payload.course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Selected Course not found.")

    # Candidate must have applied for that course
    app_record = db.query(StudentApplication).filter(
        StudentApplication.candidate_id == candidate.id,
        StudentApplication.course_id == course.id
    ).first()
    if not app_record:
        raise HTTPException(
            status_code=400,
            detail=f"Candidate has not applied for course code '{course.code}'."
        )

    # Candidate must have submitted the exam
    attempt = db.query(ExamAttempt).filter(
        ExamAttempt.candidate_id == candidate.id,
        ExamAttempt.is_submitted == True
    ).first()
    if not attempt:
        raise HTTPException(
            status_code=400,
            detail="Candidate has not completed or submitted the entrance exam."
        )

    # Update candidate confirmation
    candidate.admitted_course_id = course.id
    candidate.admission_confirmed_at = datetime.datetime.utcnow()

    # Log selection history
    conf_log = AdmissionConfirmation(
        candidate_id=candidate.id,
        course_id=course.id,
        confirmed_by_admin_id=current_admin.id,
        confirmed_at=datetime.datetime.utcnow(),
        status="confirmed"
    )
    db.add(conf_log)
    db.commit()

    return {
        "status": "confirmed",
        "candidate_id": candidate.id,
        "course_code": course.code,
        "student_name": candidate.full_name
    }

@router.post("/counselling/cancel")
def cancel_counselling(
    payload: CounsellingConfirmRequest,
    current_admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    candidate = db.query(Candidate).filter(Candidate.id == payload.candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found.")

    course_id = candidate.admitted_course_id
    if not course_id:
        raise HTTPException(status_code=400, detail="Candidate has no active admission confirmation to cancel.")

    # Reset
    candidate.admitted_course_id = None
    candidate.admission_confirmed_at = None

    # Log cancel selection history
    conf_log = AdmissionConfirmation(
        candidate_id=candidate.id,
        course_id=course_id,
        confirmed_by_admin_id=current_admin.id,
        confirmed_at=datetime.datetime.utcnow(),
        status="cancelled"
    )
    db.add(conf_log)
    db.commit()

    return {
        "status": "cancelled",
        "candidate_id": candidate.id
    }

# Course Settings Endpoints
@router.get("/courses", response_model=List[CourseBase])
def get_courses(
    current_admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    return db.query(Course).all()

@router.put("/courses/{course_id}", response_model=CourseBase)
def update_course(
    course_id: int,
    payload: CourseUpdate,
    current_admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found.")
    course.seat_count = payload.seat_count
    if payload.is_active is not None:
        course.is_active = payload.is_active
    db.commit()
    db.refresh(course)
    return course
