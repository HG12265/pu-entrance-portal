import os
import sys
import datetime
from sqlalchemy.orm import Session

# Add project root to python path to access app module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal
from app.models import Candidate, StudentApplication, Course

def main():
    db = SessionLocal()
    test_mobile = "9998887776"
    test_app_no = "APP-999-TEST"
    
    try:
        # Check if course MCA exists
        mca = db.query(Course).filter(Course.code == "MCA").first()
        if not mca:
            mca = Course(code="MCA", name="Master of Computer Applications", seat_count=30, is_active=True)
            db.add(mca)
            db.commit()
            db.refresh(mca)
            
        # Clean up any existing test student with this mobile
        candidate = db.query(Candidate).filter(Candidate.mobile_number == test_mobile).first()
        if candidate:
            db.query(StudentApplication).filter(StudentApplication.candidate_id == candidate.id).delete()
            db.query(Candidate).filter(Candidate.id == candidate.id).delete()
            db.commit()
            
        # Create candidate
        candidate = Candidate(
            mobile_number=test_mobile,
            full_name="Browser Test Student",
            community="BC",
            has_verified_details=False
        )
        db.add(candidate)
        db.commit()
        db.refresh(candidate)
        
        # Create student application
        app = StudentApplication(
            candidate_id=candidate.id,
            course_id=mca.id,
            application_number=test_app_no,
            mobile_number=test_mobile,
            full_name="Browser Test Student",
            community="BC",
            ug_marks=82.5,
            is_active=True
        )
        db.add(app)
        db.commit()
        
        print(f"SUCCESS: Seeded student candidate with App No: {test_app_no}, Mobile: {test_mobile}")
        
    except Exception as e:
        print(f"Error seeding test student: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    main()
