import re
from datetime import datetime, timezone, timedelta

MSK = timezone(timedelta(hours=3))


def normalize_phone(phone: str) -> str:
    """Strip non-digits, return last 10 digits."""
    digits = re.sub(r"\D", "", phone)
    return digits[-10:] if len(digits) >= 10 else digits


def extract_inn(text: str) -> tuple[str | None, int]:
    """Find 12-digit INN in text.

    Returns (inn_or_None, max_digit_sequence_length).
    """
    sequences = re.findall(r"\d+", text)
    if not sequences:
        return None, 0
    max_len = max(len(s) for s in sequences)
    for s in sequences:
        if len(s) == 12:
            return s, max_len
    return None, max_len


def moscow_now() -> str:
    """Current Moscow time as ISO string."""
    return datetime.now(MSK).strftime("%Y-%m-%d %H:%M:%S")
