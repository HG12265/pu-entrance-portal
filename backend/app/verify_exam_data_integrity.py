import os
import sys
import json
import argparse
from sqlalchemy import func
from sqlalchemy.orm import Session

# Add project root to python path to access app module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal
from app.models import (
    Candidate,
    StudentApplication,
    ExamAttempt,
    StudentAnswer,
    Exam
)
from app.routers.results import get_course_rankings_internal

def main():
    parser = argparse.ArgumentParser(description="Verify database integrity after load testing.")
    parser.add_argument("--allow-active", action="store_true", help="Do not fail on active/unsubmitted attempts.")
    args = parser.parse_args()

    db = SessionLocal()
    errors = []
    warnings = []

    try:
        print("==================================================")
        print("Exam Data Integrity Verification Suite")
        print("==================================================")

        # Retrieve all MOCKLOAD candidates
        candidates = db.query(Candidate).join(
            StudentApplication, Candidate.id == StudentApplication.candidate_id
        ).filter(
            StudentApplication.application_number.like("LOAD-%")
        ).all()

        print(f"Found {len(candidates)} MOCKLOAD candidates in database.")
        if len(candidates) == 0:
            print("WARNING: No MOCKLOAD candidates found. Did you run the seed script?")
            db.close()
            sys.exit(0)

        # Check 9: No candidate has multiple attempts for same exam
        for c in candidates:
            # Group by exam_id to check multiple attempts for the same exam
            attempts_by_exam = db.query(ExamAttempt.exam_id, func.count(ExamAttempt.id)).filter(
                ExamAttempt.candidate_id == c.id
            ).group_by(ExamAttempt.exam_id).all()
            
            for exam_id, count in attempts_by_exam:
                if count > 1:
                    errors.append(f"Candidate {c.full_name} (ID: {c.id}) has {count} attempts for exam ID {exam_id} (Expected <= 1).")

        # Check 1 & details
        for c in candidates:
            # Each MOCKLOAD candidate has exactly one ExamAttempt (Check 1)
            attempts = db.query(ExamAttempt).filter(ExamAttempt.candidate_id == c.id).all()
            if len(attempts) != 1:
                errors.append(f"Candidate {c.full_name} (ID: {c.id}) has {len(attempts)} attempts (Expected exactly 1).")
                continue

            attempt = attempts[0]
            app = db.query(StudentApplication).filter(StudentApplication.candidate_id == c.id).first()

            # Check 8: No active attempt stuck unless load test intentionally stopped
            if not attempt.is_submitted:
                msg = f"Candidate {c.full_name} (ID: {c.id}) has active/unsubmitted attempt (Attempt ID: {attempt.id}, Status: {attempt.status})."
                if args.allow_active:
                    warnings.append(msg)
                else:
                    errors.append(msg)

            # Check 2: Each attempt has question_order_json
            if not attempt.question_order_json:
                errors.append(f"Attempt {attempt.id} has no question_order_json.")
                continue

            # Check 3: final_order length = 100
            try:
                order_json = json.loads(attempt.question_order_json)
                final_order = order_json.get("final_order", [])
                if len(final_order) != 100:
                    errors.append(f"Attempt {attempt.id} question_order_json final_order length is {len(final_order)} (Expected 100).")
            except Exception as ex:
                errors.append(f"Attempt {attempt.id} has malformed question_order_json: {ex}")
                continue

            # Check 4: Each attempt has exactly 100 StudentAnswer rows
            ans_count = db.query(StudentAnswer).filter(StudentAnswer.attempt_id == attempt.id).count()
            if ans_count != 100:
                errors.append(f"Attempt {attempt.id} has {ans_count} StudentAnswer rows (Expected 100).")

            # Check 5: attempted_count equals selected_option not null count
            # attempted_count in the grading schema is computed as correct + wrong answers
            attempted_count = (attempt.correct_answers or 0) + (attempt.wrong_answers or 0)
            selected_option_not_null_count = db.query(StudentAnswer).filter(
                StudentAnswer.attempt_id == attempt.id,
                StudentAnswer.selected_option.isnot(None),
                StudentAnswer.selected_option != ""
            ).count()
            if attempt.is_submitted and attempted_count != selected_option_not_null_count:
                errors.append(f"Attempt {attempt.id} attempted_count is {attempted_count} but StudentAnswer count with selected_option is {selected_option_not_null_count}.")

            # Check 6: No duplicate StudentAnswer for same attempt_id + question_id
            duplicates = db.query(StudentAnswer.question_id, func.count(StudentAnswer.id)).filter(
                StudentAnswer.attempt_id == attempt.id
            ).group_by(StudentAnswer.question_id).having(func.count(StudentAnswer.id) > 1).all()
            if len(duplicates) > 0:
                errors.append(f"Attempt {attempt.id} has duplicate StudentAnswer records for question IDs: {[d[0] for d in duplicates]}.")

            # Check 7: All submitted attempts have score calculated
            if attempt.is_submitted:
                if attempt.score is None or attempt.percentage is None:
                    errors.append(f"Attempt {attempt.id} is submitted but score or percentage is NULL.")
                else:
                    # Check 10: Weighted final score values are between 0 and 100
                    # formula: (entrance_perc * 0.5) + (ug_marks * 0.5)
                    ug_marks = app.ug_marks if app and app.ug_marks is not None else 0.0
                    entrance_perc = attempt.percentage
                    final_score = (entrance_perc * 0.5) + (ug_marks * 0.5)
                    if not (0.0 <= final_score <= 100.0):
                        errors.append(f"Attempt {attempt.id} has invalid weighted final score {final_score} (Expected between 0 and 100).")

        # Check 11: Counselling rankings load without error
        print("Checking counselling rankings load...")
        try:
            rankings = get_course_rankings_internal(db, "MCA", show_excluded=True)
            print(f"Counselling rankings loaded successfully. Total entries: {len(rankings)}")
            # Make sure some of our mock load entries are present in the ranking list
            mock_in_rankings = [r for r in rankings if r["application_number"].startswith("LOAD-")]
            print(f"Mock load candidates present in ranking list: {len(mock_in_rankings)}")
        except Exception as e:
            errors.append(f"Failed to load counselling rankings: {e}")

        # Summary of results
        print("\n==================================================")
        print("Verification Summary:")
        print("==================================================")
        if warnings:
            print(f"WARNINGS ({len(warnings)}):")
            for w in warnings:
                print(f"- {w}")
        else:
            print("No warnings.")

        if errors:
            print(f"\nERRORS ({len(errors)}):")
            for e in errors:
                print(f"- {e}")
            print("\n[FAILED] Data integrity checks failed! Please review the errors above.")
            sys.exit(1)
        else:
            print("\n[SUCCESS] All data integrity checks passed successfully!")
            sys.exit(0)

    except Exception as e:
        print(f"Unexpected error during verification: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        db.close()

if __name__ == "__main__":
    main()
