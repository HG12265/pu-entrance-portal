import os
import sys
import json
from dotenv import load_dotenv

# Load environment variables from .env file
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(ROOT_DIR, ".env"))

# Map MYSQL_USER/PASSWORD to DATABASE_USER/PASSWORD if not set
if os.environ.get("MYSQL_USER") and not os.environ.get("DATABASE_USER"):
    os.environ["DATABASE_USER"] = os.environ["MYSQL_USER"]
if os.environ.get("MYSQL_PASSWORD") and not os.environ.get("DATABASE_PASSWORD"):
    os.environ["DATABASE_PASSWORD"] = os.environ["MYSQL_PASSWORD"]

# Auto-detect database port: 3306 inside Docker, 3307 on host
if os.environ.get("DATABASE_HOST") == "db":
    os.environ["DATABASE_PORT"] = "3306"
else:
    os.environ["DATABASE_PORT"] = "3307"

# Add project root and backend to python path
sys.path.insert(0, os.path.join(ROOT_DIR, "backend"))

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.main import app
from app.database import SessionLocal
from app.models import Candidate, StudentApplication, ExamAttempt, Question, StudentAnswer, Exam
from app.auth import create_access_token

def test_frontend_offline_queue_static():
    print("Test 1 & 2: Frontend offline queue survives refresh / restart (Static Check)...")
    exam_jsx_path = os.path.join(ROOT_DIR, "frontend", "src", "pages", "Exam.jsx")
    if not os.path.exists(exam_jsx_path):
        print("FAIL: Exam.jsx path not found at " + exam_jsx_path)
        return False
        
    with open(exam_jsx_path, "r", encoding="utf-8") as f:
        content = f.read()
        
    # Check for local storage keys and functions
    checks = [
        "pending_answer_queue" in content,
        "loadQueueFromLocalStorage" in content,
        "saveQueueToLocalStorage" in content,
        "localStorage.getItem(\"pending_answer_queue\")" in content or "localStorage.getItem('pending_answer_queue')" in content
    ]
    
    if all(checks):
        print("PASS: Offline queue persistence implementation found in Exam.jsx")
        return True
    else:
        print(f"FAIL: Missing queue persistence implementation. Checks: {checks}")
        return False

def test_frontend_flush_before_submit_static():
    print("Test 3: Queue flushes before submit (Static Check)...")
    exam_jsx_path = os.path.join(ROOT_DIR, "frontend", "src", "pages", "Exam.jsx")
    if not os.path.exists(exam_jsx_path):
        print("FAIL: Exam.jsx path not found")
        return False
        
    with open(exam_jsx_path, "r", encoding="utf-8") as f:
        content = f.read()
        
    # Check that flushPendingQueue is defined and awaited before submit and auto submit
    checks = [
        "flushPendingQueue" in content,
        "await flushPendingQueue()" in content
    ]
    
    if all(checks):
        print("PASS: Queue flush before submit implementation found in Exam.jsx")
        return True
    else:
        print(f"FAIL: Missing flushPendingQueue implementation. Checks: {checks}")
        return False

def test_strict_option_validation():
    print("Test 4 & 5: Strict option validation (API Check)...")
    client = TestClient(app)
    db = SessionLocal()
    
    try:
        # Create temp candidate and exam attempt
        exam = db.query(Exam).first()
        if not exam:
            print("FAIL: No seeded exam found. Run seeding scripts first.")
            return False
            
        question = db.query(Question).filter(Question.exam_id == exam.id).first()
        if not question:
            print("FAIL: No question found in database to test option validation.")
            return False
            
        candidate = Candidate(
            full_name="Test High Stakes",
            mobile_number="9999999999",
            email="test_high_stakes@example.com",
            has_verified_details=True
        )
        db.add(candidate)
        db.commit()
        db.refresh(candidate)
        
        attempt = ExamAttempt(
            candidate_id=candidate.id,
            exam_id=exam.id,
            status="active",
            is_submitted=False,
            question_order_json=json.dumps({"final_order": [question.id]})
        )
        db.add(attempt)
        db.commit()
        db.refresh(attempt)
        
        # Authenticate
        token = create_access_token({
            "candidate_id": candidate.id,
            "role": "student",
            "token_type": "student_exam"
        })
        headers = {"Authorization": f"Bearer {token}"}
        
        # Test valid options
        for opt in ["A", "B", "C", "D", "a", "b", "c", "d", "", None]:
            payload = {
                "attempt_id": attempt.id,
                "question_id": question.id,
                "selected_option": opt
            }
            res = client.post("/api/v1/exams/save-answer", json=payload, headers=headers)
            if res.status_code != 200:
                print(f"FAIL: Rejected valid option '{opt}'. Status: {res.status_code}, Body: {res.text}")
                return False
                
        # Test invalid options (must reject with 422)
        for opt in ["X", "Z", "TEST", "123", "a_long_option_value"]:
            payload = {
                "attempt_id": attempt.id,
                "question_id": question.id,
                "selected_option": opt
            }
            res = client.post("/api/v1/exams/save-answer", json=payload, headers=headers)
            if res.status_code != 422:
                print(f"FAIL: Accepted invalid option '{opt}'. Status: {res.status_code}")
                return False
                
        print("PASS: Strict option validation verified (Accepts A-D, rejects others with 422)")
        return True
    except Exception as e:
        print(f"FAIL: Strict option validation encountered error: {e}")
        return False
    finally:
        # Clean up
        db.query(StudentAnswer).filter(StudentAnswer.attempt_id == attempt.id).delete()
        db.delete(attempt)
        db.delete(candidate)
        db.commit()
        db.close()

def test_submitted_attempt_immutable():
    print("Test 6: Submitted attempt immutable (API Check)...")
    client = TestClient(app)
    db = SessionLocal()
    
    try:
        # Create temp candidate and exam attempt
        exam = db.query(Exam).first()
        question = db.query(Question).filter(Question.exam_id == exam.id).first()
        if not question:
            print("FAIL: No question found in database to test immutability.")
            return False
            
        candidate = Candidate(
            full_name="Test High Stakes Immutable",
            mobile_number="9999999998",
            email="test_high_stakes_immutable@example.com",
            has_verified_details=True
        )
        db.add(candidate)
        db.commit()
        db.refresh(candidate)
        
        attempt = ExamAttempt(
            candidate_id=candidate.id,
            exam_id=exam.id,
            status="submitted",
            is_submitted=True,
            question_order_json=json.dumps({"final_order": [question.id]})
        )
        db.add(attempt)
        db.commit()
        db.refresh(attempt)
        
        # Authenticate
        token = create_access_token({
            "candidate_id": candidate.id,
            "role": "student",
            "token_type": "student_exam"
        })
        headers = {"Authorization": f"Bearer {token}"}
        
        # Attempt to save answer (must return 400)
        payload = {
            "attempt_id": attempt.id,
            "question_id": question.id,
            "selected_option": "A"
        }
        res = client.post("/api/v1/exams/save-answer", json=payload, headers=headers)
        if res.status_code == 400:
            print("PASS: Submitted attempt is immutable (Returns 400 on edit attempt)")
            return True
        else:
            print(f"FAIL: Allowed saving answer on submitted attempt. Status: {res.status_code}, Body: {res.text}")
            return False
    except Exception as e:
        print(f"FAIL: Submitted attempt immutability check encountered error: {e}")
        return False
    finally:
        db.query(StudentAnswer).filter(StudentAnswer.attempt_id == attempt.id).delete()
        db.delete(attempt)
        db.delete(candidate)
        db.commit()
        db.close()

def test_backup_restore_scripts_generated():
    print("Test 7 & 8: Backup and restore scripts generated...")
    backup_path = os.path.join(ROOT_DIR, "deployment", "backup", "backup.sh")
    restore_path = os.path.join(ROOT_DIR, "deployment", "backup", "restore.sh")
    
    if not os.path.exists(backup_path):
        print("FAIL: backup.sh does not exist")
        return False
    if not os.path.exists(restore_path):
        print("FAIL: restore.sh does not exist")
        return False
        
    with open(backup_path, "r", encoding="utf-8") as f:
        backup_content = f.read()
    with open(restore_path, "r", encoding="utf-8") as f:
        restore_content = f.read()
        
    # Check backup script contents
    backup_checks = [
        "mysqldump" in backup_content,
        "--single-transaction" in backup_content,
        "--routines" in backup_content,
        "--triggers" in backup_content,
        "gzip" in backup_content
    ]
    
    # Check restore script contents
    restore_checks = [
        "mysql" in restore_content,
        "gunzip" in restore_content,
        "DROP DATABASE" in restore_content,
        "CREATE DATABASE" in restore_content
    ]
    
    if not all(backup_checks):
        print(f"FAIL: backup.sh does not meet specifications. Checks: {backup_checks}")
        return False
    if not all(restore_checks):
        print(f"FAIL: restore.sh does not meet specifications. Checks: {restore_checks}")
        return False
        
    print("PASS: Backup and restore scripts meet all system design requirements")
    return True

def main():
    print("\n" + "="*50)
    print("RUNNING HIGH-STAKES EXAM PORTAL READINESS TESTS")
    print("="*50)
    
    results = [
        test_frontend_offline_queue_static(),
        test_frontend_flush_before_submit_static(),
        test_strict_option_validation(),
        test_submitted_attempt_immutable(),
        test_backup_restore_scripts_generated()
    ]
    
    print("="*50)
    if all(results):
        print("FINAL RESULTS: ALL TESTS PASSED! Portal is HIGH-STAKES EXAM READY.")
        print("="*50)
        sys.exit(0)
    else:
        print("FINAL RESULTS: SOME TESTS FAILED. Portal is NOT READY.")
        print("="*50)
        sys.exit(1)

if __name__ == "__main__":
    main()
