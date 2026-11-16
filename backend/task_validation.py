"""Pure V1 Task field validation; phase, dates and transitions remain DB rules."""
from datetime import date
import re

ASCII_SPACE = " \t\n\r\f\v"


def task_name(value):
    value = task_text(value)
    value = value.strip(ASCII_SPACE)
    if not value:
        raise ValueError("TASK_NAME_REQUIRED")
    if len(value) > 255:
        raise ValueError("TASK_NAME_TOO_LONG")
    return value


def task_text(value):
    if not isinstance(value, str) or "\x00" in value or any(0xD800 <= ord(c) <= 0xDFFF for c in value):
        raise ValueError("TASK_TEXT_INVALID")
    return value


def task_description(value):
    return None if value is None else task_text(value).strip(ASCII_SPACE) or None


def task_due_date(value):
    if value is None:
        return None
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
        raise ValueError("TASK_DATE_INVALID")
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise ValueError("TASK_DATE_INVALID") from None


def task_status(value):
    if not isinstance(value, str) or value not in ("not_started", "in_progress", "completed"):
        raise ValueError("TASK_STATUS_INVALID")
    return value
