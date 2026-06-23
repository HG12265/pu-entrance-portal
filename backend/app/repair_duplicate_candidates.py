import os
import sys
import argparse
from collections import defaultdict

# Setup python path to include backend dir
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.dirname(current_dir)
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

# Handle running on host vs docker
if not os.environ.get("DATABASE_HOST"):
    os.environ["DATABASE_HOST"] = "localhost"
    os.environ["DATABASE_PORT"] = "3307"
    os.environ["DATABASE_USER"] = "root"
    os.environ["DATABASE_PASSWORD"] = "PeriyarDbRootPassword2026!"
    os.environ["DATABASE_NAME"] = "periyar_entrance_exam"

from sqlalchemy import text
from sqlalchemy.orm import Session
from app.database import engine, SessionLocal
from app.models import Candidate, StudentApplication, ExamAttempt, StudentAnswer
from app.utils.mobile import normalize_mobile

def main():
    parser = argparse.ArgumentParser(description="Repair and merge duplicate candidates with the same normalized mobile.")
    parser.add_argument("--commit", action="store_true", help="Commit the changes to the database. If not specified, runs as a dry-run.")
    args = parser.parse_args()

    db: Session = SessionLocal()
    try:
        # Load all candidates
        candidates = db.query(Candidate).all()
        print(f"Total candidate records found in database: {len(candidates)}")

        # Group by normalized mobile number
        mobile_groups = defaultdict(list)
        for cand in candidates:
            norm_m = normalize_mobile(cand.mobile_number)
            
            # Apply normalization update to the candidate record if it's different in DB
            if cand.mobile_number != norm_m:
                print(f"Normalizing candidate ID {cand.id} mobile from '{cand.mobile_number}' to '{norm_m}'")
                cand.mobile_number = norm_m
            
            mobile_groups[norm_m].append(cand)

        duplicate_groups = {m: list(sorted(cands, key=lambda c: c.id)) for m, cands in mobile_groups.items() if len(cands) > 1}

        if not duplicate_groups:
            print("\nNo duplicate candidates found based on normalized mobile numbers.")
            if args.commit:
                db.commit()
                print("Any mobile normalization updates committed.")
            return

        print(f"\nFound {len(duplicate_groups)} mobile numbers with duplicate candidate records.")
        print("==================================================")
        print("MERGE ACTION SUMMARY")
        print("==================================================")

        for mobile, group in duplicate_groups.items():
            primary = group[0]
            duplicates = group[1:]
            print(f"\nNormalized Mobile: {mobile}")
            print(f" -> KEEP Primary Candidate: ID={primary.id}, Name='{primary.full_name}'")
            for dup in duplicates:
                print(f" -> MERGE Duplicate Candidate: ID={dup.id}, Name='{dup.full_name}'")

                # Applications details
                apps = db.query(StudentApplication).filter(StudentApplication.candidate_id == dup.id).all()
                for app in apps:
                    conflict = db.query(StudentApplication).filter(
                        StudentApplication.candidate_id == primary.id,
                        StudentApplication.course_id == app.course_id
                    ).first()
                    if conflict:
                        print(f"    * App No '{app.application_number}' (Course ID {app.course_id}) conflicts with Primary's App No '{conflict.application_number}'. Details will be merged, duplicate app deleted.")
                    else:
                        print(f"    * Move App No '{app.application_number}' (Course ID {app.course_id}) to Primary.")

                # Exam attempts details
                attempts = db.query(ExamAttempt).filter(ExamAttempt.candidate_id == dup.id).all()
                for att in attempts:
                    conflict_att = db.query(ExamAttempt).filter(
                        ExamAttempt.candidate_id == primary.id,
                        ExamAttempt.exam_id == att.exam_id
                    ).first()
                    if conflict_att:
                        print(f"    * Exam Attempt ID {att.id} (Submitted={att.is_submitted}, Score={att.score}) conflicts with Primary's Attempt ID {conflict_att.id} (Submitted={conflict_att.is_submitted}, Score={conflict_att.score}). Better attempt will be kept.")
                    else:
                        print(f"    * Move Exam Attempt ID {att.id} to Primary.")

        # Process the merge
        for mobile, group in duplicate_groups.items():
            primary = group[0]
            duplicates = group[1:]

            for dup in duplicates:
                # Merge Candidate details if empty in primary
                if not primary.email and dup.email:
                    primary.email = dup.email
                if not primary.community and dup.community:
                    primary.community = dup.community
                if not primary.date_of_birth and dup.date_of_birth:
                    primary.date_of_birth = dup.date_of_birth

                # Reassign/Merge applications
                apps = db.query(StudentApplication).filter(StudentApplication.candidate_id == dup.id).all()
                for app in apps:
                    conflict = db.query(StudentApplication).filter(
                        StudentApplication.candidate_id == primary.id,
                        StudentApplication.course_id == app.course_id
                    ).first()
                    if conflict:
                        # Copy details if missing in conflict app
                        if conflict.ug_marks is None and app.ug_marks is not None:
                            conflict.ug_marks = app.ug_marks
                        if not conflict.email and app.email:
                            conflict.email = app.email
                        if not conflict.community and app.community:
                            conflict.community = app.community
                        # Delete the duplicate app record
                        db.delete(app)
                    else:
                        db.execute(
                            text("UPDATE student_applications SET candidate_id = :pid WHERE id = :aid"),
                            {"pid": primary.id, "aid": app.id}
                        )

                # Reassign/Merge attempts
                attempts = db.query(ExamAttempt).filter(ExamAttempt.candidate_id == dup.id).all()
                for att in attempts:
                    conflict_att = db.query(ExamAttempt).filter(
                        ExamAttempt.candidate_id == primary.id,
                        ExamAttempt.exam_id == att.exam_id
                    ).first()
                    if conflict_att:
                        # Pick the best attempt (submitted prioritised, then higher score)
                        keep_dup = False
                        if att.is_submitted and not conflict_att.is_submitted:
                            keep_dup = True
                        elif not att.is_submitted and conflict_att.is_submitted:
                            keep_dup = False
                        else:
                            if (att.score or 0) > (conflict_att.score or 0):
                                keep_dup = True

                        if keep_dup:
                            db.delete(conflict_att)
                            db.flush()
                            db.execute(
                                text("UPDATE exam_attempts SET candidate_id = :pid WHERE id = :atid"),
                                {"pid": primary.id, "atid": att.id}
                            )
                        else:
                            db.delete(att)
                    else:
                        db.execute(
                            text("UPDATE exam_attempts SET candidate_id = :pid WHERE id = :atid"),
                            {"pid": primary.id, "atid": att.id}
                        )

                db.flush()
                # Safe to delete duplicate candidate using raw SQL to bypass cascades
                db.execute(
                    text("DELETE FROM candidates WHERE id = :did"),
                    {"did": dup.id}
                )

        print("\n==================================================")
        if args.commit:
            db.commit()
            print("SUCCESS: Duplicate candidates successfully merged and committed!")
        else:
            db.rollback()
            print("DRY-RUN COMPLETE: Changes rolled back. Use '--commit' to apply changes.")
        print("==================================================")

    except Exception as e:
        db.rollback()
        print(f"Error executing repair utility: {e}", file=sys.stderr)
    finally:
        db.close()

if __name__ == "__main__":
    main()
