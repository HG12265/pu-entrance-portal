import os
import sys
import datetime
from sqlalchemy.orm import Session
from fastapi import HTTPException
from unittest.mock import patch

# Add project root to python path to access app module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal
from app.models import (
    Candidate,
    StudentApplication,
    ExamAttempt,
    Exam,
    Course,
    Admin,
    Question,
    StudentAnswer
)
from app.routers.exams import start_exam, get_active_exam
from app.routers.admin import reopen_attempt, ReopenPayload
from app.utils.timezone import (
    IST,
    now_utc,
    to_ist,
    parse_admin_ist_datetime,
    format_ist_for_response
)

def delete_test_candidate(db: Session, mobile: str):
    print(f"Cleaning up test candidate for mobile {mobile}...")
    candidate = db.query(Candidate).filter(Candidate.mobile_number == mobile).first()
    if candidate:
        db.query(StudentAnswer).filter(StudentAnswer.attempt_id.in_(
            db.query(ExamAttempt.id).filter(ExamAttempt.candidate_id == candidate.id)
        )).delete(synchronize_session=False)
        db.query(ExamAttempt).filter(ExamAttempt.candidate_id == candidate.id).delete(synchronize_session=False)
        db.query(StudentApplication).filter(StudentApplication.candidate_id == candidate.id).delete()
        db.query(Candidate).filter(Candidate.id == candidate.id).delete()
        db.commit()

def main():
    db = SessionLocal()
    test_mobile = "8881112233"
    
    try:
        # Cleanup test data
        delete_test_candidate(db, test_mobile)
        
        # 1. Assert 2026-06-29 10:30 IST converts to 2026-06-29 05:00 UTC
        print("Checking timezone conversions...")
        utc_dt = parse_admin_ist_datetime("2026-06-29", "10:30")
        assert utc_dt.year == 2026
        assert utc_dt.month == 6
        assert utc_dt.day == 29
        assert utc_dt.hour == 5
        assert utc_dt.minute == 0
        assert utc_dt.tzinfo == datetime.timezone.utc
        print("Timezone conversion verified: 2026-06-29 10:30 IST = 2026-06-29 05:00 UTC.")
        
        # Configure Exam start and end times in DB
        exam = db.query(Exam).first()
        if not exam:
            exam = Exam(
                name="Periyar University Entrance Examination 2026",
                total_questions=100,
                duration_minutes=120,
                start_date=datetime.datetime(2026, 6, 29, 5, 0, 0),
                end_date=datetime.datetime(2026, 6, 29, 7, 0, 0),
                start_at_utc=datetime.datetime(2026, 6, 29, 5, 0, 0),
                end_at_utc=datetime.datetime(2026, 6, 29, 7, 0, 0),
                timezone="Asia/Kolkata",
                schedule_mode="FIXED_WINDOW",
                result_visibility=True
            )
            db.add(exam)
            db.commit()
            db.refresh(exam)
        else:
            exam.total_questions = 100
            exam.duration_minutes = 120
            exam.start_at_utc = datetime.datetime(2026, 6, 29, 5, 0, 0)
            exam.end_at_utc = datetime.datetime(2026, 6, 29, 7, 0, 0)
            exam.timezone = "Asia/Kolkata"
            exam.schedule_mode = "FIXED_WINDOW"
            db.commit()
            
        # Ensure 25 questions per part exist
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

        # Create test candidate and application
        candidate = Candidate(
            mobile_number=test_mobile,
            full_name="IST Schedule Test Candidate",
            community="BC",
            has_verified_details=True
        )
        db.add(candidate)
        db.commit()
        db.refresh(candidate)

        mca = db.query(Course).filter(Course.code == "MCA").first()
        if not mca:
            mca = Course(code="MCA", name="Master of Computer Applications", seat_count=30, is_active=True)
            db.add(mca)
            db.commit()
            db.refresh(mca)

        app = StudentApplication(
            candidate_id=candidate.id,
            course_id=mca.id,
            application_number="APP-888-MCA",
            mobile_number=test_mobile,
            full_name="IST Schedule Test Candidate",
            community="BC",
            ug_marks=75.0,
            is_active=True
        )
        db.add(app)
        db.commit()

        # 2. Mock 10:00 IST -> /start returns exam_not_started
        print("\n--- Test Case: 10:00 AM IST (Before exam start) ---")
        mock_now_1000 = datetime.datetime(2026, 6, 29, 4, 30, 0, tzinfo=datetime.timezone.utc) # 10:00 AM IST
        with patch("app.utils.timezone.now_utc", return_value=mock_now_1000):
            # Assert active settings endpoint response
            active_info = get_active_exam(db=db)
            assert active_info["is_exam_configured"] is True
            assert active_info["is_login_allowed"] is True
            assert active_info["is_start_allowed"] is False
            assert active_info["exam_not_started"] is True
            assert active_info["seconds_until_start"] == 1800
            print("Active exam info before start verified successfully.")
            
            try:
                start_exam(current_candidate=candidate, db=db)
                raise AssertionError("Expected HTTPException for exam_not_started")
            except HTTPException as he:
                assert he.status_code == 403, f"Expected 403, got {he.status_code}"
                assert he.detail["exam_not_started"] is True, "Expected exam_not_started = True"
                assert he.detail["seconds_until_start"] == 1800, f"Expected 1800 seconds, got {he.detail['seconds_until_start']}"
                print("exam_not_started returned correctly with countdown.")

        # 3. Mock 10:30 IST -> /start allows start
        print("\n--- Test Case: 10:30 AM IST (Exact start time) ---")
        mock_now_1030 = datetime.datetime(2026, 6, 29, 5, 0, 0, tzinfo=datetime.timezone.utc) # 10:30 AM IST
        with patch("app.utils.timezone.now_utc", return_value=mock_now_1030):
            # Assert active settings endpoint response
            active_info = get_active_exam(db=db)
            assert active_info["is_exam_configured"] is True
            assert active_info["is_login_allowed"] is True
            assert active_info["is_start_allowed"] is True
            assert active_info["exam_not_started"] is False
            assert active_info["seconds_until_start"] == 0
            print("Active exam info at start time verified successfully.")
            
            res = start_exam(current_candidate=candidate, db=db)
            assert res["status"] == "active", "Attempt status should be active"
            assert res["remaining_seconds"] == 7200, f"Expected 7200 seconds remaining, got {res['remaining_seconds']}"
            print("Exam start success at 10:30 AM IST with full 120 minutes.")

        # Clean up attempt for the late starter test case
        delete_test_candidate(db, test_mobile)
        
        candidate = Candidate(
            mobile_number=test_mobile,
            full_name="IST Schedule Test Candidate",
            community="BC",
            has_verified_details=True
        )
        db.add(candidate)
        db.commit()
        db.refresh(candidate)
        
        app = StudentApplication(
            candidate_id=candidate.id,
            course_id=mca.id,
            application_number="APP-888-MCA",
            mobile_number=test_mobile,
            full_name="IST Schedule Test Candidate",
            community="BC",
            ug_marks=75.0,
            is_active=True
        )
        db.add(app)
        db.commit()

        # 4. Mock 10:45 IST -> /start allows, remaining_seconds = 105 minutes (late starter)
        print("\n--- Test Case: 10:45 AM IST (Late start) ---")
        mock_now_1045 = datetime.datetime(2026, 6, 29, 5, 15, 0, tzinfo=datetime.timezone.utc) # 10:45 AM IST
        with patch("app.utils.timezone.now_utc", return_value=mock_now_1045):
            res_late = start_exam(current_candidate=candidate, db=db)
            assert res_late["status"] == "active", "Attempt status should be active"
            # Late starters in FIXED_WINDOW mode only get remaining window duration
            # Exam ends at 12:30 PM (07:00 UTC). Current is 10:45 AM (05:15 UTC).
            # Remaining = 12:30 - 10:45 = 105 minutes = 6300 seconds.
            assert res_late["remaining_seconds"] == 6300, f"Expected 6300 seconds remaining, got {res_late['remaining_seconds']}"
            print("Exam start success at 10:45 AM IST with remaining 105 minutes (capping verified).")

        # 5. Mock 12:31 IST -> /start returns exam_closed and auto-submits active attempt
        print("\n--- Test Case: 12:31 PM IST (After exam window, should close & auto-submit) ---")
        mock_now_1231 = datetime.datetime(2026, 6, 29, 7, 1, 0, tzinfo=datetime.timezone.utc) # 12:31 PM IST
        with patch("app.utils.timezone.now_utc", return_value=mock_now_1231):
            # Assert active settings endpoint response
            active_info = get_active_exam(db=db)
            assert active_info["is_exam_configured"] is True
            assert active_info["is_login_allowed"] is True
            assert active_info["is_start_allowed"] is False
            assert active_info["exam_not_started"] is False
            print("Active exam info after window verified successfully.")
            
            try:
                start_exam(current_candidate=candidate, db=db)
                raise AssertionError("Expected HTTPException for exam_closed")
            except HTTPException as he:
                assert he.status_code == 403, f"Expected 403, got {he.status_code}"
                assert he.detail["exam_closed"] is True, "Expected exam_closed = True"
                print("Exam closed 403 raised correctly.")
                
            # Verify attempt was auto-submitted
            attempt = db.query(ExamAttempt).filter(ExamAttempt.candidate_id == candidate.id).first()
            assert attempt.status == "auto_submitted", f"Expected auto_submitted, got {attempt.status}"
            assert attempt.is_submitted is True, "Attempt should be marked submitted"
            assert attempt.submit_source == "time_over", f"Expected time_over, got {attempt.submit_source}"
            print("Active attempt was successfully auto-submitted as 'time_over'.")

        # 6. Admin reopen attempt after 12:30 without extension should fail
        print("\n--- Test Case: Reopen after close without extension (Should fail) ---")
        admin = db.query(Admin).first()
        if not admin:
            admin = Admin(username="ist_verify_admin", password_hash="hash", name="IST Verify Admin")
            db.add(admin)
            db.commit()
            db.refresh(admin)

        with patch("app.utils.timezone.now_utc", return_value=mock_now_1231):
            try:
                reopen_attempt(
                    attempt_id=attempt.id,
                    payload=ReopenPayload(reason="Testing reopen block", time_extension_minutes=0),
                    current_admin=admin,
                    db=db
                )
                raise AssertionError("Expected HTTPException for reopen block")
            except HTTPException as he:
                assert he.status_code == 400, f"Expected 400, got {he.status_code}"
                assert "extension" in he.detail, f"Expected error to prompt for extension, got: {he.detail}"
                print("Reopening block without extension verified successfully.")

            # Reopening WITH extension should work
            print("\n--- Test Case: Reopen after close WITH extension (Should succeed) ---")
            reopen_attempt(
                attempt_id=attempt.id,
                payload=ReopenPayload(reason="Testing reopen success", time_extension_minutes=15),
                current_admin=admin,
                db=db
            )
            db.refresh(attempt)
            assert attempt.status == "admin_reopened"
            assert attempt.time_extension_minutes == 15
            print("Reopen with extension succeeded.")

        print("\n[SUCCESS] verify_exam_schedule_ist test suite ran successfully without any failures!")

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
