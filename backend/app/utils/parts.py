from typing import Tuple

def normalize_question_part(value: str) -> Tuple[str, str, int]:
    """
    Normalizes the input string value representing a question part.
    Returns a tuple of (part_code, part_name, part_order).
    Raises ValueError if part is missing, invalid or unrecognized.
    """
    if not value:
        raise ValueError("Part column value is missing.")
        
    val_clean = str(value).strip().lower()
    
    # Part A: Quantitative Ability
    if val_clean in ["a", "part a", "quantitative ability", "quantitativeability"]:
        return "A", "Quantitative Ability", 1
    # Part B: Analytical Reasoning
    elif val_clean in ["b", "part b", "analytical reasoning", "analyticalreasoning"]:
        return "B", "Analytical Reasoning", 2
    # Part C: Logical Reasoning
    elif val_clean in ["c", "part c", "logical reasoning", "logicalreasoning"]:
        return "C", "Logical Reasoning", 3
    # Part D: Computer Awareness
    elif val_clean in ["d", "part d", "computer awareness", "computerawareness"]:
        return "D", "Computer Awareness", 4
    else:
        raise ValueError(f"Unrecognized part value: '{value}'. Expected values: Part A (Quantitative Ability), Part B (Analytical Reasoning), Part C (Logical Reasoning), Part D (Computer Awareness).")
