import os
import sys
import argparse
import random
import datetime
from sqlalchemy.orm import Session

# Add project root to python path to access app module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal
from app.config import settings
from app.models import (
    Candidate,
    StudentApplication,
    Course,
    Exam,
    Question,
    ExamAttempt,
    StudentAnswer
)

def main():
    # Safeguard environment check
    if settings.ENVIRONMENT in ["production", "prod", "staging"]:
        print("CRITICAL ERROR: seed_load_test_students.py is disabled in production / staging environments!", file=sys.stderr)
        sys.exit(1)

    parser = argparse.ArgumentParser(description="Seed mock candidates and active exam for load testing.")
    parser.add_argument("--count", type=int, default=250, help="Number of load test students to seed.")
    args = parser.parse_args()

    count = args.count
    db = SessionLocal()

    try:
        print(f"==================================================")
        print(f"Seeding {count} Mock Load Test Students")
        print(f"==================================================")

        # 1. Ensure MCA Course exists
        mca_course = db.query(Course).filter(Course.code == "MCA").first()
        if not mca_course:
            print("Creating MCA course...")
            mca_course = Course(
                code="MCA",
                name="Master of Computer Applications",
                seat_count=30,
                is_active=True
            )
            db.add(mca_course)
            db.commit()
            db.refresh(mca_course)
        else:
            print("MCA course already exists.")

        # 2. Ensure active exam exists
        exam = db.query(Exam).first()
        now = datetime.datetime.utcnow()
        start_utc = now - datetime.timedelta(days=1)
        end_utc = now + datetime.timedelta(days=1)

        if not exam:
            print("Creating active exam...")
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
            print(f"Exam '{exam.name}' exists. Ensuring it is active and has 100 questions.")
            exam.total_questions = 100
            exam.start_date = start_utc
            exam.end_date = end_utc
            exam.start_at_utc = start_utc
            exam.end_at_utc = end_utc
            exam.timezone = "Asia/Kolkata"
            exam.schedule_mode = "FIXED_WINDOW"
            db.commit()

        # 3. Ensure exactly 100 questions (25 per part: A, B, C, D) exist
        parts_data = [
            ("A", "Quantitative Ability", 1),
            ("B", "Analytical Reasoning", 2),
            ("C", "Logical Reasoning", 3),
            ("D", "Computer Awareness", 4),
        ]
        
        # Verify question distribution
        recreate_questions = False
        for part_code, _, _ in parts_data:
            q_cnt = db.query(Question).filter(
                Question.exam_id == exam.id,
                Question.part_code == part_code
            ).count()
            if q_cnt != 25:
                print(f"Part {part_code} has {q_cnt} questions, expected 25. Will recreate all questions.")
                recreate_questions = True
                break

        if db.query(Question).filter(Question.exam_id == exam.id).count() != 100:
            recreate_questions = True

        if recreate_questions:
            print("Re-seeding question bank (exactly 25 questions per part: A, B, C, D)...")
            # Clear old questions for this exam to maintain integrity
            # We must also clean up any student answers pointing to old questions
            db.query(StudentAnswer).delete()
            db.query(ExamAttempt).delete()
            db.query(Question).filter(Question.exam_id == exam.id).delete()
            db.commit()

            q_counter = 1
            for part_code, part_name, part_order in parts_data:
                for i in range(1, 26):
                    q = Question(
                        exam_id=exam.id,
                        question_text=f"Part {part_code} Question {i}: Sample question content.",
                        option_a="Option A",
                        option_b="Option B",
                        option_c="Option C",
                        option_d="Option D",
                        correct_option=random.choice(["A", "B", "C", "D"]),
                        marks=1.0,
                        part_code=part_code,
                        part_name=part_name,
                        part_order=part_order,
                        source_s_no=q_counter
                    )
                    db.add(q)
                    q_counter += 1
            db.commit()
            print("Question bank successfully re-seeded.")
        else:
            print("Question bank already has correct 25-25-25-25 distribution. Skipping question seeding.")

        # 4. Create Mock candidates
        print(f"Upserting {count} MOCKLOAD candidates...")
        random.seed(42)  # For reproducible marks if needed, but the requirement is random 60 to 95

        for i in range(1, count + 1):
            app_num = f"LOAD-MCA-{i:03d}"
            # Mobile starts from 9100000001
            mobile = f"91{i:08d}"
            name = f"Load Test Candidate {i}"
            ug_marks = round(random.uniform(60, 95), 2)

            # Query existing Candidate by mobile number
            candidate = db.query(Candidate).filter(Candidate.mobile_number == mobile).first()
            if candidate:
                # If candidate exists, clean up attempts to allow a fresh exam test run
                db.query(ExamAttempt).filter(ExamAttempt.candidate_id == candidate.id).delete()
                # Update candidate fields
                candidate.full_name = name
                candidate.has_verified_details = True
                candidate.verified_at = datetime.datetime.utcnow()
            else:
                candidate = Candidate(
                    mobile_number=mobile,
                    full_name=name,
                    community="BC",
                    has_verified_details=True,
                    verified_at=datetime.datetime.utcnow()
                )
                db.add(candidate)
            db.commit()
            db.refresh(candidate)

            # Query existing StudentApplication by application number
            app = db.query(StudentApplication).filter(StudentApplication.application_number == app_num).first()
            if app:
                app.candidate_id = candidate.id
                app.course_id = mca_course.id
                app.mobile_number = mobile
                app.full_name = name
                app.ug_marks = ug_marks
                app.is_active = True
            else:
                app = StudentApplication(
                    candidate_id=candidate.id,
                    course_id=mca_course.id,
                    application_number=app_num,
                    mobile_number=mobile,
                    full_name=name,
                    community="BC",
                    ug_marks=ug_marks,
                    is_active=True
                )
                db.add(app)
            db.commit()

        print(f"==================================================")
        print(f"SUCCESS: Seeded {count} MOCKLOAD students with credentials:")
        print(f"Application numbers: LOAD-MCA-001 to LOAD-MCA-{count:03d}")
        print(f"Mobile numbers: 9100000001 to 91{count:08d}")
        print(f"==================================================")

    except Exception as e:
        db.rollback()
        print(f"Error during seeding: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        db.close()

if __name__ == "__main__":
    main()
