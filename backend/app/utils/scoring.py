import json
from sqlalchemy.orm import Session
from app.models import ExamAttempt, Question, StudentAnswer, Exam

def calculate_and_save_score(db: Session, attempt: ExamAttempt) -> ExamAttempt:
    exam = db.query(Exam).filter(Exam.id == attempt.exam_id).first()
    if not exam:
        return attempt
        
    if not attempt.question_order_json:
        return attempt
        
    order_json = json.loads(attempt.question_order_json)
    final_order = order_json.get("final_order", [])
    
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
        
        if selected is not None and selected != "":
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
        
    attempt.total_questions = len(final_order)
    attempt.correct_answers = correct_count
    attempt.wrong_answers = wrong_count
    attempt.score = total_score
    attempt.percentage = percentage
    
    db.commit()
    return attempt
