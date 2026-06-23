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
        cols_to_add = ["image_url", "option_a_image_url", "option_b_image_url", "option_c_image_url", "option_d_image_url"]
        for col in cols_to_add:
            res = db.execute(text(f"SHOW COLUMNS FROM questions LIKE '{col}'")).fetchone()
            if not res:
                db.execute(text(f"ALTER TABLE questions ADD COLUMN {col} VARCHAR(500) NULL"))
                db.commit()
                print(f"Migration: Column '{col}' added to questions table.")
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
            {"code": "MSC_CS", "name": "M.Sc Computer Science", "seat_count": 45},
            {"code": "MSC_DS", "name": "M.Sc Data Science", "seat_count": 30}
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
        db.commit()
        print("Default courses checked/seeded successfully.")
    except Exception as e:
        print(f"Error seeding courses: {e}")
        db.rollback()
    finally:
        db.close()

seed_default_courses()


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
