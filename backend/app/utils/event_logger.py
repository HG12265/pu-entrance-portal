import json
import datetime
from sqlalchemy.orm import Session
from app.models import ExamAttemptEventLog

def log_event(db: Session, attempt_id: int, candidate_id: int, event_type: str, event_message: str, metadata: dict = None, commit: bool = True):
    try:
        log = ExamAttemptEventLog(
            attempt_id=attempt_id,
            candidate_id=candidate_id,
            event_type=event_type,
            event_message=event_message,
            metadata_json=json.dumps(metadata) if metadata else None,
            created_at=datetime.datetime.utcnow()
        )
        db.add(log)
        if commit:
            db.commit()
        print(f"[EVENT LOGGED] {event_type}: {event_message}")
    except Exception as e:
        if commit:
            db.rollback()
        print(f"[ERROR LOGGING EVENT] {e}")
