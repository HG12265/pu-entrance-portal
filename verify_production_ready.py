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

from sqlalchemy import text
from app.database import engine, SessionLocal
from app.models import Question

def check_gunicorn_workers():
    print("1. Checking Gunicorn configuration in Dockerfile...")
    dockerfile_path = os.path.join(ROOT_DIR, "backend", "Dockerfile")
    if not os.path.exists(dockerfile_path):
        print("FAIL: backend/Dockerfile not found")
        return False
        
    with open(dockerfile_path, "r", encoding="utf-8") as f:
        content = f.read()
        
    if "gunicorn" in content and ("-w 4" in content or '"-w", "4"' in content):
        print("PASS: Gunicorn configured with 4 workers in Dockerfile.")
        return True
    else:
        print("FAIL: Gunicorn with 4 workers not found in Dockerfile.")
        return False

def check_db_pool_settings():
    print("2. Checking SQLAlchemy DB pool settings...")
    pool = engine.pool
    size = pool.size()
    overflow = pool._max_overflow
    timeout = pool._timeout
    recycle = pool._recycle
    
    print(f"   Pool Size: {size} (Expected: 100)")
    print(f"   Max Overflow: {overflow} (Expected: 50)")
    print(f"   Pool Timeout: {timeout} seconds (Expected: 60)")
    print(f"   Pool Recycle: {recycle} seconds (Expected: 1800)")
    
    if size == 100 and overflow == 50 and timeout == 60 and recycle == 1800:
        print("PASS: DB Pool settings match production values.")
        return True
    else:
        print("FAIL: DB Pool settings mismatch.")
        return False

def check_mysql_max_connections():
    print("3. Querying MySQL live max_connections...")
    db = SessionLocal()
    try:
        res = db.execute(text("SHOW VARIABLES LIKE 'max_connections'")).fetchone()
        if res:
            val = int(res[1])
            print(f"   MySQL max_connections: {val} (Expected: 300)")
            if val == 300:
                print("PASS: MySQL max_connections is 300.")
                return True
            else:
                print("FAIL: MySQL max_connections is not 300.")
                return False
        else:
            print("FAIL: Could not query max_connections.")
            return False
    except Exception as e:
        print(f"FAIL: Error querying MySQL max_connections: {e}")
        return False
    finally:
        db.close()

def check_question_bank():
    print("4. Checking question bank configuration...")
    db = SessionLocal()
    try:
        questions = db.query(Question).all()
        total_count = len(questions)
        print(f"   Total Questions: {total_count} (Expected: 100)")
        
        part_counts = {"A": 0, "B": 0, "C": 0, "D": 0}
        for q in questions:
            if q.part_code in part_counts:
                part_counts[q.part_code] += 1
                
        print(f"   Part counts: {part_counts} (Expected: 25 each)")
        
        if total_count == 100 and all(c == 25 for c in part_counts.values()):
            print("PASS: Question bank has exactly 100 questions distributed as 25-25-25-25.")
            return True
        else:
            print("FAIL: Question count or distribution mismatch.")
            return False
    except Exception as e:
        print(f"FAIL: Error checking question bank: {e}")
        return False
    finally:
        db.close()

def check_backup_scripts():
    print("5. Checking backup and restore scripts...")
    bpath = os.path.join(ROOT_DIR, "deployment", "backup", "backup.sh")
    rpath = os.path.join(ROOT_DIR, "deployment", "backup", "restore.sh")
    
    if os.path.exists(bpath) and os.path.exists(rpath):
        print("PASS: Backup scripts found.")
        return True
    else:
        print("FAIL: Backup or restore script missing.")
        return False

def check_ssl_nginx_config():
    print("6. Checking Nginx SSL configuration...")
    nginx_conf = os.path.join(ROOT_DIR, "frontend", "nginx.conf")
    if not os.path.exists(nginx_conf):
        print("FAIL: Nginx conf not found")
        return False
        
    with open(nginx_conf, "r", encoding="utf-8") as f:
        content = f.read()
        
    checks = [
        "listen 443 ssl" in content,
        "ssl_certificate" in content,
        "ssl_certificate_key" in content,
        "ssl_protocols" in content
    ]
    
    if all(checks):
        print("PASS: Nginx SSL/TLS parameters found.")
        return True
    else:
        print(f"FAIL: Nginx SSL configuration parameters missing. Checks: {checks}")
        return False

def check_indexes():
    print("7. Verifying required indexes in MySQL...")
    db = SessionLocal()
    try:
        tables_to_check = {
            "candidates": ["ix_candidates_mobile_number"],
            "student_applications": ["ix_student_applications_application_number"],
            "exam_attempts": ["_candidate_exam_attempt_uc"],
            "student_answers": ["_attempt_question_uc"]
        }
        
        for table, expected_idxs in tables_to_check.items():
            res = db.execute(text(f"SHOW INDEX FROM {table}")).fetchall()
            indices = {row[2] for row in res}
            for idx in expected_idxs:
                if idx not in indices:
                    print(f"FAIL: Index '{idx}' on table '{table}' not found.")
                    return False
        print("PASS: All required unique constraints and performance indexes are present.")
        return True
    except Exception as e:
        print(f"FAIL: Error verifying indexes: {e}")
        return False
    finally:
        db.close()

def check_frontend_persistence_auto_submit():
    print("8. Checking frontend queue persistence and auto-submit...")
    exam_jsx = os.path.join(ROOT_DIR, "frontend", "src", "pages", "Exam.jsx")
    if not os.path.exists(exam_jsx):
        print("FAIL: Exam.jsx not found")
        return False
        
    with open(exam_jsx, "r", encoding="utf-8") as f:
        content = f.read()
        
    checks = [
        "pending_answer_queue" in content,
        "handleAutoSubmit" in content,
        "flushPendingQueue" in content
    ]
    
    if all(checks):
        print("PASS: Queue persistence and auto-submit components present in Exam.jsx.")
        return True
    else:
        print(f"FAIL: Missing Exam.jsx attributes. Checks: {checks}")
        return False

def main():
    print("\n" + "="*60)
    # Perform all checks
    checks = [
        check_gunicorn_workers(),
        check_db_pool_settings(),
        check_mysql_max_connections(),
        check_question_bank(),
        check_backup_scripts(),
        check_ssl_nginx_config(),
        check_indexes(),
        check_frontend_persistence_auto_submit()
    ]
    
    print("="*60)
    if all(checks):
        print("FINAL RESULTS: ALL CHECKS PASSED. SYSTEM IS PRODUCTION READY FOR 250 STUDENTS.")
        print("="*60)
        sys.exit(0)
    else:
        print("FINAL RESULTS: SOME CHECKS FAILED. SYSTEM IS NOT READY.")
        print("="*60)
        sys.exit(1)

if __name__ == "__main__":
    main()
