"""Pure Evaluation validation aligned with V1 INTEGER/TEXT constraints.

No database/config access, authentication, routing or result disclosure. API/UI
and role-specific result projections remain subject to the Evaluation contract.
"""

ASCII_SPACE = " \t\n\r\f\v"


def validate_score(value: int) -> int:
    """Accept integer 0..100 without coercing bool, float or numeric strings."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("EVALUATION_SCORE_INTEGER_REQUIRED")
    if not 0 <= value <= 100:
        raise ValueError("EVALUATION_SCORE_OUT_OF_RANGE")
    return value


def validate_comment(value: str) -> str:
    """Match V1 ASCII btrim; preserve inner whitespace and impose no TEXT cap."""
    if not isinstance(value, str):
        raise ValueError("EVALUATION_COMMENT_REQUIRED")
    if "\x00" in value or any(0xD800 <= ord(character) <= 0xDFFF for character in value):
        raise ValueError("EVALUATION_COMMENT_INVALID")
    normalized = value.strip(ASCII_SPACE)
    if not normalized:
        raise ValueError("EVALUATION_COMMENT_REQUIRED")
    return normalized
