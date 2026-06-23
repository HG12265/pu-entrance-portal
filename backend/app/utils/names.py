import re

def are_names_equivalent(name1: str, name2: str) -> bool:
    if name1 is None or name2 is None:
        return False

    def normalize_name(n: str) -> list:
        # Uppercase
        n_up = str(n).upper()
        # Replace non-alphanumeric (like dots and punctuation) with spaces
        cleaned = re.sub(r'[^A-Z0-9\s]', ' ', n_up)
        # Split into tokens (removes multiple spaces and trims)
        return cleaned.split()

    t1 = normalize_name(name1)
    t2 = normalize_name(name2)

    if not t1 or not t2:
        return False

    # Equivalent if the set of tokens is identical (order-independent)
    return set(t1) == set(t2)
