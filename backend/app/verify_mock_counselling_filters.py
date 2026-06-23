import os
import sys

# Add project root to python path to access app module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal
from app.routers.results import get_course_rankings_internal

def main():
    db = SessionLocal()
    try:
        print("[TEST] Fetching mock counselling rankings for MCA...")
        mca_rankings = get_course_rankings_internal(db, "MCA", show_excluded=True)
        
        # Verify candidates exist
        assert len(mca_rankings) >= 6, f"Expected at least 6 mock candidates in rankings, got {len(mca_rankings)}"
        print(f"[TEST] Found {len(mca_rankings)} MCA candidates in rankings.")

        # Find our mock candidates
        mock_entries = [r for r in mca_rankings if r["student_name"].startswith("MOCK Candidate")]
        assert len(mock_entries) == 6, f"Expected 6 MOCK candidates, got {len(mock_entries)}"
        print("[TEST] Successfully retrieved all 6 seeded MOCK candidates.")

        # Verify no mock candidate is marked with Incomplete UG Percentage
        for r in mock_entries:
            print(f"- {r['student_name']}: UG % = {r['ug_percentage']}, Final Score = {r['final_score']}, Status = {r['confirmation_status']}")
            assert r["confirmation_status"] != "Incomplete UG Percentage", f"Candidate {r['student_name']} has Incomplete UG Percentage, but it was seeded!"
            assert r["final_score"] is not None, f"Candidate {r['student_name']} final score is None, but it was seeded!"

        print("[TEST] SUCCESS: verify_mock_counselling_filters passed successfully!")

    except AssertionError as ae:
        print(f"[TEST] FAILED: AssertionError: {ae}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"[TEST] FAILED: Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        db.close()

if __name__ == "__main__":
    main()
