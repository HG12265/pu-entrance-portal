import os
import sys
import argparse
from sqlalchemy.orm import Session

# Add project root to python path to access app module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal
from app.config import settings
from app.models import (
    Admin,
    Course,
    CourseCommunitySeat,
    Exam,
    Question,
    ExamAttempt,
    StudentAnswer,
    AdmissionConfirmation,
    StudentApplication,
    Candidate,
    ImportBatch
)

def main():
    # Safeguard environment check
    if settings.ENVIRONMENT in ["production", "prod", "staging"]:
        print("CRITICAL ERROR: cleanup_operational_data.py is disabled in production / staging environments!", file=sys.stderr)
        sys.exit(1)
        
    parser = argparse.ArgumentParser(description="Clean operational candidate, application, and attempt data while preserving configuration.")
    parser.add_argument("--confirm", action="store_true", help="Confirm deletion of operational data.")
    args = parser.parse_args()
    
    db = SessionLocal()
    try:
        # Get count of rows from each table
        tables = [
            ("student_answers", StudentAnswer),
            ("exam_attempts", ExamAttempt),
            ("admission_confirmations", AdmissionConfirmation),
            ("student_applications", StudentApplication),
            ("candidates", Candidate),
            ("import_batches", ImportBatch),
            ("questions", Question),
            ("admins", Admin),
            ("courses", Course),
            ("course_community_seats", CourseCommunitySeat),
            ("exams", Exam),
        ]
        
        print("==================================================")
        print("Operational Data Cleanup Utility (Local Development)")
        print("==================================================")
        
        # Dry-run or warning print
        print("Current database operational & configuration row counts:")
        for name, model in tables:
            cnt = db.query(model).count()
            print(f"- {name:25s} : {cnt} rows")
            
        print("--------------------------------------------------")
        
        if not args.confirm:
            print("WARNING: This is a DRY RUN only.")
            print("To delete operational tables only (student answers, exam attempts, confirmations,")
            print("applications, candidates, import batches, and questions), run with the --confirm flag.")
            print("Configuration data (admins, courses, course community seats, exams) will be preserved.")
            print("==================================================")
            return
            
        print("WARNING: YOU ARE PERMANENTLY DELETING ALL OPERATIONAL DATA!")
        print("This deletes student answers, attempts, registrations, confirmations, applications, and questions.")
        print("It preserves courses, admin profiles, exam configuration settings, and seat matrices.")
        print("Executing cleanup...")
        
        # Delete in safe dependency order:
        # 1. student_answers
        deleted_answers = db.query(StudentAnswer).delete(synchronize_session=False)
        print(f"- Deleted {deleted_answers} rows from student_answers")
        
        # 2. exam_attempts
        deleted_attempts = db.query(ExamAttempt).delete(synchronize_session=False)
        print(f"- Deleted {deleted_attempts} rows from exam_attempts")
        
        # 3. admission_confirmations
        deleted_confirmations = db.query(AdmissionConfirmation).delete(synchronize_session=False)
        print(f"- Deleted {deleted_confirmations} rows from admission_confirmations")
        
        # 4. student_applications
        deleted_apps = db.query(StudentApplication).delete(synchronize_session=False)
        print(f"- Deleted {deleted_apps} rows from student_applications")
        
        # 5. candidates
        deleted_candidates = db.query(Candidate).delete(synchronize_session=False)
        print(f"- Deleted {deleted_candidates} rows from candidates")
        
        # 6. import_batches
        deleted_batches = db.query(ImportBatch).delete(synchronize_session=False)
        print(f"- Deleted {deleted_batches} rows from import_batches")
        
        # 7. questions
        deleted_questions = db.query(Question).delete(synchronize_session=False)
        print(f"- Deleted {deleted_questions} rows from questions")
        
        db.commit()
        print("--------------------------------------------------")
        print("[SUCCESS] Operational data cleanup finished successfully!")
        print("--------------------------------------------------")
        
        # Post-cleanup verifications:
        print("Verifying database state after cleanup...")
        admins_cnt = db.query(Admin).count()
        courses_cnt = db.query(Course).count()
        seats_cnt = db.query(CourseCommunitySeat).count()
        exams_cnt = db.query(Exam).count()
        cand_cnt = db.query(Candidate).count()
        apps_cnt = db.query(StudentApplication).count()
        attempts_cnt = db.query(ExamAttempt).count()
        qns_cnt = db.query(Question).count()
        
        print(f"- admins count: {admins_cnt} (Expected > 0)")
        print(f"- courses count: {courses_cnt} (Expected = 3)")
        print(f"- course_community_seats count: {seats_cnt} (Expected = 21)")
        print(f"- exams count: {exams_cnt} (Expected >= 1)")
        print(f"- candidates count: {cand_cnt} (Expected = 0)")
        print(f"- student_applications count: {apps_cnt} (Expected = 0)")
        print(f"- exam_attempts count: {attempts_cnt} (Expected = 0)")
        print(f"- questions count: {qns_cnt} (Expected = 0)")
        
        assert admins_cnt > 0, "Verification Failed: Admins count should be > 0"
        assert courses_cnt == 3, f"Verification Failed: Courses count should be 3, got {courses_cnt}"
        assert seats_cnt == 21, f"Verification Failed: CourseCommunitySeat count should be 21, got {seats_cnt}"
        assert exams_cnt >= 1, "Verification Failed: Exams count should be >= 1"
        assert cand_cnt == 0, "Verification Failed: Candidates count should be 0"
        assert apps_cnt == 0, "Verification Failed: StudentApplications count should be 0"
        assert attempts_cnt == 0, "Verification Failed: ExamAttempts count should be 0"
        assert qns_cnt == 0, "Verification Failed: Questions count should be 0"
        
        print("[SUCCESS] All post-cleanup database verifications passed successfully!")
        print("==================================================")
        
    except AssertionError as a_err:
        print(f"\n[ERROR] VERIFICATION FAILED: {a_err}", file=sys.stderr)
        sys.exit(1)
    except Exception as err:
        db.rollback()
        print(f"\n[ERROR] Exception during cleanup: {err}", file=sys.stderr)
        sys.exit(1)
    finally:
        db.close()

if __name__ == "__main__":
    main()
