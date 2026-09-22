import re
from decimal import Decimal, InvalidOperation


def normalize_record_ref(raw):
    """
    Normalize a system_b record_ref to canonical 'REC-NNNN' format.
    Handles: 'rec1034', ' REC - 1070 ', '1112', and already-canonical 'REC-1001'.
    Raises ValueError for inputs that can't be normalized.
    """
    cleaned = raw.strip()
    if not cleaned:
        raise ValueError(f"Cannot normalize empty record_ref: '{raw}'")

    cleaned = re.sub(r"\s+", "", cleaned)
    cleaned = cleaned.upper()

    if re.fullmatch(r"REC-\d+", cleaned):
        return cleaned

    match = re.fullmatch(r"REC(\d+)", cleaned)
    if match:
        return f"REC-{match.group(1)}"

    if re.fullmatch(r"\d+", cleaned):
        return f"REC-{cleaned}"

    raise ValueError(f"Cannot normalize record_ref: '{raw}'")


def parse_value(raw):
    """
    Parse a value string into a Decimal.
    Returns (Decimal_or_None, warning_string).
    """
    stripped = raw.strip()
    if not stripped:
        return None, "blank_value"

    try:
        return Decimal(stripped), ""
    except (InvalidOperation, ValueError):
        return None, f"unparseable_value: '{raw}'"
