import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.database import Base, engine, SessionLocal
from app.models import Admin
from app.auth import get_password_hash
from app.routers import admin, students, exams, questions, results
from slowapi.middleware import SlowAPIMiddleware
from slowapi.errors import RateLimitExceeded
from slowapi import _rate_limit_exceeded_handler
from app.limiter import limiter

import os
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

# Create tables
Base.metadata.create_all(bind=engine)

# Dynamic database columns migration
def run_migrations():
    db = SessionLocal()
    try:
        # Columns for questions table
        cols_to_add = ["image_url", "option_a_image_url", "option_b_image_url", "option_c_image_url", "option_d_image_url"]
        for col in cols_to_add:
            res = db.execute(text(f"SHOW COLUMNS FROM questions LIKE '{col}'")).fetchone()
            if not res:
                db.execute(text(f"ALTER TABLE questions ADD COLUMN {col} VARCHAR(500) NULL"))
                db.commit()
                print(f"Migration: Column '{col}' added to questions table.")

        # Part columns for questions table
        part_cols = {
            "part_code": "VARCHAR(50) NULL",
            "part_name": "VARCHAR(255) NULL",
            "part_order": "INT NULL",
            "source_s_no": "INT NULL"
        }
        for col, col_type in part_cols.items():
            res = db.execute(text(f"SHOW COLUMNS FROM questions LIKE '{col}'")).fetchone()
            if not res:
                db.execute(text(f"ALTER TABLE questions ADD COLUMN {col} {col_type}"))
                db.commit()
                print(f"Migration: Column '{col}' added to questions table.")

        # Shuffling serialization column for exam_attempts table
        res = db.execute(text("SHOW COLUMNS FROM exam_attempts LIKE 'question_order_json'")).fetchone()
        if not res:
            db.execute(text("ALTER TABLE exam_attempts ADD COLUMN question_order_json TEXT NULL"))
            db.commit()
            print("Migration: Column 'question_order_json' added to exam_attempts table.")

        # Additional columns for exam_attempts table
        attempt_cols = {
            "status": "VARCHAR(50) NOT NULL DEFAULT 'active'",
            "violation_count": "INT NOT NULL DEFAULT 0",
            "submitted_reason": "VARCHAR(500) NULL",
            "submit_source": "VARCHAR(100) NULL",
            "elapsed_seconds_at_submit": "INT NOT NULL DEFAULT 0",
            "reopened_by_admin_id": "INT NULL",
            "reopened_at": "DATETIME NULL",
            "reopen_reason": "VARCHAR(500) NULL",
            "reopen_count": "INT NOT NULL DEFAULT 0",
            "last_activity_at": "DATETIME NULL",
            "current_question_index": "INT NULL",
            "time_extension_minutes": "INT NOT NULL DEFAULT 0"
        }
        for col, col_type in attempt_cols.items():
            res = db.execute(text(f"SHOW COLUMNS FROM exam_attempts LIKE '{col}'")).fetchone()
            if not res:
                db.execute(text(f"ALTER TABLE exam_attempts ADD COLUMN {col} {col_type}"))
                db.commit()
                print(f"Migration: Column '{col}' added to exam_attempts table.")

        # Additional columns for student_answers table
        res = db.execute(text("SHOW COLUMNS FROM student_answers LIKE 'updated_at'")).fetchone()
        if not res:
            db.execute(text("ALTER TABLE student_answers ADD COLUMN updated_at DATETIME NULL"))
            db.commit()
            print("Migration: Column 'updated_at' added to student_answers table.")

    except Exception as e:
        print(f"Migration warning: {e}")
    finally:
        db.close()

run_migrations()

# Seed default admin
def seed_admin():
    db = SessionLocal()
    try:
        admin_exists = db.query(Admin).filter(Admin.username == settings.ADMIN_USERNAME).first()
        if not admin_exists:
            hashed_pw = get_password_hash(settings.ADMIN_PASSWORD)
            default_admin = Admin(
                username=settings.ADMIN_USERNAME,
                password_hash=hashed_pw,
                name="Periyar Admin"
            )
            db.add(default_admin)
            db.commit()
            print("Admin account seeded successfully from environment variables.")
    except Exception as e:
        print(f"Error seeding admin: {e}")
    finally:
        db.close()

seed_admin()

def seed_default_courses():
    db = SessionLocal()
    try:
        from app.models import Course
        courses = [
            {"code": "MCA", "name": "Master of Computer Applications", "seat_count": 30},
            {"code": "MSC_CS", "name": "M.Sc Computer Science", "seat_count": 44},
            {"code": "MSC_DS", "name": "M.Sc Data Science", "seat_count": 44}
        ]
        for c in courses:
            existing = db.query(Course).filter(Course.code == c["code"]).first()
            if not existing:
                new_c = Course(
                    code=c["code"],
                    name=c["name"],
                    seat_count=c["seat_count"],
                    is_active=True
                )
                db.add(new_c)
            else:
                if existing.seat_count != c["seat_count"]:
                    existing.seat_count = c["seat_count"]
        db.commit()
        print("Default courses checked/seeded successfully.")
    except Exception as e:
        print(f"Error seeding courses: {e}")
        db.rollback()
    finally:
        db.close()

seed_default_courses()

def seed_default_community_seats():
    db = SessionLocal()
    try:
        from app.models import Course, CourseCommunitySeat
        community_seats_data = {
            "MCA": [
                {"code": "OC", "name": "Open Competition", "seats": 9, "order": 1},
                {"code": "BC", "name": "Backward Class", "seats": 8, "order": 2},
                {"code": "BCM", "name": "Backward Class Muslim", "seats": 1, "order": 3},
                {"code": "MBC", "name": "Most Backward Class", "seats": 6, "order": 4},
                {"code": "SC", "name": "Scheduled Caste", "seats": 4, "order": 5},
                {"code": "SCA", "name": "Scheduled Caste Arunthathiyar", "seats": 1, "order": 6},
                {"code": "ST", "name": "Scheduled Tribe", "seats": 1, "order": 7},
            ],
            "MSC_CS": [
                {"code": "OC", "name": "Open Competition", "seats": 14, "order": 1},
                {"code": "BC", "name": "Backward Class", "seats": 12, "order": 2},
                {"code": "BCM", "name": "Backward Class Muslim", "seats": 2, "order": 3},
                {"code": "MBC", "name": "Most Backward Class", "seats": 9, "order": 4},
                {"code": "SC", "name": "Scheduled Caste", "seats": 5, "order": 5},
                {"code": "SCA", "name": "Scheduled Caste Arunthathiyar", "seats": 1, "order": 6},
                {"code": "ST", "name": "Scheduled Tribe", "seats": 1, "order": 7},
            ],
            "MSC_DS": [
                {"code": "OC", "name": "Open Competition", "seats": 14, "order": 1},
                {"code": "BC", "name": "Backward Class", "seats": 12, "order": 2},
                {"code": "BCM", "name": "Backward Class Muslim", "seats": 2, "order": 3},
                {"code": "MBC", "name": "Most Backward Class", "seats": 9, "order": 4},
                {"code": "SC", "name": "Scheduled Caste", "seats": 5, "order": 5},
                {"code": "ST", "name": "Scheduled Tribe", "seats": 1, "order": 7},
                {"code": "SCA", "name": "Scheduled Caste Arunthathiyar", "seats": 1, "order": 6},
            ]
        }
        for course_code, seats_list in community_seats_data.items():
            course_obj = db.query(Course).filter(Course.code == course_code).first()
            if course_obj:
                for seat_info in seats_list:
                    existing_seat = db.query(CourseCommunitySeat).filter(
                        CourseCommunitySeat.course_id == course_obj.id,
                        CourseCommunitySeat.community_code == seat_info["code"]
                    ).first()
                    if not existing_seat:
                        new_seat = CourseCommunitySeat(
                            course_id=course_obj.id,
                            community_code=seat_info["code"],
                            community_name=seat_info["name"],
                            seat_count=seat_info["seats"],
                            display_order=seat_info["order"]
                        )
                        db.add(new_seat)
                    else:
                        existing_seat.seat_count = seat_info["seats"]
                        existing_seat.display_order = seat_info["order"]
        db.commit()
        print("Default community seats seeded/updated successfully.")
    except Exception as e:
        print(f"Error seeding community seats: {e}")
        db.rollback()
    finally:
        db.close()

seed_default_community_seats()

def seed_default_exam():
    db = SessionLocal()
    try:
        from app.models import Exam
        import datetime
        exam = db.query(Exam).first()
        start = datetime.datetime(2026, 6, 20, 0, 0, 0)
        end = datetime.datetime(2026, 7, 5, 23, 59, 59)
        if not exam:
            exam = Exam(
                name="Periyar University Entrance Examination 2026",
                total_questions=100,
                duration_minutes=120,
                start_date=start,
                end_date=end,
                result_visibility=True
            )
            db.add(exam)
            print("Exam seeded successfully.")
        else:
            exam.total_questions = 100
            exam.duration_minutes = 120
            exam.start_date = start
            exam.end_date = end
        db.commit()
    except Exception as e:
        print(f"Error seeding exam: {e}")
        db.rollback()
    finally:
        db.close()

seed_default_exam()


app = FastAPI(
    title=settings.APP_NAME,
    description="Backend services for student registration, exam taking, evaluation, leaderboard, and admin dashboard.",
    version="1.0.0",
    docs_url="/docs" if settings.SHOW_DOCS else None,
    redoc_url="/redoc" if settings.SHOW_DOCS else None,
    openapi_url="/openapi.json" if settings.SHOW_DOCS else None,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# Enable CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(admin.router)
app.include_router(students.router)
app.include_router(exams.router)
app.include_router(questions.router)
app.include_router(results.router)

# Mount static directory for serving question/option images
static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
os.makedirs(static_dir, exist_ok=True)
app.mount("/api/v1/static", StaticFiles(directory=static_dir), name="static")

@app.get("/")
def read_root():
    if settings.SHOW_DOCS:
        return {"message": "Welcome to Periyar University Entrance Examination Portal API. Refer to /docs for API documentation."}
    return {"message": "Welcome to Periyar University Entrance Examination Portal API."}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
