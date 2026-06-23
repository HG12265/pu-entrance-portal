import os
import sys
import argparse
import datetime
from sqlalchemy.orm import Session

# Add project root to python path to access app module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal
from app.config import settings
from app.models import (
    Candidate,
    StudentApplication,
    ExamAttempt,
    StudentAnswer,
    AdmissionConfirmation,
    Exam,
    Question,
    Course,
    CourseCommunitySeat
)

def delete_mock_data(db: Session):
    print("Identifying and deleting existing mock records...")
    # Find mock candidate IDs
    mock_candidates = db.query(Candidate).filter(
        (Candidate.full_name.like("MOCK%")) | (Candidate.mobile_number.like("900000%"))
    ).all()
    mock_cand_ids = [c.id for c in mock_candidates]

    if mock_cand_ids:
        # Delete related StudentAnswers
        deleted_answers = db.query(StudentAnswer).filter(
            StudentAnswer.attempt_id.in_(
                db.query(ExamAttempt.id).filter(ExamAttempt.candidate_id.in_(mock_cand_ids))
            )
        ).delete(synchronize_session=False)
        print(f"- Deleted {deleted_answers} mock student answers")

        # Delete related ExamAttempts
        deleted_attempts = db.query(ExamAttempt).filter(
            ExamAttempt.candidate_id.in_(mock_cand_ids)
        ).delete(synchronize_session=False)
        print(f"- Deleted {deleted_attempts} mock exam attempts")

        # Delete related AdmissionConfirmations
        deleted_confirmations = db.query(AdmissionConfirmation).filter(
            AdmissionConfirmation.candidate_id.in_(mock_cand_ids)
        ).delete(synchronize_session=False)
        print(f"- Deleted {deleted_confirmations} mock confirmations")

        # Delete related StudentApplications
        deleted_apps = db.query(StudentApplication).filter(
            (StudentApplication.candidate_id.in_(mock_cand_ids)) | 
            (StudentApplication.application_number.like("MOCK-%"))
        ).delete(synchronize_session=False)
        print(f"- Deleted {deleted_apps} mock student applications")

        # Delete related Candidates
        deleted_candidates = db.query(Candidate).filter(
            Candidate.id.in_(mock_cand_ids)
        ).delete(synchronize_session=False)
        print(f"- Deleted {deleted_candidates} mock candidates")

        db.commit()
    else:
        print("No mock candidates or applications found to delete.")

def main():
    # 1. Environment Check
    if settings.ENVIRONMENT in ["production", "prod", "staging"]:
        print("CRITICAL ERROR: seed_mock_counselling_data.py cannot run in production or staging environments!", file=sys.stderr)
        sys.exit(1)

    parser = argparse.ArgumentParser(description="Seed mock counselling and candidate application data.")
    parser.add_argument("--delete-existing-mock", action="store_true", help="Delete existing mock records before seeding.")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        # 2. Cleanup if requested
        if args.delete_existing_mock:
            delete_mock_data(db)

        # 3. Fetch/Setup Courses
        mca = db.query(Course).filter(Course.code == "MCA").first()
        if not mca:
            mca = Course(code="MCA", name="Master of Computer Applications", seat_count=5, is_active=True)
            db.add(mca)
            db.commit()
            db.refresh(mca)

        msc_cs = db.query(Course).filter(Course.code == "MSC_CS").first()
        if not msc_cs:
            msc_cs = Course(code="MSC_CS", name="M.Sc Computer Science", seat_count=5, is_active=True)
            db.add(msc_cs)
            db.commit()
            db.refresh(msc_cs)

        # 4. Fetch/Setup Exam
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

        # 5. Dynamically balance questions to exactly 25 per part
        parts_info = {
            "A": ("Quantitative Ability", 1),
            "B": ("Analytical Reasoning", 2),
            "C": ("Logical Reasoning", 3),
            "D": ("Computer Awareness", 4)
        }
        
        q_counter = 1
        for part_code, (part_name, part_order) in parts_info.items():
            existing_cnt = db.query(Question).filter(
                Question.exam_id == exam.id,
                Question.part_code == part_code
            ).count()
            needed = 25 - existing_cnt
            if needed > 0:
                print(f"Part {part_code} has {existing_cnt} questions. Seeding {needed} mock questions...")
                for _ in range(needed):
                    q = Question(
                        exam_id=exam.id,
                        question_text=f"MOCK Question {q_counter:03d} for Part {part_code}",
                        option_a="A",
                        option_b="B",
                        option_c="C",
                        option_d="D",
                        correct_option="A",
                        marks=1.0,
                        part_code=part_code,
                        part_name=part_name,
                        part_order=part_order,
                        source_s_no=q_counter
                    )
                    db.add(q)
                    q_counter += 1
        db.commit()

        # Gather seeded questions for ordering json
        all_q_ids = [q.id for q in db.query(Question).filter(Question.exam_id == exam.id).all()]
        q_by_part = {p: [q.id for q in db.query(Question).filter(Question.exam_id == exam.id, Question.part_code == p).all()] for p in ["A", "B", "C", "D"]}

        # 6. Seed mock candidates with ug_marks=100.0
        # We will seed 6 candidates to MCA and M.Sc CS to test allocations
        mock_candidates_info = [
            # Name, Mobile, Community, MCA score, CS score
            ("MOCK Candidate Alpha", "9000000001", "OC", 85.0, 75.0),
            ("MOCK Candidate Beta", "9000000002", "BC", 80.0, 82.0),
            ("MOCK Candidate Gamma", "9000000003", "MBC", 75.0, 70.0),
            ("MOCK Candidate Delta", "9000000004", "SC", 70.0, 65.0),
            ("MOCK Candidate Epsilon", "9000000005", "ST", 65.0, 60.0),
            ("MOCK Candidate Zeta", "9000000006", "BCM", 60.0, 55.0),
        ]

        print("Seeding mock candidates, applications, and attempts...")
        import json
        for index, (name, mobile, community, mca_score, cs_score) in enumerate(mock_candidates_info):
            # Fetch or create Candidate
            c = db.query(Candidate).filter(Candidate.mobile_number == mobile).first()
            if not c:
                c = Candidate(
                    mobile_number=mobile,
                    full_name=name,
                    community=community,
                    has_verified_details=True,
                    verified_at=datetime.datetime.utcnow()
                )
                db.add(c)
                db.commit()
                db.refresh(c)
            else:
                c.full_name = name
                c.community = community
                c.has_verified_details = True
                db.commit()

            # Seed MCA Application (ug_marks=100.0)
            app_mca = db.query(StudentApplication).filter(
                StudentApplication.candidate_id == c.id,
                StudentApplication.course_id == mca.id
            ).first()
            if not app_mca:
                app_mca = StudentApplication(
                    candidate_id=c.id,
                    course_id=mca.id,
                    application_number=f"MOCK-MCA-{100 + index}",
                    mobile_number=mobile,
                    full_name=name,
                    community=community,
                    ug_marks=100.0,  # Adding ug_marks=100.0 as requested
                    is_active=True
                )
                db.add(app_mca)
            else:
                app_mca.ug_marks = 100.0
                app_mca.is_active = True
                
            # Seed CS Application (ug_marks=100.0)
            app_cs = db.query(StudentApplication).filter(
                StudentApplication.candidate_id == c.id,
                StudentApplication.course_id == msc_cs.id
            ).first()
            if not app_cs:
                app_cs = StudentApplication(
                    candidate_id=c.id,
                    course_id=msc_cs.id,
                    application_number=f"MOCK-CS-{100 + index}",
                    mobile_number=mobile,
                    full_name=name,
                    community=community,
                    ug_marks=100.0,  # Adding ug_marks=100.0 as requested
                    is_active=True
                )
                db.add(app_cs)
            else:
                app_cs.ug_marks = 100.0
                app_cs.is_active = True

            # Setup single ExamAttempt for candidate
            attempt = db.query(ExamAttempt).filter(
                ExamAttempt.candidate_id == c.id,
                ExamAttempt.exam_id == exam.id
            ).first()
            
            # Since the score for MCA is used here, let's use mca_score for their exam score
            # (entrance score is candidate-wide, but UG score and rankings are course-specific)
            order_json = {
                "A": q_by_part["A"],
                "B": q_by_part["B"],
                "C": q_by_part["C"],
                "D": q_by_part["D"],
                "final_order": all_q_ids
            }
            
            if not attempt:
                attempt = ExamAttempt(
                    candidate_id=c.id,
                    exam_id=exam.id,
                    started_at=datetime.datetime.utcnow(),
                    submitted_at=datetime.datetime.utcnow(),
                    total_questions=100,
                    correct_answers=int(mca_score),
                    wrong_answers=100 - int(mca_score),
                    score=float(mca_score),
                    percentage=float(mca_score),
                    is_submitted=True,
                    question_order_json=json.dumps(order_json)
                )
                db.add(attempt)
            else:
                attempt.score = float(mca_score)
                attempt.percentage = float(mca_score)
                attempt.is_submitted = True
                attempt.question_order_json = json.dumps(order_json)

            db.commit()

        print("[SUCCESS] Mock data seeded successfully!")

    except Exception as e:
        db.rollback()
        print(f"[ERROR] Seeding failed: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        db.close()

if __name__ == "__main__":
    main()
