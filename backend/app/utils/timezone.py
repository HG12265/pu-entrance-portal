import datetime
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")

def now_utc() -> datetime.datetime:
    """Returns the current timezone-aware UTC datetime."""
    return datetime.datetime.now(datetime.timezone.utc)

def to_ist(dt: datetime.datetime) -> datetime.datetime:
    """Converts a naive or aware datetime to timezone-aware IST."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        # Assume naive datetime is in UTC
        dt = dt.replace(tzinfo=datetime.timezone.utc)
    return dt.astimezone(IST)

def parse_admin_ist_datetime(date_str: str, time_str: str) -> datetime.datetime:
    """
    Parses a date string ('YYYY-MM-DD') and time string ('HH:MM') in IST
    and returns a timezone-aware UTC datetime.
    """
    # Parse in naive format
    naive_dt = datetime.datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
    # Localize to IST
    ist_dt = naive_dt.replace(tzinfo=IST)
    # Convert to UTC
    return ist_dt.astimezone(datetime.timezone.utc)

def format_ist_for_response(dt: datetime.datetime) -> str:
    """
    Formats a datetime in IST for API response display.
    Example: '29 June 2026, 10:30 AM IST'
    """
    if dt is None:
        return ""
    ist_dt = to_ist(dt)
    day = ist_dt.strftime("%d").lstrip("0")
    rest = ist_dt.strftime("%B %Y, %I:%M %p IST")
    return f"{day} {rest}"
