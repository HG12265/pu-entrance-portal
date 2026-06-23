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
    AdmissionConfirmation,
    Exam,
    Question,
    Course,
    CourseCommunitySeat
)
from app.routers.results import get_course_rankings_internal, export_results_excel

def delete_test_candidates(db: Session, mobiles: list):
    print("Deleting old test candidate profiles...")
    test_candidates = db.query(Candidate).filter(Candidate.mobile_number.in_(mobiles)).all()
    test_cand_ids = [c.id for c in test_candidates]

    if test_cand_ids:
        # Delete related StudentAnswers
        db.query(StudentAnswer).filter(
            StudentAnswer.attempt_id.in_(
                db.query(ExamAttempt.id).filter(ExamAttempt.candidate_id.in_(test_cand_ids))
            )
        ).delete(synchronize_session=False)

        # Delete related ExamAttempts
        db.query(ExamAttempt).filter(ExamAttempt.candidate_id.in_(test_cand_ids)).delete(synchronize_session=False)

        # Delete related AdmissionConfirmations
        db.query(AdmissionConfirmation).filter(AdmissionConfirmation.candidate_id.in_(test_cand_ids)).delete(synchronize_session=False)

        # Delete related StudentApplications
        db.query(StudentApplication).filter(StudentApplication.candidate_id.in_(test_cand_ids)).delete(synchronize_session=False)

        # Delete related Candidates
        db.query(Candidate).filter(Candidate.id.in_(test_cand_ids)).delete(synchronize_session=False)

        db.commit()
        print(f"Cleared {len(test_cand_ids)} test candidates successfully.")

def main():
    db = SessionLocal()
    test_mobiles = ["9990000001", "9990000002", "9990000003"]
    try:
        # 1. Clean up existing test data
        delete_test_candidates(db, test_mobiles)

        # 2. Fetch or create Course MCA
        mca = db.query(Course).filter(Course.code == "MCA").first()
        if not mca:
            mca = Course(code="MCA", name="Master of Computer Applications", seat_count=10, is_active=True)
            db.add(mca)
            db.commit()
            db.refresh(mca)

        # 3. Fetch or create Exam
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

        # 4. Dynamically seed questions if less than 100 to ensure we can resolve total_marks
        q_count = db.query(Question).filter(Question.exam_id == exam.id).count()
        parts_info = {
            "A": ("Quantitative Ability", 1),
            "B": ("Analytical Reasoning", 2),
            "C": ("Logical Reasoning", 3),
            "D": ("Computer Awareness", 4)
        }
        if q_count < 100:
            print(f"Exam only has {q_count} questions. Balancing to exactly 25 questions per part...")
            q_counter = 1
            for part_code, (part_name, part_order) in parts_info.items():
                existing_cnt = db.query(Question).filter(
                    Question.exam_id == exam.id,
                    Question.part_code == part_code
                ).count()
                needed = 25 - existing_cnt
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

        # Gather questions list to populate question_order_json
        questions = db.query(Question).filter(Question.exam_id == exam.id).all()
        q_ids = [q.id for q in questions]

        # 5. Create candidates A, B, and C
        print("Creating Candidate A, B, and C records...")
        
        # Candidate A: Entrance 80, UG 70 -> Final 75
        c_a = Candidate(mobile_number="9990000001", full_name="TEST Candidate A", community="OC", has_verified_details=True)
        db.add(c_a)
        db.commit()
        db.refresh(c_a)

        app_a = StudentApplication(
            candidate_id=c_a.id,
            course_id=mca.id,
            application_number="TEST-MCA-A",
            mobile_number="9990000001",
            full_name="TEST Candidate A",
            community="OC",
            ug_marks=70.0,
            is_active=True
        )
        db.add(app_a)

        # Candidate B: Entrance 90, UG 50 -> Final 70
        c_b = Candidate(mobile_number="9990000002", full_name="TEST Candidate B", community="OC", has_verified_details=True)
        db.add(c_b)
        db.commit()
        db.refresh(c_b)

        app_b = StudentApplication(
            candidate_id=c_b.id,
            course_id=mca.id,
            application_number="TEST-MCA-B",
            mobile_number="9990000002",
            full_name="TEST Candidate B",
            community="OC",
            ug_marks=50.0,
            is_active=True
        )
        db.add(app_b)

        # Candidate C: Entrance 60, UG 90 -> Final 75
        c_c = Candidate(mobile_number="9990000003", full_name="TEST Candidate C", community="OC", has_verified_details=True)
        db.add(c_c)
        db.commit()
        db.refresh(c_c)

        app_c = StudentApplication(
            candidate_id=c_c.id,
            course_id=mca.id,
            application_number="TEST-MCA-C",
            mobile_number="9990000003",
            full_name="TEST Candidate C",
            community="OC",
            ug_marks=90.0,
            is_active=True
        )
        db.add(app_c)

        db.commit()

        # Seed attempt details with correct question order referencing seeded questions
        order_json = {
            "A": [q.id for q in questions if q.part_code == "A"],
            "B": [q.id for q in questions if q.part_code == "B"],
            "C": [q.id for q in questions if q.part_code == "C"],
            "D": [q.id for q in questions if q.part_code == "D"],
            "final_order": q_ids
        }
        order_str = json.dumps(order_json)

        # Assign attempts
        # Attempt A: score 80
        att_a = ExamAttempt(
            candidate_id=c_a.id,
            exam_id=exam.id,
            total_questions=100,
            correct_answers=80,
            score=80.0,
            percentage=80.0,
            is_submitted=True,
            submitted_at=datetime.datetime.utcnow() - datetime.timedelta(minutes=10),
            question_order_json=order_str
        )
        db.add(att_a)

        # Attempt B: score 90
        att_b = ExamAttempt(
            candidate_id=c_b.id,
            exam_id=exam.id,
            total_questions=100,
            correct_answers=90,
            score=90.0,
            percentage=90.0,
            is_submitted=True,
            submitted_at=datetime.datetime.utcnow() - datetime.timedelta(minutes=8),
            question_order_json=order_str
        )
        db.add(att_b)

        # Attempt C: score 60
        att_c = ExamAttempt(
            candidate_id=c_c.id,
            exam_id=exam.id,
            total_questions=100,
            correct_answers=60,
            score=60.0,
            percentage=60.0,
            is_submitted=True,
            submitted_at=datetime.datetime.utcnow() - datetime.timedelta(minutes=6),
            question_order_json=order_str
        )
        db.add(att_c)

        db.commit()

        # 6. Fetch MCA Rankings
        print("Calculating MCA Course Rankings...")
        rankings = get_course_rankings_internal(db, "MCA", show_excluded=True)

        # Filter rankings to only include our test candidates A, B, and C
        test_rankings = [r for r in rankings if r["candidate_id"] in [c_a.id, c_b.id, c_c.id]]
        
        # We expect exactly 3 entries
        assert len(test_rankings) == 3, f"Expected 3 test candidate ranking entries, got {len(test_rankings)}"

        # Assert correct values
        entry_a = next(r for r in test_rankings if r["candidate_id"] == c_a.id)
        entry_b = next(r for r in test_rankings if r["candidate_id"] == c_b.id)
        entry_c = next(r for r in test_rankings if r["candidate_id"] == c_c.id)

        print("\nCandidate A Details:")
        print(f"- Entrance score: {entry_a['entrance_score']} / {entry_a['entrance_total_marks']} ({entry_a['entrance_percentage']}%)")
        print(f"- UG percentage: {entry_a['ug_percentage']}%")
        print(f"- Weighted component - Entrance: {entry_a['entrance_weighted_score']} | UG: {entry_a['ug_weighted_score']}")
        print(f"- Final Score: {entry_a['final_score']}")
        print(f"- Breakdown text: {entry_a['final_score_breakdown_text']}")

        print("\nCandidate B Details:")
        print(f"- Final Score: {entry_b['final_score']}")

        print("\nCandidate C Details:")
        print(f"- Final Score: {entry_c['final_score']}")

        # Assert scores match math:
        # A: 80 * 0.50 + 70 * 0.50 = 40.0 + 35.0 = 75.0
        assert entry_a["final_score"] == 75.0, f"Expected Final Score 75.0 for A, got {entry_a['final_score']}"
        # B: 90 * 0.50 + 50 * 0.50 = 45.0 + 25.0 = 70.0
        assert entry_b["final_score"] == 70.0, f"Expected Final Score 70.0 for B, got {entry_b['final_score']}"
        # C: 60 * 0.50 + 90 * 0.50 = 30.0 + 45.0 = 75.0
        assert entry_c["final_score"] == 75.0, f"Expected Final Score 75.0 for C, got {entry_c['final_score']}"

        # Assert order of candidates:
        # A (Final 75.0, Entrance 80%) should sort above C (Final 75.0, Entrance 60%)
        # B (Final 70.0) should sort at the bottom
        print("\nAsserting sorting order...")
        print(f"1. {test_rankings[0]['student_name']} (Final Score: {test_rankings[0]['final_score']}, Entrance %: {test_rankings[0]['entrance_percentage']})")
        print(f"2. {test_rankings[1]['student_name']} (Final Score: {test_rankings[1]['final_score']}, Entrance %: {test_rankings[1]['entrance_percentage']})")
        print(f"3. {test_rankings[2]['student_name']} (Final Score: {test_rankings[2]['final_score']}, Entrance %: {test_rankings[2]['entrance_percentage']})")

        assert test_rankings[0]["candidate_id"] == c_a.id, "Candidate A should be Rank 1"
        assert test_rankings[1]["candidate_id"] == c_c.id, "Candidate C should be Rank 2"
        assert test_rankings[2]["candidate_id"] == c_b.id, "Candidate B should be Rank 3"

        print("\n[SUCCESS] verify_weighted_final_score tests passed successfully!")

    except AssertionError as ae:
        print(f"\n[TEST FAILED] Assertion Error: {ae}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"\n[TEST FAILED] Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        delete_test_candidates(db, test_mobiles)
        db.close()

if __name__ == "__main__":
    main()
