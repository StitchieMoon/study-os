"""Date parsing and display helpers.

Extracted from app.py without changing the accepted date formats.
Australian DD/MM/YYYY is used for slash-formatted dates.
"""
from datetime import date, datetime


# =========================================================

def parse_homework_date(value):

    if not value:
        return None

    if isinstance(value, datetime):
        return value.date()

    if isinstance(value, date):
        return value

    text = str(value).strip()

    # ISO format is the canonical format stored by SmartStride.
    for fmt in ("%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except (ValueError, TypeError):
            continue

    # SmartStride uses Australian DD/MM/YYYY whenever a slash-formatted date is
    # encountered. This is important for dates such as 09/11/2026, where
    # interpreting the value as MM/DD/YYYY silently changes the due date.
    if "/" in text:
        parts = text.split("/")
        if len(parts) == 3 and all(part.isdigit() for part in parts):
            day, month, year = (int(part) for part in parts)
            try:
                return date(year, month, day)
            except ValueError:
                return None

    return None


def normalise_homework_date(value):

    parsed = parse_homework_date(value)

    if parsed is None:
        return ""

    return parsed.strftime("%Y-%m-%d")


def date_format(value):

    if not value:
        return ""

    parsed = parse_homework_date(value)

    if parsed is not None:
        return parsed.strftime("%d/%m/%Y")

    return str(value)


def homework_date_input(value):

    parsed = parse_homework_date(value)

    if parsed is None:
        return ""

    return parsed.strftime("%Y-%m-%d")
