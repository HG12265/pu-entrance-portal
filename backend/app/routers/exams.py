import datetime
import json
import secrets
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from app.database import get_db
from app.models import Exam, Candidate, StudentApplication, ExamAttempt, Question, StudentAnswer, Admin
from app.schemas import ExamCreate, ExamResponse, ExamSubmitResultResponse, StudentAnswerSave
from app.auth import get_current_admin, get_current_candidate

router = APIRouter(prefix="/api/v1/exams", tags=["Exams"])

def get_main_exam(db: Session) -> Exam:
    exam = db.query(Exam).first()
    import datetime as dt_mod
    start_utc = dt_mod.datetime(2026, 6, 29, 5, 0, 0)
    end_utc = dt_mod.datetime(2026, 6, 29, 7, 0, 0)
    
    if not exam:
        exam = Exam(
            name="Periyar University Entrance Examination 2026",
            total_questions=100,
            duration_minutes=120,
            start_date=start_utc,
            end_date=end_utc,
            start_at_utc=start_utc,
            end_at_utc=end_utc,
            timezone="Asia/Kolkata",
            schedule_mode="FIXED_WINDOW",
            result_visibility=True
        )
        db.add(exam)
        db.commit()
        db.refresh(exam)
    else:
        if exam.start_at_utc is None or exam.end_at_utc is None:
            exam.start_at_utc = start_utc
            exam.end_at_utc = end_utc
            exam.timezone = "Asia/Kolkata"
            exam.schedule_mode = "FIXED_WINDOW"
            db.commit()
            db.refresh(exam)
    return exam

@router.get("/active")
def get_active_exam(db: Session = Depends(get_db)):
    exam = get_main_exam(db)
    
    from app.utils.timezone import now_utc, to_ist, format_ist_for_response
    import datetime as dt_mod
    
    now = now_utc()
    
    start_utc = exam.start_at_utc
    if start_utc is None:
        start_utc = exam.start_date
    if start_utc.tzinfo is None:
        start_utc = start_utc.replace(tzinfo=dt_mod.timezone.utc)
        
    end_utc = exam.end_at_utc
    if end_utc is None:
        end_utc = exam.end_date
    if end_utc.tzinfo is None:
        end_utc = end_utc.replace(tzinfo=dt_mod.timezone.utc)
        
    is_active = start_utc <= now <= end_utc
    is_start_allowed = start_utc <= now < end_utc
    exam_not_started = now < start_utc
    seconds_until_start = max(0, int((start_utc - now).total_seconds()))
    
    starts_at_ist = format_ist_for_response(start_utc)
    ends_at_ist = format_ist_for_response(end_utc)
    server_time_ist = format_ist_for_response(now)
    
    return {
        "id": exam.id,
        "name": exam.name,
        "total_questions": exam.total_questions,
        "duration_minutes": exam.duration_minutes,
        "start_date": start_utc,
        "end_date": end_utc,
        "start_at_utc": start_utc,
        "end_at_utc": end_utc,
        "timezone": exam.timezone or "Asia/Kolkata",
        "schedule_mode": exam.schedule_mode or "FIXED_WINDOW",
        "starts_at_ist": starts_at_ist,
        "ends_at_ist": ends_at_ist,
        "is_active_now": is_active,
        "server_time": to_ist(now),
        "server_time_utc": now,
        
        # New timezone lock parameters
        "is_exam_configured": True,
        "is_login_allowed": True,
        "is_start_allowed": is_start_allowed,
        "exam_not_started": exam_not_started,
        "seconds_until_start": seconds_until_start,
        "server_time_ist": server_time_ist
    }

@router.put("/settings", response_model=ExamResponse)
def update_exam_settings(exam_data: ExamCreate, current_admin: Admin = Depends(get_current_admin), db: Session = Depends(get_db)):
    exam = db.query(Exam).first()
    if not exam:
        exam = Exam()
        db.add(exam)
    
    exam.name = exam_data.name
    exam.total_questions = exam_data.total_questions
    exam.duration_minutes = exam_data.duration_minutes
    exam.start_date = exam_data.start_date
    exam.end_date = exam_data.end_date
    exam.result_visibility = exam_data.result_visibility
    
    db.commit()
    db.refresh(exam)
    return exam

@router.post("/start")
def start_exam(current_candidate: Candidate = Depends(get_current_candidate), db: Session = Depends(get_db)):
    # 1. Enforce student verification lock
    if not current_candidate.has_verified_details:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You must verify your details before starting the examination."
        )
        
    # 2. Check if candidate has active applications
    active_apps = db.query(StudentApplication).filter(
        StudentApplication.candidate_id == current_candidate.id,
        StudentApplication.is_active == True
    ).all()
    if not active_apps:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active applications found for this student session."
        )

    exam = get_main_exam(db)
    
    from app.utils.timezone import now_utc, format_ist_for_response
    now = now_utc()
    
    start_at_utc = exam.start_at_utc
    if start_at_utc is None:
        start_at_utc = exam.start_date
    if start_at_utc.tzinfo is None:
        start_at_utc = start_at_utc.replace(tzinfo=datetime.timezone.utc)
        
    end_at_utc = exam.end_at_utc
    if end_at_utc is None:
        end_at_utc = exam.end_date
    if end_at_utc.tzinfo is None:
        end_at_utc = end_at_utc.replace(tzinfo=datetime.timezone.utc)
        
    # 3. Check if before start
    if now < start_at_utc:
        seconds_until_start = int((start_at_utc - now).total_seconds())
        starts_at_ist = format_ist_for_response(start_at_utc)
        server_time_ist = format_ist_for_response(now)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "detail": "Exam has not started yet.",
                "exam_not_started": True,
                "seconds_until_start": seconds_until_start,
                "starts_at_ist": starts_at_ist,
                "server_time_ist": server_time_ist
            }
        )
        
    # 4. Check for existing attempts
    attempt = db.query(ExamAttempt).filter(
        ExamAttempt.candidate_id == current_candidate.id,
        ExamAttempt.exam_id == exam.id
    ).first()
    
    extension_mins = attempt.time_extension_minutes if attempt else 0
    effective_end_at_utc = end_at_utc + datetime.timedelta(minutes=extension_mins)
    
    # 5. Check if after effective end time
    if now >= effective_end_at_utc:
        if attempt and attempt.status in ["active", "admin_reopened"]:
            # Auto submit it
            attempt.is_submitted = True
            attempt.submitted_at = now.replace(tzinfo=None) # Store naive UTC
            # Calculate elapsed seconds and cap it
            elapsed = (now - attempt.started_at.replace(tzinfo=datetime.timezone.utc)).total_seconds()
            total_duration_sec = (exam.duration_minutes + attempt.time_extension_minutes) * 60
            attempt.elapsed_seconds_at_submit = max(0, min(int(elapsed), int(total_duration_sec)))
            attempt.submit_source = "time_over"
            attempt.submitted_reason = "Exam time is over"
            attempt.status = "auto_submitted"
            
            from app.utils.scoring import calculate_and_save_score
            calculate_and_save_score(db, attempt)
            db.commit()
            
            from app.utils.event_logger import log_event
            log_event(
                db,
                attempt.id,
                current_candidate.id,
                "auto_submitted",
                "Exam attempt auto-submitted as exam window closed",
                metadata={
                    "submit_source": "time_over",
                    "submitted_reason": "Exam time is over",
                    "elapsed_seconds": attempt.elapsed_seconds_at_submit,
                    "score": attempt.score
                }
            )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "detail": "Exam is closed.",
                "exam_closed": True
            }
        )
    
    if attempt and attempt.status in ["submitted", "auto_submitted", "force_submitted"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Your exam has already been submitted. Please contact admin if this was accidental."
        )
    
    # Fetch all questions
    all_questions = db.query(Question).filter(Question.exam_id == exam.id).all()
    
    # Strict validation of counts per part
    part_counts = {"A": 0, "B": 0, "C": 0, "D": 0}
    for q in all_questions:
        if q.part_code in part_counts:
            part_counts[q.part_code] += 1
            
    mismatches = []
    expected_parts = {
        "A": ("Quantitative Ability", 25),
        "B": ("Analytical Reasoning", 25),
        "C": ("Logical Reasoning", 25),
        "D": ("Computer Awareness", 25)
    }
    for p_code, (p_name, expected_count) in expected_parts.items():
        actual = part_counts[p_code]
        if actual != expected_count:
            mismatches.append(f"Part {p_code} ({p_name}): expected {expected_count}, got {actual}")
            
    if mismatches:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"The examination question bank is not configured correctly. Errors: {', '.join(mismatches)}"
        )

    rng = secrets.SystemRandom()
    questions = []

    if not attempt:
        # Create new attempt
        attempt = ExamAttempt(
            candidate_id=current_candidate.id,
            exam_id=exam.id,
            started_at=now,
            is_submitted=False,
            status="active",
            violation_count=0
        )
        db.add(attempt)
        db.commit()
        db.refresh(attempt)

        # Shuffle questions within each part code A, B, C, D
        part_A_qs = [q for q in all_questions if q.part_code == "A"]
        part_B_qs = [q for q in all_questions if q.part_code == "B"]
        part_C_qs = [q for q in all_questions if q.part_code == "C"]
        part_D_qs = [q for q in all_questions if q.part_code == "D"]

        rng.shuffle(part_A_qs)
        rng.shuffle(part_B_qs)
        rng.shuffle(part_C_qs)
        rng.shuffle(part_D_qs)

        # Assemble final ordered list of questions
        ordered_qs = part_A_qs + part_B_qs + part_C_qs + part_D_qs

        # Store question IDs in order JSON
        order_json = {
            "A": [q.id for q in part_A_qs],
            "B": [q.id for q in part_B_qs],
            "C": [q.id for q in part_C_qs],
            "D": [q.id for q in part_D_qs],
            "final_order": [q.id for q in ordered_qs]
        }
        attempt.question_order_json = json.dumps(order_json)
        db.commit()

        # Create StudentAnswer rows only for the final 100 questions
        for q in ordered_qs:
            empty_ans = StudentAnswer(
                attempt_id=attempt.id,
                question_id=q.id,
                selected_option=None,
                is_correct=None,
                marks_obtained=0.0
            )
            db.add(empty_ans)
        db.commit()

        questions = ordered_qs
        
        # Log event
        from app.utils.event_logger import log_event
        log_event(db, attempt.id, current_candidate.id, "started", "Exam session started by candidate")
    else:
        # Resume flow: load stored order from attempt.question_order_json
        if attempt.question_order_json:
            try:
                order_json = json.loads(attempt.question_order_json)
                final_order = order_json.get("final_order", [])
                
                # Fetch questions and sort to match final_order exactly
                q_map = {q.id: q for q in all_questions}
                questions = [q_map[qid] for qid in final_order if qid in q_map]
            except Exception as e:
                # Fallback if json parsing fails: regenerate
                print(f"[ERROR START EXAM] Failed to parse question_order_json: {e}")
                part_A_qs = [q for q in all_questions if q.part_code == "A"]
                part_B_qs = [q for q in all_questions if q.part_code == "B"]
                part_C_qs = [q for q in all_questions if q.part_code == "C"]
                part_D_qs = [q for q in all_questions if q.part_code == "D"]
                rng.shuffle(part_A_qs)
                rng.shuffle(part_B_qs)
                rng.shuffle(part_C_qs)
                rng.shuffle(part_D_qs)
                ordered_qs = part_A_qs + part_B_qs + part_C_qs + part_D_qs
                order_json = {
                    "A": [q.id for q in part_A_qs],
                    "B": [q.id for q in part_B_qs],
                    "C": [q.id for q in part_C_qs],
                    "D": [q.id for q in part_D_qs],
                    "final_order": [q.id for q in ordered_qs]
                }
                attempt.question_order_json = json.dumps(order_json)
                db.commit()
                questions = ordered_qs
        else:
            # Fallback if column is null
            part_A_qs = [q for q in all_questions if q.part_code == "A"]
            part_B_qs = [q for q in all_questions if q.part_code == "B"]
            part_C_qs = [q for q in all_questions if q.part_code == "C"]
            part_D_qs = [q for q in all_questions if q.part_code == "D"]
            rng.shuffle(part_A_qs)
            rng.shuffle(part_B_qs)
            rng.shuffle(part_C_qs)
            rng.shuffle(part_D_qs)
            ordered_qs = part_A_qs + part_B_qs + part_C_qs + part_D_qs
            order_json = {
                "A": [q.id for q in part_A_qs],
                "B": [q.id for q in part_B_qs],
                "C": [q.id for q in part_C_qs],
                "D": [q.id for q in part_D_qs],
                "final_order": [q.id for q in ordered_qs]
            }
            attempt.question_order_json = json.dumps(order_json)
            db.commit()
            questions = ordered_qs

        # Ensure StudentAnswer records exist for all questions in final_order
        existing_answers = db.query(StudentAnswer).filter(StudentAnswer.attempt_id == attempt.id).all()
        existing_qids = {ans.question_id for ans in existing_answers}
        for q in questions:
            if q.id not in existing_qids:
                empty_ans = StudentAnswer(
                    attempt_id=attempt.id,
                    question_id=q.id,
                    selected_option=None,
                    is_correct=None,
                    marks_obtained=0.0
                )
                db.add(empty_ans)
        db.commit()

    # Load saved answers and compute session states
    saved_answers = db.query(StudentAnswer).filter(StudentAnswer.attempt_id == attempt.id).all()
    answers_map = {ans.question_id: ans.selected_option for ans in saved_answers}

    order_json = json.loads(attempt.question_order_json)
    final_order = order_json.get("final_order", [])

    first_unanswered_index = 0
    answered_count = 0
    found_first_unanswered = False

    for idx, qid in enumerate(final_order):
        sel = answers_map.get(qid)
        if sel is not None:
            answered_count += 1
        else:
            if not found_first_unanswered:
                first_unanswered_index = idx
                found_first_unanswered = True

    unanswered_count = len(final_order) - answered_count
    current_question_index = attempt.current_question_index if attempt.current_question_index is not None else first_unanswered_index

    # Log resumed event
    from app.utils.event_logger import log_event
    log_event(
        db,
        attempt.id,
        current_candidate.id,
        "resumed",
        f"Exam attempt resumed. Current index: {current_question_index}. Violation count: {attempt.violation_count}"
    )

    questions_list = []
    for q in questions:
        questions_list.append({
            "id": q.id,
            "question_text": q.question_text,
            "option_a": q.option_a,
            "option_b": q.option_b,
            "option_c": q.option_c,
            "option_d": q.option_d,
            "marks": q.marks,
            "image_url": q.image_url,
            "option_a_image_url": q.option_a_image_url,
            "option_b_image_url": q.option_b_image_url,
            "option_c_image_url": q.option_c_image_url,
            "option_d_image_url": q.option_d_image_url,
            "part_code": q.part_code,
            "part_name": q.part_name,
            "part_order": q.part_order,
            "source_s_no": q.source_s_no
        })

    started_at_aware = attempt.started_at.replace(tzinfo=datetime.timezone.utc) if attempt.started_at.tzinfo is None else attempt.started_at
    if (exam.schedule_mode or "FIXED_WINDOW") == "FIXED_WINDOW":
        rem_sec = (end_at_utc - now).total_seconds() + attempt.time_extension_minutes * 60
        remaining_seconds = max(0, min(int(rem_sec), (exam.duration_minutes + attempt.time_extension_minutes) * 60))
    else:
        elapsed_seconds = (now - started_at_aware).total_seconds()
        duration_seconds = (exam.duration_minutes + attempt.time_extension_minutes) * 60
        remaining_seconds = max(0, int(duration_seconds - elapsed_seconds))

    return {
        "attempt_id": attempt.id,
        "exam_name": exam.name,
        "duration_minutes": exam.duration_minutes,
        "time_extension_minutes": attempt.time_extension_minutes,
        "remaining_seconds": remaining_seconds,
        "questions": questions_list,
        "answers": answers_map,
        "current_question_index": current_question_index,
        "first_unanswered_index": first_unanswered_index,
        "answered_count": answered_count,
        "unanswered_count": unanswered_count,
        "violation_count": attempt.violation_count,
        "status": attempt.status
    }

class SaveAnswerPayload(BaseModel):
    attempt_id: int
    question_id: int
    selected_option: Optional[str] = None

@router.post("/save-answer")
def save_answer(
    payload: SaveAnswerPayload,
    current_candidate: Candidate = Depends(get_current_candidate),
    db: Session = Depends(get_db)
):
    # Retrieve attempt and verify candidate ownership
    attempt = db.query(ExamAttempt).filter(
        ExamAttempt.id == payload.attempt_id,
        ExamAttempt.candidate_id == current_candidate.id
    ).first()
    
    if not attempt:
        raise HTTPException(status_code=404, detail="Exam attempt not found.")
    if attempt.status not in ["active", "admin_reopened"]:
        raise HTTPException(status_code=400, detail="Cannot edit answers of a submitted or inactive exam.")
        
    # Safeguard: ensure the question is in final_order
    if attempt.question_order_json:
        try:
            order_json = json.loads(attempt.question_order_json)
            final_order = order_json.get("final_order", [])
            if payload.question_id not in final_order:
                raise HTTPException(status_code=400, detail="Question is not part of this exam attempt.")
        except Exception as e:
            print(f"[ERROR SAVE ANSWER] Failed to parse question_order_json: {e}")

    db_answer = db.query(StudentAnswer).filter(
        StudentAnswer.attempt_id == payload.attempt_id,
        StudentAnswer.question_id == payload.question_id
    ).first()
    
    if not db_answer:
        db_answer = StudentAnswer(
            attempt_id=payload.attempt_id,
            question_id=payload.question_id
        )
        db.add(db_answer)
        
    db_answer.selected_option = payload.selected_option.upper() if payload.selected_option else None
    db_answer.updated_at = datetime.datetime.utcnow()
    attempt.last_activity_at = datetime.datetime.utcnow()
    db.commit()
    
    # Write event log
    from app.utils.event_logger import log_event
    log_event(
        db,
        attempt.id,
        current_candidate.id,
        "answer_saved",
        f"Answer saved for question {payload.question_id}: {payload.selected_option}",
        metadata={"question_id": payload.question_id, "selected_option": payload.selected_option}
    )
    
    return {"status": "saved"}

class SubmitExamPayload(BaseModel):
    attempt_id: int
    submit_source: Optional[str] = "manual"  # manual, auto_tab_violation, time_over, admin_force
    submitted_reason: Optional[str] = None

@router.post("/submit", response_model=ExamSubmitResultResponse)
def submit_exam(
    payload: SubmitExamPayload,
    current_candidate: Candidate = Depends(get_current_candidate),
    db: Session = Depends(get_db)
):
    # Retrieve attempt and verify candidate ownership
    attempt = db.query(ExamAttempt).filter(
        ExamAttempt.id == payload.attempt_id,
        ExamAttempt.candidate_id == current_candidate.id
    ).first()
    
    if not attempt:
        raise HTTPException(status_code=404, detail="Exam attempt not found.")
        
    exam = db.query(Exam).filter(Exam.id == attempt.exam_id).first()
    
    # Resolve degree codes and ug percentage
    degrees_list = [app.course.code for app in current_candidate.applications]
    ug_perc = 0.0
    if current_candidate.applications:
        ug_perc = current_candidate.applications[0].ug_marks or 0.0

    # Retrieve and parse question order
    if not attempt.question_order_json:
        raise HTTPException(status_code=400, detail="Question order json not found for this attempt.")
        
    order_json = json.loads(attempt.question_order_json)
    final_order = order_json.get("final_order", [])

    if attempt.is_submitted and attempt.status in ["submitted", "auto_submitted", "force_submitted"]:
        saved_answers = db.query(StudentAnswer).filter(StudentAnswer.attempt_id == attempt.id).all()
        attempted_count = sum(1 for ans in saved_answers if ans.selected_option is not None and ans.selected_option != "" and ans.question_id in final_order)
        
        entrance_perc = attempt.percentage
        final_perc = round((ug_perc * 0.5) + (entrance_perc * 0.5), 2)
        
        return {
            "attempt_id": attempt.id,
            "mobile_number": current_candidate.mobile_number,
            "student_name": current_candidate.full_name,
            "degrees": degrees_list,
            "total_questions": attempt.total_questions,
            "attempted_questions": attempted_count,
            "unanswered_questions": max(0, len(final_order) - attempted_count),
            "correct_answers": attempt.correct_answers,
            "wrong_answers": attempt.wrong_answers,
            "score": attempt.score,
            "percentage": attempt.percentage,
            "ug_percentage": ug_perc,
            "entrance_percentage": entrance_perc,
            "final_percentage": final_perc,
            "result_visibility": exam.result_visibility
        }

    # Grade attempt and update score using scoring helper
    from app.utils.scoring import calculate_and_save_score
    calculate_and_save_score(db, attempt)

    from app.utils.timezone import now_utc
    now = now_utc()
    
    end_at_utc = exam.end_at_utc
    if end_at_utc is None:
        end_at_utc = exam.end_date
    if end_at_utc.tzinfo is None:
        end_at_utc = end_at_utc.replace(tzinfo=datetime.timezone.utc)
        
    started_at_aware = attempt.started_at.replace(tzinfo=datetime.timezone.utc) if attempt.started_at.tzinfo is None else attempt.started_at
    
    if (exam.schedule_mode or "FIXED_WINDOW") == "FIXED_WINDOW":
        max_allowed_sec = (end_at_utc - started_at_aware).total_seconds() + attempt.time_extension_minutes * 60
        max_allowed_sec = max(0, min(max_allowed_sec, (exam.duration_minutes + attempt.time_extension_minutes) * 60))
    else:
        max_allowed_sec = (exam.duration_minutes + attempt.time_extension_minutes) * 60
        
    elapsed = (now - started_at_aware).total_seconds()
    attempt.elapsed_seconds_at_submit = max(0, min(int(elapsed), int(max_allowed_sec)))

    attempt.is_submitted = True
    attempt.submitted_at = now.replace(tzinfo=None)
    attempt.submit_source = payload.submit_source or "manual"
    attempt.submitted_reason = payload.submitted_reason
    attempt.status = "auto_submitted" if payload.submit_source == "auto_tab_violation" else "submitted"

    db.commit()
    db.refresh(attempt)

    # Log event
    from app.utils.event_logger import log_event
    log_event(
        db,
        attempt.id,
        current_candidate.id,
        "auto_submitted" if attempt.status == "auto_submitted" else "manual_submitted",
        f"Exam attempt submitted. Source: {attempt.submit_source}. Reason: {attempt.submitted_reason}",
        metadata={
            "submit_source": attempt.submit_source,
            "submitted_reason": attempt.submitted_reason,
            "elapsed_seconds": attempt.elapsed_seconds_at_submit,
            "score": attempt.score
        }
    )

    saved_answers = db.query(StudentAnswer).filter(StudentAnswer.attempt_id == attempt.id).all()
    attempted_count = sum(1 for ans in saved_answers if ans.selected_option is not None and ans.selected_option != "" and ans.question_id in final_order)
    entrance_perc = attempt.percentage
    final_perc = round((ug_perc * 0.5) + (entrance_perc * 0.5), 2)

    return {
        "attempt_id": attempt.id,
        "mobile_number": current_candidate.mobile_number,
        "student_name": current_candidate.full_name,
        "degrees": degrees_list,
        "total_questions": attempt.total_questions,
        "attempted_questions": attempted_count,
        "unanswered_questions": max(0, len(final_order) - attempted_count),
        "correct_answers": attempt.correct_answers,
        "wrong_answers": attempt.wrong_answers,
        "score": attempt.score,
        "percentage": attempt.percentage,
        "ug_percentage": ug_perc,
        "entrance_percentage": entrance_perc,
        "final_percentage": final_perc,
        "result_visibility": exam.result_visibility
    }

class UpdateIndexPayload(BaseModel):
    attempt_id: int
    current_question_index: int

@router.post("/update-index")
def update_current_index(
    payload: UpdateIndexPayload,
    current_candidate: Candidate = Depends(get_current_candidate),
    db: Session = Depends(get_db)
):
    attempt = db.query(ExamAttempt).filter(
        ExamAttempt.id == payload.attempt_id,
        ExamAttempt.candidate_id == current_candidate.id
    ).first()
    
    if not attempt:
        raise HTTPException(status_code=404, detail="Exam attempt not found.")
    if attempt.status not in ["active", "admin_reopened"]:
        raise HTTPException(status_code=400, detail="Cannot update progress of an inactive exam.")
        
    attempt.current_question_index = payload.current_question_index
    attempt.last_activity_at = datetime.datetime.utcnow()
    db.commit()
    return {"status": "success"}

class LogViolationPayload(BaseModel):
    attempt_id: int
    violation_message: str

@router.post("/log-violation")
def log_violation(
    payload: LogViolationPayload,
    current_candidate: Candidate = Depends(get_current_candidate),
    db: Session = Depends(get_db)
):
    attempt = db.query(ExamAttempt).filter(
        ExamAttempt.id == payload.attempt_id,
        ExamAttempt.candidate_id == current_candidate.id
    ).first()
    
    if not attempt:
        raise HTTPException(status_code=404, detail="Exam attempt not found.")
    if attempt.status not in ["active", "admin_reopened"]:
        raise HTTPException(status_code=400, detail="Cannot log violation for inactive exam.")
        
    attempt.violation_count += 1
    attempt.last_activity_at = datetime.datetime.utcnow()
    db.commit()
    
    # Write event log
    from app.utils.event_logger import log_event
    log_event(
        db, 
        attempt.id, 
        current_candidate.id, 
        "tab_violation", 
        payload.violation_message,
        metadata={"violation_count": attempt.violation_count}
    )
    
    return {"status": "success", "violation_count": attempt.violation_count}

