import os
import time
import json
import random
import sys
import threading
from dotenv import load_dotenv

# Load env file from project root
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv(os.path.join(ROOT_DIR, ".env"))

# Map variables if not set
if os.environ.get("MYSQL_USER") and not os.environ.get("DATABASE_USER"):
    os.environ["DATABASE_USER"] = os.environ["MYSQL_USER"]
if os.environ.get("MYSQL_PASSWORD") and not os.environ.get("DATABASE_PASSWORD"):
    os.environ["DATABASE_PASSWORD"] = os.environ["MYSQL_PASSWORD"]

from sqlalchemy import event, text
from sqlalchemy.orm import Session
from app.database import engine, SessionLocal
from app.models import Exam, Candidate, StudentApplication, ExamAttempt, Question, StudentAnswer, ExamAttemptEventLog
from app.routers.exams import start_exam, save_answer, SaveAnswerPayload

# Global query list for event listener
queries = []

@event.listens_for(engine, "before_cursor_execute")
def before_cursor_execute(conn, cursor, statement, parameters, context, execmany):
    context._query_start_time = time.perf_counter()

@event.listens_for(engine, "after_cursor_execute")
def after_cursor_execute(conn, cursor, statement, parameters, context, execmany):
    if hasattr(context, "_query_start_time"):
        total = time.perf_counter() - context._query_start_time
        queries.append((statement, parameters, total))

def reset_queries():
    global queries
    queries = []

def run_explain(db: Session, query_str: str):
    try:
        res = db.execute(text(f"EXPLAIN {query_str}")).fetchall()
        print(f"\nEXPLAIN Plan for: {query_str}")
        print("-" * 80)
        for row in res:
            print(row)
        print("-" * 80)
    except Exception as e:
        print(f"Error running EXPLAIN: {e}")

def run_explain_analyze(db: Session, query_str: str):
    try:
        res = db.execute(text(f"EXPLAIN ANALYZE {query_str}")).fetchall()
        print(f"\nEXPLAIN ANALYZE Plan for: {query_str}")
        print("-" * 80)
        for row in res:
            print(row[0])
        print("-" * 80)
    except Exception as e:
        print(f"Error running EXPLAIN ANALYZE: {e}")

def run_audit():
    db = SessionLocal()
    db.expire_on_commit = False
    
    print("=" * 60)
    print("         PERIYAR ENTRANCE PORTAL PERFORMANCE AUDIT")
    print("=" * 60)
    
    # ----------------------------------------------------
    # Setup test exam and candidate
    # ----------------------------------------------------
    exam = db.query(Exam).first()
    if not exam:
        print("ERROR: No exam found. Run seed_load_test_students.py first.")
        sys.exit(1)
        
    # Create clean profile candidate
    candidate_mobile = "9999999999"
    db.query(StudentApplication).filter(StudentApplication.mobile_number == candidate_mobile).delete()
    db.query(Candidate).filter(Candidate.mobile_number == candidate_mobile).delete()
    db.commit()
    
    course_mca = db.query(StudentApplication).filter(StudentApplication.application_number.like("LOAD-%")).first().course
    
    candidate = Candidate(
        mobile_number=candidate_mobile,
        full_name="Profile Test Student",
        has_verified_details=True
    )
    db.add(candidate)
    db.commit()
    db.refresh(candidate)
    
    application = StudentApplication(
        candidate_id=candidate.id,
        course_id=course_mca.id,
        application_number="PROFILE-MCA-001",
        mobile_number=candidate_mobile,
        full_name="Profile Test Student",
        ug_marks=85.0,
        is_active=True
    )
    db.add(application)
    db.commit()
    
    # ----------------------------------------------------
    # PHASE 1 - START EXAM PROFILING
    # ----------------------------------------------------
    print("\n" + "=" * 50)
    print("PHASE 1 - START EXAM PROFILING")
    print("=" * 50)
    
    reset_queries()
    start_time = time.perf_counter()
    
    # Measure subcomponents:
    # 1. Question loading time
    t0 = time.perf_counter()
    all_questions = db.query(Question).filter(Question.exam_id == exam.id).all()
    q_load_time = time.perf_counter() - t0
    
    # 2. Question shuffle time
    t0 = time.perf_counter()
    part_A_qs = [q for q in all_questions if q.part_code == "A"]
    part_B_qs = [q for q in all_questions if q.part_code == "B"]
    part_C_qs = [q for q in all_questions if q.part_code == "C"]
    part_D_qs = [q for q in all_questions if q.part_code == "D"]
    random.shuffle(part_A_qs)
    random.shuffle(part_B_qs)
    random.shuffle(part_C_qs)
    random.shuffle(part_D_qs)
    ordered_qs = part_A_qs + part_B_qs + part_C_qs + part_D_qs
    q_shuffle_time = time.perf_counter() - t0
    
    # 3. question_order_json creation time
    t0 = time.perf_counter()
    order_json = {
        "A": [q.id for q in part_A_qs],
        "B": [q.id for q in part_B_qs],
        "C": [q.id for q in part_C_qs],
        "D": [q.id for q in part_D_qs],
        "final_order": [q.id for q in ordered_qs]
    }
    order_str = json.dumps(order_json)
    json_creation_time = time.perf_counter() - t0
    
    # 4. Save attempt
    t0 = time.perf_counter()
    # Clean any old attempt first
    db.query(ExamAttempt).filter(ExamAttempt.candidate_id == candidate.id).delete()
    db.commit()
    
    # Now run the actual endpoint code for starting exam
    reset_queries()
    t_start_endpoint = time.perf_counter()
    res = start_exam(current_candidate=candidate, db=db)
    endpoint_execution_time = time.perf_counter() - t_start_endpoint
    
    total_query_time = sum(q[2] for q in queries)
    query_count = len(queries)
    
    # Clean answers time
    t_answers_insert = 0.0
    for q in queries:
        if "INSERT INTO student_answers" in q[0]:
            t_answers_insert += q[2]
            
    print(f"Total Execution Time (endpoint): {endpoint_execution_time * 1000:.2f} ms")
    print(f"Query Count: {query_count}")
    print(f"Total DB Query Time: {total_query_time * 1000:.2f} ms")
    print(f"ORM/Serialization/Python Overhead: {(endpoint_execution_time - total_query_time) * 1000:.2f} ms")
    print(f"  - Question Loading time: {q_load_time * 1000:.2f} ms")
    print(f"  - Question Shuffle time: {q_shuffle_time * 1000:.2f} ms")
    print(f"  - question_order_json creation time: {json_creation_time * 1000:.2f} ms")
    print(f"  - StudentAnswer INSERT DB time: {t_answers_insert * 1000:.2f} ms")
    
    # Print query breakdown
    print("\nQuery Breakdown:")
    for i, (stmt, params, dur) in enumerate(queries):
        print(f"Query {i+1} [{dur*1000:.2f}ms]: {stmt[:120]}...")
        
    attempt_id = res["attempt_id"]
    
    # ----------------------------------------------------
    # PHASE 2 - SAVE ANSWER PROFILING
    # ----------------------------------------------------
    print("\n" + "=" * 50)
    print("PHASE 2 - SAVE ANSWER PROFILING")
    print("=" * 50)
    
    save_times = []
    question_ids = order_json["final_order"]
    
    # We will simulate 100 answer saves
    reset_queries()
    
    for idx, qid in enumerate(question_ids):
        payload = SaveAnswerPayload(
            attempt_id=attempt_id,
            question_id=qid,
            selected_option=random.choice(["A", "B", "C", "D"])
        )
        t_save_start = time.perf_counter()
        save_answer(payload=payload, current_candidate=candidate, db=db)
        t_save_end = time.perf_counter()
        save_times.append((t_save_end - t_save_start) * 1000)
        
    avg_save = sum(save_times) / len(save_times)
    save_times.sort()
    p95_save = save_times[int(len(save_times) * 0.95)]
    p99_save = save_times[int(len(save_times) * 0.99)]
    
    # Analyze the queries executed for a single save_answer
    reset_queries()
    payload = SaveAnswerPayload(
        attempt_id=attempt_id,
        question_id=question_ids[0],
        selected_option="B"
    )
    save_answer(payload=payload, current_candidate=candidate, db=db)
    
    print(f"Average Answer Save Time: {avg_save:.2f} ms")
    print(f"P95 Answer Save Time: {p95_save:.2f} ms")
    print(f"P99 Answer Save Time: {p99_save:.2f} ms")
    print(f"Queries executed per single save-answer call: {len(queries)}")
    for i, (stmt, params, dur) in enumerate(queries):
        print(f"  - Query {i+1} [{dur*1000:.2f}ms]: {stmt[:120]}...")
        
    # ----------------------------------------------------
    # PHASE 3 - DATABASE EXPLAIN ANALYSIS
    # ----------------------------------------------------
    print("\n" + "=" * 50)
    print("PHASE 3 - DATABASE EXPLAIN ANALYSIS")
    print("=" * 50)
    
    # Explain all key queries
    run_explain(db, f"SELECT * FROM exam_attempts WHERE candidate_id = {candidate.id} AND exam_id = {exam.id}")
    run_explain(db, f"SELECT * FROM student_answers WHERE attempt_id = {attempt_id} AND question_id = {question_ids[0]}")
    run_explain(db, f"SELECT * FROM questions WHERE exam_id = {exam.id}")
    run_explain(db, f"SELECT * FROM candidates WHERE mobile_number = '{candidate_mobile}'")
    run_explain(db, f"SELECT * FROM student_applications WHERE application_number = 'PROFILE-MCA-001'")
    
    # EXPLAIN ANALYZE support
    run_explain_analyze(db, f"SELECT * FROM exam_attempts WHERE candidate_id = {candidate.id} AND exam_id = {exam.id}")
    run_explain_analyze(db, f"SELECT * FROM student_answers WHERE attempt_id = {attempt_id} AND question_id = {question_ids[0]}")
    
    # ----------------------------------------------------
    # PHASE 4 - CONNECTION POOL AUDIT
    # ----------------------------------------------------
    print("\n" + "=" * 50)
    print("PHASE 4 - CONNECTION POOL AUDIT")
    print("=" * 50)
    
    pool = engine.pool
    print(f"Pool class: {pool.__class__.__name__}")
    print(f"Pool size: {pool.size()}")
    print(f"Max overflow: {pool._max_overflow}")
    print(f"Pool timeout: {pool._timeout} seconds")
    print(f"Current checked-in connections (in pool): {pool.checkedin()}")
    print(f"Current checked-out connections (active): {pool.checkedout()}")
    print(f"Current overflow connections: {pool.overflow()}")
    
    # Clean test candidates
    db.query(StudentApplication).filter(StudentApplication.mobile_number == candidate_mobile).delete()
    db.query(Candidate).filter(Candidate.mobile_number == candidate_mobile).delete()
    db.commit()
    db.close()

if __name__ == "__main__":
    run_audit()
