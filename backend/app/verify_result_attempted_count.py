import os
import sys
import datetime
import json
from sqlalchemy.orm import Session

# Add project root to python path to access app module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal
from app.models import (
    Candidate,
    StudentApplication,
    ExamAttempt,
    StudentAnswer,
    Exam,
    Question,
    Course
)

from app.routers.exams import (
    start_exam,
    save_answer,
    submit_exam,
    SaveAnswerPayload,
    SubmitExamPayload
)

from app.routers.results import get_my_results

def delete_test_candidate(db: Session, mobile: str):
    print(f"Cleaning up test candidate mobile {mobile}...")
    candidate = db.query(Candidate).filter(Candidate.mobile_number == mobile).first()
    if candidate:
        attempts = db.query(ExamAttempt).filter(ExamAttempt.candidate_id == candidate.id).all()
        attempt_ids = [att.id for att in attempts]
        if attempt_ids:
            db.query(StudentAnswer).filter(StudentAnswer.attempt_id.in_(attempt_ids)).delete(synchronize_session=False)
            db.query(ExamAttempt).filter(ExamAttempt.candidate_id == candidate.id).delete(synchronize_session=False)
        db.query(StudentApplication).filter(StudentApplication.candidate_id == candidate.id).delete()
        db.query(Candidate).filter(Candidate.id == candidate.id).delete()
        db.commit()

def main():
    db = SessionLocal()
    test_mobile = "9990000095"
    try:
        # 1. Clean up old candidate
        delete_test_candidate(db, test_mobile)

        # 2. Get Course MCA
        mca = db.query(Course).filter(Course.code == "MCA").first()
        if not mca:
            mca = Course(code="MCA", name="Master of Computer Applications", seat_count=30, is_active=True)
            db.add(mca)
            db.commit()
            db.refresh(mca)

        # 3. Get or create Exam
        exam = db.query(Exam).first()
        if not exam:
            exam = Exam(
                name="Periyar University Entrance Examination 2026",
                total_questions=100,
                duration_minutes=120,
                start_date=datetime.datetime.utcnow() - datetime.timedelta(days=1),
                end_date=datetime.datetime.utcnow() + datetime.timedelta(days=1),
                start_at_utc=datetime.datetime.utcnow() - datetime.timedelta(days=1),
                end_at_utc=datetime.datetime.utcnow() + datetime.timedelta(days=1),
                result_visibility=True
            )
            db.add(exam)
            db.commit()
            db.refresh(exam)
        else:
            exam.total_questions = 100
            exam.duration_minutes = 120
            exam.start_date = datetime.datetime.utcnow() - datetime.timedelta(days=1)
            exam.end_date = datetime.datetime.utcnow() + datetime.timedelta(days=1)
            exam.start_at_utc = datetime.datetime.utcnow() - datetime.timedelta(days=1)
            exam.end_at_utc = datetime.datetime.utcnow() + datetime.timedelta(days=1)
            db.commit()

        # 4. Ensure balanced questions (25 per part)
        parts_info = {
            "A": ("Quantitative Ability", 1),
            "B": ("Analytical Reasoning", 2),
            "C": ("Logical Reasoning", 3),
            "D": ("Computer Awareness", 4)
        }
        for part_code, (part_name, part_order) in parts_info.items():
            existing_cnt = db.query(Question).filter(
                Question.exam_id == exam.id,
                Question.part_code == part_code
            ).count()
            needed = 25 - existing_cnt
            if needed > 0:
                print(f"Seeding {needed} questions for Part {part_code}...")
                for i in range(needed):
                    q = Question(
                        exam_id=exam.id,
                        question_text=f"Q {i} Part {part_code}",
                        option_a="A",
                        option_b="B",
                        option_c="C",
                        option_d="D",
                        correct_option="A",
                        marks=1.0,
                        part_code=part_code,
                        part_name=part_name,
                        part_order=part_order
                    )
                    db.add(q)
                db.commit()

        # 5. Create Candidate
        candidate = Candidate(
            mobile_number=test_mobile,
            full_name="Attempt Counter Candidate",
            community="OC",
            has_verified_details=True
        )
        db.add(candidate)
        db.commit()
        db.refresh(candidate)

        app = StudentApplication(
            candidate_id=candidate.id,
            course_id=mca.id,
            application_number="APP-995-MCA",
            mobile_number=test_mobile,
            full_name="Attempt Counter Candidate",
            community="OC",
            ug_marks=80.0,
            is_active=True
        )
        db.add(app)
        db.commit()

        # 6. Start exam
        print("Starting exam...")
        start_res = start_exam(current_candidate=candidate, db=db)
        attempt_id = start_res["attempt_id"]
        questions = start_res["questions"]

        # Gather questions list and map correct/wrong option
        # We need 15 answered questions total:
        # - 5 correct: we answer matching the correct_option ("A")
        # - 10 wrong: we answer with a wrong option ("B" instead of "A")
        print("Answering 15 questions (5 correct, 10 wrong)...")
        db_qs = {q.id: q for q in db.query(Question).filter(Question.exam_id == exam.id).all()}
        
        for i in range(15):
            q_id = questions[i]["id"]
            q_obj = db_qs[q_id]
            
            # Answer option
            if i < 5:
                # Correct answer
                sel_opt = q_obj.correct_option
            else:
                # Wrong answer
                sel_opt = "B" if q_obj.correct_option != "B" else "C"
                
            save_answer(
                payload=SaveAnswerPayload(attempt_id=attempt_id, question_id=q_id, selected_option=sel_opt),
                current_candidate=candidate,
                db=db
            )

        print("Submitting exam...")
        submit_res = submit_exam(
            payload=SubmitExamPayload(attempt_id=attempt_id, submit_source="manual"),
            current_candidate=candidate,
            db=db
        )

        print("\n--- Asserting submit response statistics ---")
        assert submit_res["total_questions"] == 100, f"Expected total_questions = 100, got {submit_res['total_questions']}"
        assert submit_res["attempted_questions"] == 15, f"Expected attempted_questions = 15, got {submit_res['attempted_questions']}"
        assert submit_res["unanswered_questions"] == 85, f"Expected unanswered_questions = 85, got {submit_res['unanswered_questions']}"
        assert submit_res["correct_answers"] == 5, f"Expected correct_answers = 5, got {submit_res['correct_answers']}"
        assert submit_res["wrong_answers"] == 10, f"Expected wrong_answers = 10, got {submit_res['wrong_answers']}"
        assert submit_res["score"] == 5.0, f"Expected score = 5.0, got {submit_res['score']}"
        assert submit_res["entrance_percentage"] == 5.0, f"Expected entrance_percentage = 5.0, got {submit_res['entrance_percentage']}"
        print("Submit response statistics are correct!")

        print("\n--- Asserting my-results API response statistics ---")
        my_res = get_my_results(current_candidate=candidate, db=db)
        
        assert my_res["total_questions"] == 100, f"Expected total_questions = 100, got {my_res['total_questions']}"
        assert my_res["attempted_questions"] == 15, f"Expected attempted_questions = 15, got {my_res['attempted_questions']}"
        assert my_res["unanswered_questions"] == 85, f"Expected unanswered_questions = 85, got {my_res['unanswered_questions']}"
        assert my_res["correct_answers"] == 5, f"Expected correct_answers = 5, got {my_res['correct_answers']}"
        assert my_res["wrong_answers"] == 10, f"Expected wrong_answers = 10, got {my_res['wrong_answers']}"
        assert my_res["score"] == 5.0, f"Expected score = 5.0, got {my_res['score']}"
        assert my_res["percentage"] == 5.0, f"Expected percentage = 5.0, got {my_res['percentage']}"
        print("My-results API response statistics are correct!")

        print("\n[SUCCESS] verify_result_attempted_count test suite ran successfully without any failures!")

    except AssertionError as ae:
        print(f"\n[TEST FAILED] Assertion Error: {ae}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"\n[TEST FAILED] Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        delete_test_candidate(db, test_mobile)
        db.close()

if __name__ == "__main__":
    main()
