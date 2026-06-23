import os
import sys

# Add backend folder to python search path
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.join(current_dir, "backend")
sys.path.insert(0, backend_dir)

def check_env_allowed():
    # 1. Check current OS/Process environment variable
    env_val = os.environ.get("ENVIRONMENT", "").strip().lower()
    if env_val in ["production", "prod", "staging"]:
        return False
        
    # 2. Try loading and reading from root and backend .env files manually
    for env_file in [".env", "backend/.env"]:
        env_path = os.path.join(current_dir, env_file)
        if os.path.exists(env_path):
            try:
                with open(env_path, "r") as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith("ENVIRONMENT="):
                            val = line.split("=", 1)[1].strip()
                            # Strip quotes
                            val = val.replace('"', '').replace("'", '').lower()
                            if val in ["production", "prod", "staging"]:
                                return False
            except Exception:
                pass
    return True

if not check_env_allowed():
    print("==================================================================")
    print(" CRITICAL ERROR: clear_db.py execution aborted!")
    print(" Running this reset script is strictly forbidden in production/staging.")
    print("==================================================================")
    sys.exit(1)

# Configure database credentials for host machine access (port 3307 mapped to MySQL container)
os.environ["DATABASE_HOST"] = "localhost"
os.environ["DATABASE_PORT"] = "3307"
os.environ["DATABASE_USER"] = "root"
os.environ["DATABASE_PASSWORD"] = "PeriyarDbRootPassword2026!"
os.environ["DATABASE_NAME"] = "periyar_entrance_exam"

from sqlalchemy import text
from app.database import engine, Base, SessionLocal
from app.auth import get_password_hash
from app.config import settings

def main():
    print("==================================================")
    print(" WARNING: This will delete and recreate all tables.")
    print(" Safe dependency-order drop will be executed.")
    print(" Local development use only.")
    print("==================================================")
    
    # Import all models to ensure metadata registers them
    try:
        from app.models import Admin, Course, Candidate, StudentApplication, ImportBatch, AdmissionConfirmation, ExamAttempt, StudentAnswer
    except ImportError as ie:
        print(f"Model Import Warning (some tables may not be loaded yet): {ie}")

    try:
        # 1. Clear database tables
        with engine.connect() as connection:
            # Safely disable foreign key checks for dropping tables
            connection.execute(text("SET FOREIGN_KEY_CHECKS = 0;"))
            
            tables_to_drop = [
                "student_answers",
                "exam_attempts",
                "admission_confirmations",
                "student_applications",
                "candidates",
                "import_batches",
                "courses",
                "admins"
            ]
            for t in tables_to_drop:
                print(f"Dropping table if exists: {t}")
                connection.execute(text(f"DROP TABLE IF EXISTS {t};"))
                
            print("Creating all tables from current model declarations...")
            Base.metadata.create_all(bind=engine)
            connection.execute(text("SET FOREIGN_KEY_CHECKS = 1;"))
            
        print("[SUCCESS] All tables dropped and recreated!")

        # 2. Seed default courses
        print("Seeding default courses (MCA, MSC_CS, MSC_DS)...")
        db = SessionLocal()
        try:
            from app.models import Course
            courses = [
                {"code": "MCA", "name": "Master of Computer Applications", "seat_count": 30},
                {"code": "MSC_CS", "name": "M.Sc Computer Science", "seat_count": 45},
                {"code": "MSC_DS", "name": "M.Sc Data Science", "seat_count": 30}
            ]
            for c in courses:
                new_c = Course(
                    code=c["code"],
                    name=c["name"],
                    seat_count=c["seat_count"],
                    is_active=True
                )
                db.add(new_c)
            db.commit()
            print("[SUCCESS] Courses seeded successfully!")
        except Exception as course_err:
            print(f"[ERROR] Failed to seed courses: {course_err}")
            db.rollback()
        finally:
            db.close()

        # 3. Seed default admin immediately
        print("Seeding admin account...")
        db = SessionLocal()
        try:
            from app.models import Admin
            hashed_pw = get_password_hash(settings.ADMIN_PASSWORD)
            default_admin = Admin(
                username=settings.ADMIN_USERNAME,
                password_hash=hashed_pw,
                name="Periyar Admin"
            )
            db.add(default_admin)
            db.commit()
            print("[SUCCESS] Admin account seeded successfully!")
        except Exception as seed_err:
            print(f"[ERROR] Failed to seed admin: {seed_err}")
            db.rollback()
        finally:
            db.close()

        print("\nDatabase is fully cleared, courses seeded, and Admin account is ready!")
    except Exception as e:
        print(f"[ERROR] Clear database failed: {e}")
    print("--------------------------------------------------")

if __name__ == "__main__":
    main()
