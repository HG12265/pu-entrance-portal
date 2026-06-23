import datetime
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
            total_questions=30,
            duration_minutes=30,
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
    
    questions = db.query(Question).filter(Question.exam_id == exam.id).all()
    if not questions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No questions are available in the question bank for this exam."
        )
        
    # Create new attempt if it doesn't exist
    if not attempt:
        attempt = ExamAttempt(
            candidate_id=current_candidate.id,
            exam_id=exam.id,
            started_at=now,
            is_submitted=False
        )
        db.add(attempt)
        db.commit()
        db.refresh(attempt)
        
        # Populate empty answers for all questions
        for q in questions:
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
        # Load from the first available application
        ug_perc = current_candidate.applications[0].ug_marks or 0.0

    if attempt.is_submitted:
        saved_answers = db.query(StudentAnswer).filter(StudentAnswer.attempt_id == attempt.id).all()
        attempted_count = sum(1 for ans in saved_answers if ans.selected_option is not None)
        
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
        
    questions = db.query(Question).filter(Question.exam_id == exam.id).all()
    saved_answers = db.query(StudentAnswer).filter(StudentAnswer.attempt_id == attempt.id).all()
    answers_map = {ans.question_id: ans for ans in saved_answers}
    
    correct_count = 0
    wrong_count = 0
    attempted_count = 0
    total_score = 0.0
    
    for q in questions:
        ans = answers_map.get(q.id)
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
        
    max_possible_score = sum([q.marks for q in questions])
    percentage = 0.0
    if max_possible_score > 0:
        percentage = round((total_score / max_possible_score) * 100, 2)
        
    attempt.is_submitted = True
    attempt.submitted_at = datetime.datetime.utcnow()
    attempt.total_questions = len(questions)
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
