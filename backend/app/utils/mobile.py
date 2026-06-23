import re

def normalize_mobile(m) -> str:
    if m is None:
        return ""
    s = str(m).strip()
    # Handle floats like 6383528252.0 by removing trailing '.0'
    if s.endswith('.0'):
        s = s[:-2]
    # Retain only digits
    digits = re.sub(r'\D', '', s)
    # Return last 10 digits
    return digits[-10:] if len(digits) >= 10 else digits
