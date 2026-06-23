def normalize_community(c: str) -> str:
    if not c:
        return "OC_SEAT"
    c_up = str(c).upper().strip()
    
    # Remove dots, parentheses, and spaces for matching
    cleaned = c_up.replace(".", "").replace("(", "").replace(")", "").replace(" ", "").replace("&", "").replace("/", "")
    
    if cleaned in ["BCM", "BCMUSLIM"]:
        return "BCM"
    elif cleaned in ["MBC", "MBCDNC", "DNC"]:
        return "MBC"
    elif cleaned in ["SCA"]:
        return "SCA"
    elif cleaned in ["OC", "GENERAL", "UR", "OPEN"]:
        return "OC_SEAT"
    elif cleaned in ["BC", "SC", "ST"]:
        return cleaned
        
    return "OC_SEAT"

def get_community_display(code: str, course_code: str) -> str:
    if not code:
        return "OC"
    code_up = str(code).upper().strip()
    
    if code_up == "OC_SEAT":
        return "OC"
    elif code_up == "OC":
        return "OC"
    elif code_up == "BCM":
        return "BC(M)"
    elif code_up == "SCA":
        return "SC(A)" if course_code == "MSC_CS" else "SCA"
    elif code_up == "MBC":
        return "MBC&DNC" if course_code == "MCA" else "MBC"
        
    return code_up
