import sys
import os

# Add the parent directory to sys.path so we can import app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal
from app.models import Candidate, StudentApplication, Question, ExamAttempt, StudentAnswer, Exam, Course
from app.routers.exams import start_exam

def verify_shuffling():
    db = SessionLocal()
    try:
        print("[TEST] Clearing existing operational data...")
        # Clean up existing attempts and questions to avoid interference
        db.query(StudentAnswer).delete()
        db.query(ExamAttempt).delete()
        db.query(Question).delete()
        db.commit()

        # Fetch or create the main exam
        exam = db.query(Exam).first()
        if not exam:
            import datetime
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
            import datetime
            exam.total_questions = 100
            exam.duration_minutes = 120
            exam.start_date = datetime.datetime.utcnow() - datetime.timedelta(days=1)
            exam.end_date = datetime.datetime.utcnow() + datetime.timedelta(days=1)
            db.commit()

        # Seed courses if missing
        mca_course = db.query(Course).filter(Course.code == "MCA").first()
        if not mca_course:
            mca_course = Course(code="MCA", name="Master of Computer Applications", seat_count=30, is_active=True)
            db.add(mca_course)
            db.commit()

        print("[TEST] Seeding exactly 25 questions per part...")
        parts_data = [
            ("A", "Quantitative Ability", 1),
            ("B", "Analytical Reasoning", 2),
            ("C", "Logical Reasoning", 3),
            ("D", "Computer Awareness", 4),
        ]
        
        seeded_questions = []
        q_counter = 1
        for part_code, part_name, part_order in parts_data:
            for i in range(1, 26):
                q = Question(
                    exam_id=exam.id,
                    question_text=f"Part {part_code} Question {i}",
                    option_a="Option A text",
                    option_b="Option B text",
                    option_c="Option C text",
                    option_d="Option D text",
                    correct_option="A",
                    marks=1.0,
                    part_code=part_code,
                    part_name=part_name,
                    part_order=part_order,
                    source_s_no=q_counter
                )
                db.add(q)
                seeded_questions.append(q)
                q_counter += 1
        db.commit()
        print(f"[TEST] Successfully seeded {len(seeded_questions)} questions.")

        print("[TEST] Setting up two candidates with active applications...")
        # Setup Candidate 1
        c1 = db.query(Candidate).filter(Candidate.mobile_number == "9000000001").first()
        if not c1:
            c1 = Candidate(mobile_number="9000000001", full_name="Candidate 1", has_verified_details=True)
            db.add(c1)
            db.commit()
            db.refresh(c1)
        else:
            c1.has_verified_details = True
            db.commit()

        app1 = db.query(StudentApplication).filter(StudentApplication.candidate_id == c1.id).first()
        if not app1:
            app1 = StudentApplication(
                candidate_id=c1.id,
                course_id=mca_course.id,
                application_number="TEST-MCA-001",
                mobile_number="9000000001",
                full_name="Candidate 1",
                is_active=True
            )
            db.add(app1)
            db.commit()

        # Setup Candidate 2
        c2 = db.query(Candidate).filter(Candidate.mobile_number == "9000000002").first()
        if not c2:
            c2 = Candidate(mobile_number="9000000002", full_name="Candidate 2", has_verified_details=True)
            db.add(c2)
            db.commit()
            db.refresh(c2)
        else:
            c2.has_verified_details = True
            db.commit()

        app2 = db.query(StudentApplication).filter(StudentApplication.candidate_id == c2.id).first()
        if not app2:
            app2 = StudentApplication(
                candidate_id=c2.id,
                course_id=mca_course.id,
                application_number="TEST-MCA-002",
                mobile_number="9000000002",
                full_name="Candidate 2",
                is_active=True
            )
            db.add(app2)
            db.commit()

        print("[TEST] Starting exam for Candidate 1...")
        res1 = start_exam(current_candidate=c1, db=db)
        questions1 = res1["questions"]
        
        print("[TEST] Starting exam for Candidate 2...")
        res2 = start_exam(current_candidate=c2, db=db)
        questions2 = res2["questions"]

        # Assertions
        print("[TEST] Asserting total questions count is 100...")
        assert len(questions1) == 100, f"Expected 100 questions, got {len(questions1)}"
        assert len(questions2) == 100, f"Expected 100 questions, got {len(questions2)}"

        print("[TEST] Asserting parts grouping order (first 25 Part A, next 25 B, next 25 C, last 25 D)...")
        for i in range(100):
            expected_part = "A" if i < 25 else "B" if i < 50 else "C" if i < 75 else "D"
            assert questions1[i]["part_code"] == expected_part, f"Q{i+1} for Candidate 1 has part_code {questions1[i]['part_code']}, expected {expected_part}"
            assert questions2[i]["part_code"] == expected_part, f"Q{i+1} for Candidate 2 has part_code {questions2[i]['part_code']}, expected {expected_part}"

        print("[TEST] Asserting candidate question orders differ within parts...")
        c1_ids = [q["id"] for q in questions1]
        c2_ids = [q["id"] for q in questions2]

        part_A_diff = c1_ids[0:25] != c2_ids[0:25]
        part_B_diff = c1_ids[25:50] != c2_ids[25:50]
        part_C_diff = c1_ids[50:75] != c2_ids[50:75]
        part_D_diff = c1_ids[75:100] != c2_ids[75:100]

        print(f"[TEST] Part differences - A: {part_A_diff}, B: {part_B_diff}, C: {part_C_diff}, D: {part_D_diff}")
        assert part_A_diff or part_B_diff or part_C_diff or part_D_diff, "Candidates have identical question orders across all sections! Shuffling failed."

        print("[TEST] Resuming exam for Candidate 1...")
        resume_res = start_exam(current_candidate=c1, db=db)
        resume_questions = resume_res["questions"]
        resume_ids = [q["id"] for q in resume_questions]

        print("[TEST] Asserting resumed order matches initial order exactly...")
        assert resume_ids == c1_ids, "Candidate 1's question order changed upon resuming! Resume preservation failed."

        print("[TEST] SUCCESS: All question parts shuffling and resume tests passed successfully!")
    except AssertionError as ae:
        print(f"[TEST] FAILED: AssertionError: {str(ae)}")
        sys.exit(1)
    except Exception as e:
        print(f"[TEST] FAILED: Unexpected error: {str(e)}")
        sys.exit(1)
    finally:
        db.close()

if __name__ == "__main__":
    verify_shuffling()
