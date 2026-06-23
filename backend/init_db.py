import pymysql
from app.config import settings
from app.database import engine, Base, SessionLocal
from app.models import Admin
from app.auth import get_password_hash

def init_database():
    print("Checking and creating tables...")
    try:
        # Create all tables using SQLAlchemy Metadata
        Base.metadata.create_all(bind=engine)
        print("All tables checked/created successfully!")
        
        # Seed default admin credentials
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
            else:
                print(f"Admin account '{settings.ADMIN_USERNAME}' already exists.")
        except Exception as e:
            print(f"Error seeding admin account: {e}")
        finally:
            db.close()
            
    except Exception as e:
        print(f"Error initializing database: {e}")

if __name__ == "__main__":
    init_database()
