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
    if not exam:
        exam = Exam(
            name="Periyar University Entrance Examination 2026",
            total_questions=100,
            duration_minutes=120,
            start_date=datetime.datetime.utcnow(),
            end_date=datetime.datetime.utcnow() + datetime.timedelta(days=30),
            result_visibility=True
        )
        db.add(exam)
        db.commit()
        db.refresh(exam)
    return exam

@router.get("/active")
def get_active_exam(db: Session = Depends(get_db)):
    exam = get_main_exam(db)
    now = datetime.datetime.utcnow()
    is_active = exam.start_date <= now <= exam.end_date
    return {
        "id": exam.id,
        "name": exam.name,
        "total_questions": exam.total_questions,
        "duration_minutes": exam.duration_minutes,
        "start_date": exam.start_date,
        "end_date": exam.end_date,
        "result_visibility": exam.result_visibility,
        "is_active_now": is_active,
        "server_time": now
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
    now = datetime.datetime.utcnow()
    
    # 3. Check exam window
    if now < exam.start_date or now > exam.end_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The examination is not currently active or available."
        )
        
    # 4. Check for existing attempts
    attempt = db.query(ExamAttempt).filter(
        ExamAttempt.candidate_id == current_candidate.id,
        ExamAttempt.exam_id == exam.id
    ).first()
    
    if attempt and attempt.is_submitted:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You have already submitted and completed this examination."
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
            is_submitted=False
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

    saved_answers = db.query(StudentAnswer).filter(StudentAnswer.attempt_id == attempt.id).all()
    answers_map = {ans.question_id: ans.selected_option for ans in saved_answers}

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

    elapsed_seconds = (now - attempt.started_at).total_seconds()
    duration_seconds = exam.duration_minutes * 60
    remaining_seconds = max(0, int(duration_seconds - elapsed_seconds))

    return {
        "attempt_id": attempt.id,
        "exam_name": exam.name,
        "duration_minutes": exam.duration_minutes,
        "remaining_seconds": remaining_seconds,
        "questions": questions_list,
        "answers": answers_map
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
    if attempt.is_submitted:
        raise HTTPException(status_code=400, detail="Cannot edit answers of a submitted exam.")
        
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
    db.commit()
    return {"status": "saved"}

class SubmitExamPayload(BaseModel):
    attempt_id: int

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

    if attempt.is_submitted:
        saved_answers = db.query(StudentAnswer).filter(StudentAnswer.attempt_id == attempt.id).all()
        attempted_count = sum(1 for ans in saved_answers if ans.selected_option is not None and ans.question_id in final_order)
        
        entrance_perc = attempt.percentage
        final_perc = round((ug_perc * 0.5) + (entrance_perc * 0.5), 2)
        
        return {
            "attempt_id": attempt.id,
            "mobile_number": current_candidate.mobile_number,
            "student_name": current_candidate.full_name,
            "degrees": degrees_list,
            "total_questions": attempt.total_questions,
            "attempted_questions": attempted_count,
            "correct_answers": attempt.correct_answers,
            "wrong_answers": attempt.wrong_answers,
            "score": attempt.score,
            "percentage": attempt.percentage,
            "ug_percentage": ug_perc,
            "entrance_percentage": entrance_perc,
            "final_percentage": final_perc,
            "result_visibility": exam.result_visibility
        }
        
    all_questions = db.query(Question).filter(Question.exam_id == exam.id).all()
    q_map = {q.id: q for q in all_questions}
    
    saved_answers = db.query(StudentAnswer).filter(StudentAnswer.attempt_id == attempt.id).all()
    answers_map = {ans.question_id: ans for ans in saved_answers}
    
    correct_count = 0
    wrong_count = 0
    attempted_count = 0
    total_score = 0.0
    
    # Grade only questions present in the saved final_order
    for q_id in final_order:
        q = q_map.get(q_id)
        if not q:
            continue
        ans = answers_map.get(q_id)
        selected = ans.selected_option if ans else None
        
        if selected:
            attempted_count += 1
            if selected.upper() == q.correct_option.upper():
                correct_count += 1
                score_diff = q.marks
                if ans:
                    ans.is_correct = True
                    ans.marks_obtained = score_diff
            else:
                wrong_count += 1
                score_diff = 0.0
                if ans:
                    ans.is_correct = False
                    ans.marks_obtained = score_diff
        else:
            score_diff = 0.0
            if ans:
                ans.is_correct = None
                ans.marks_obtained = score_diff
                
        total_score += score_diff
        
    max_possible_score = sum([q_map[qid].marks for qid in final_order if qid in q_map])
    percentage = 0.0
    if max_possible_score > 0:
        percentage = round((total_score / max_possible_score) * 100, 2)
        
    attempt.is_submitted = True
    attempt.submitted_at = datetime.datetime.utcnow()
    attempt.total_questions = len(final_order)
    attempt.correct_answers = correct_count
    attempt.wrong_answers = wrong_count
    attempt.score = total_score
    attempt.percentage = percentage
    
    db.commit()
    db.refresh(attempt)
    
    entrance_perc = attempt.percentage
    final_perc = round((ug_perc * 0.5) + (entrance_perc * 0.5), 2)
    
    return {
        "attempt_id": attempt.id,
        "mobile_number": current_candidate.mobile_number,
        "student_name": current_candidate.full_name,
        "degrees": degrees_list,
        "total_questions": attempt.total_questions,
        "attempted_questions": attempted_count,
        "correct_answers": attempt.correct_answers,
        "wrong_answers": attempt.wrong_answers,
        "score": attempt.score,
        "percentage": attempt.percentage,
        "ug_percentage": ug_perc,
        "entrance_percentage": entrance_perc,
        "final_percentage": final_perc,
        "result_visibility": exam.result_visibility
    }
