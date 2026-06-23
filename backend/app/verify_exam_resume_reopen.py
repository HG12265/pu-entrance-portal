import os
import sys
import datetime
import json
from sqlalchemy.orm import Session
from fastapi import HTTPException

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
    Course,
    Admin,
    ExamAttemptEventLog
)

from app.routers.exams import (
    start_exam,
    save_answer,
    update_current_index,
    log_violation,
    submit_exam,
    SaveAnswerPayload,
    UpdateIndexPayload,
    LogViolationPayload,
    SubmitExamPayload
)

from app.routers.admin import (
    reopen_attempt,
    ReopenPayload
)

def delete_test_candidate(db: Session, mobile: str):
    print(f"Cleaning up test data for mobile {mobile}...")
    candidate = db.query(Candidate).filter(Candidate.mobile_number == mobile).first()
    if candidate:
        # Delete event logs
        db.query(ExamAttemptEventLog).filter(ExamAttemptEventLog.candidate_id == candidate.id).delete()
        
        # Delete answers
        attempts = db.query(ExamAttempt).filter(ExamAttempt.candidate_id == candidate.id).all()
        attempt_ids = [att.id for att in attempts]
        if attempt_ids:
            db.query(StudentAnswer).filter(StudentAnswer.attempt_id.in_(attempt_ids)).delete(synchronize_session=False)
            db.query(ExamAttempt).filter(ExamAttempt.candidate_id == candidate.id).delete(synchronize_session=False)
            
        db.query(StudentApplication).filter(StudentApplication.candidate_id == candidate.id).delete()
        db.query(Candidate).filter(Candidate.id == candidate.id).delete()
        db.commit()
        print("Cleanup completed.")

def main():
    db = SessionLocal()
    test_mobile = "9990000099"
    try:
        # 1. Clean up first
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
            db.commit()

        # 4. Ensure balanced question set (25 per part)
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
                        question_text=f"Verify Q {i} Part {part_code}",
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

        # 5. Create test candidate and application
        candidate = Candidate(
            mobile_number=test_mobile,
            full_name="Resume Test Candidate",
            community="BC",
            has_verified_details=True
        )
        db.add(candidate)
        db.commit()
        db.refresh(candidate)

        app = StudentApplication(
            candidate_id=candidate.id,
            course_id=mca.id,
            application_number="APP-999-MCA",
            mobile_number=test_mobile,
            full_name="Resume Test Candidate",
            community="BC",
            ug_marks=75.0,
            is_active=True
        )
        db.add(app)
        db.commit()

        print("\n--- Step 1: Starting Exam ---")
        start_res = start_exam(current_candidate=candidate, db=db)
        attempt_id = start_res["attempt_id"]
        questions = start_res["questions"]
        print(f"Started attempt: {attempt_id}, number of questions: {len(questions)}")
        assert start_res["status"] == "active", "Attempt status should be active"
        assert len(questions) == 100, f"Expected 100 questions, got {len(questions)}"

        print("\n--- Step 2: Answering 60 Questions ---")
        answered_qids = []
        for idx in range(60):
            q = questions[idx]
            q_id = q["id"]
            answered_qids.append(q_id)
            save_answer(
                payload=SaveAnswerPayload(attempt_id=attempt_id, question_id=q_id, selected_option="B"),
                current_candidate=candidate,
                db=db
            )
        
        # Verify 60 answers in DB
        db_answers_cnt = db.query(StudentAnswer).filter(
            StudentAnswer.attempt_id == attempt_id,
            StudentAnswer.selected_option == "B"
        ).count()
        print(f"Verified {db_answers_cnt} answers saved with 'B'")
        assert db_answers_cnt == 60, f"Expected 60 saved answers, got {db_answers_cnt}"

        print("\n--- Step 3: Resuming Exam (Crash Simulation) ---")
        resume_res = start_exam(current_candidate=candidate, db=db)
        assert resume_res["attempt_id"] == attempt_id, "Should resume same attempt ID"
        assert resume_res["status"] == "active", "Should remain active"
        assert resume_res["answered_count"] == 60, f"Expected 60 answers resumed, got {resume_res['answered_count']}"
        assert resume_res["first_unanswered_index"] == 60, f"Expected first unanswered index at 60, got {resume_res['first_unanswered_index']}"
        
        # Verify question order is preserved
        first_order = [q["id"] for q in questions]
        resume_order = [q["id"] for q in resume_res["questions"]]
        assert first_order == resume_order, "Question order must be preserved exactly on resume"
        print("Question order and answer state successfully verified on crash/resume.")

        print("\n--- Step 4: Submitting the Exam at 60 Answers ---")
        submit_res = submit_exam(
            payload=SubmitExamPayload(attempt_id=attempt_id, submit_source="manual"),
            current_candidate=candidate,
            db=db
        )
        print(f"Submitted. Correct answers: {submit_res['correct_answers']}, Wrong: {submit_res['wrong_answers']}, Score: {submit_res['score']}")
        
        # Verify attempt details are recorded
        attempt = db.query(ExamAttempt).filter(ExamAttempt.id == attempt_id).first()
        assert attempt.is_submitted is True, "Attempt should be marked is_submitted"
        assert attempt.status == "submitted", "Attempt status should be 'submitted'"
        assert attempt.elapsed_seconds_at_submit >= 0, "elapsed_seconds_at_submit should be calculated"
        print(f"Verified: status='{attempt.status}', elapsed_seconds_at_submit={attempt.elapsed_seconds_at_submit}")

        print("\n--- Step 5: Verifying block on started attempt ---")
        try:
            start_exam(current_candidate=candidate, db=db)
            raise AssertionError("start_exam should have raised HTTPException since exam is already submitted")
        except HTTPException as he:
            assert he.status_code == 400, f"Expected status 400, got {he.status_code}"
            assert "submitted" in he.detail, f"Expected submit explanation message, got '{he.detail}'"
            print("Successfully blocked restart of submitted attempt.")

        print("\n--- Step 6: Admin Reopens Attempt ---")
        admin = db.query(Admin).first()
        if not admin:
            # Seed a mock admin if not present
            admin = Admin(username="verify_reopen_admin", password_hash="hash", name="Reopen Admin")
            db.add(admin)
            db.commit()
            db.refresh(admin)

        reopen_attempt(
            attempt_id=attempt_id,
            payload=ReopenPayload(reason="Accidental submission by candidate", time_extension_minutes=15),
            current_admin=admin,
            db=db
        )
        
        db.refresh(attempt)
        assert attempt.status == "admin_reopened", f"Attempt status should be admin_reopened, got {attempt.status}"
        assert attempt.is_submitted is False, "Attempt should not be submitted"
        assert attempt.submitted_at is None, "submitted_at should be cleared"
        assert attempt.score == 0.0, "Score should be cleared to 0.0"
        assert attempt.percentage == 0.0, "Percentage should be cleared to 0.0"
        assert attempt.reopen_count == 1, f"reopen_count should be 1, got {attempt.reopen_count}"
        assert attempt.time_extension_minutes == 15, f"time_extension_minutes should be 15, got {attempt.time_extension_minutes}"
        
        # Verify shifted started_at is within expected range
        now = datetime.datetime.utcnow()
        expected_started_at = now - datetime.timedelta(seconds=attempt.elapsed_seconds_at_submit)
        diff_sec = abs((attempt.started_at - expected_started_at).total_seconds())
        assert diff_sec < 5, f"started_at shift deviation is too high: {diff_sec} seconds"
        print("Reopened successfully. Timer shifted correctly using elapsed_seconds_at_submit.")

        print("\n--- Step 7: Resuming after Reopen ---")
        reopen_resume_res = start_exam(current_candidate=candidate, db=db)
        assert reopen_resume_res["status"] == "admin_reopened", "Should show admin_reopened status"
        assert reopen_resume_res["answered_count"] == 60, f"Answers should be preserved: expected 60, got {reopen_resume_res['answered_count']}"
        assert reopen_resume_res["time_extension_minutes"] == 15, "Should include admin time extension"
        print("Successfully resumed from reopened state, answers preserved.")

        print("\n--- Step 8: Tab Violations Auto-Submit Flow ---")
        # Log 3 violations
        for i in range(1, 4):
            v_res = log_violation(
                payload=LogViolationPayload(attempt_id=attempt_id, violation_message=f"Tab switch violation {i}"),
                current_candidate=candidate,
                db=db
            )
            assert v_res["violation_count"] == i, f"Expected violation count to be {i}, got {v_res['violation_count']}"

        # Get DB count
        db.refresh(attempt)
        assert attempt.violation_count == 3, f"Expected violation_count in DB to be 3, got {attempt.violation_count}"
        print("Logged 3 violations successfully.")

        # Simulate frontend auto-submitting after 3 violations
        submit_res_auto = submit_exam(
            payload=SubmitExamPayload(attempt_id=attempt_id, submit_source="auto_tab_violation", submitted_reason="Exceeded tab switch limit"),
            current_candidate=candidate,
            db=db
        )
        
        db.refresh(attempt)
        assert attempt.status == "auto_submitted", f"Attempt status should be auto_submitted, got {attempt.status}"
        assert attempt.is_submitted is True, "Attempt should be marked submitted"
        assert attempt.submit_source == "auto_tab_violation", "Submit source should be auto_tab_violation"
        print("Verified auto-submission due to tab violations.")

        print("\n--- Step 9: Reopen again after Auto-submit ---")
        reopen_attempt(
            attempt_id=attempt_id,
            payload=ReopenPayload(reason="Second reopen", time_extension_minutes=10),
            current_admin=admin,
            db=db
        )
        db.refresh(attempt)
        assert attempt.status == "admin_reopened", "Should be admin_reopened again"
        assert attempt.reopen_count == 2, f"reopen_count should be 2, got {attempt.reopen_count}"
        assert attempt.time_extension_minutes == 25, f"total extensions should sum to 25, got {attempt.time_extension_minutes}"
        
        # Verify answers are still preserved
        ans_count_final = db.query(StudentAnswer).filter(
            StudentAnswer.attempt_id == attempt_id,
            StudentAnswer.selected_option == "B"
        ).count()
        assert ans_count_final == 60, f"Answers should still be preserved: expected 60, got {ans_count_final}"
        print("Second reopen verified successfully. Answers and timer preserved.")

        print("\n[SUCCESS] verify_exam_resume_reopen test suite ran successfully without any failures!")

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
