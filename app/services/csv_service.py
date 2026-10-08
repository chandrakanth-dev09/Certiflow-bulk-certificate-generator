import csv
import io
import re
from typing import Any

from fastapi import UploadFile

from app.core.config import settings

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
REQUIRED_COLUMNS = ("name", "email")


def validate_csv_upload(file: UploadFile) -> tuple[list[dict[str, str]], list[dict[str, Any]]]:
    if file is None or not file.filename:
        raise ValueError("CSV file is required.")
    if not file.filename.lower().endswith(".csv"):
        raise ValueError("Only .csv files are allowed.")

    payload = file.file.read()
    if not payload:
        raise ValueError("Uploaded CSV file is empty.")
    if len(payload) > settings.MAX_CSV_SIZE:
        raise ValueError("Uploaded CSV file exceeds the maximum allowed size.")

    try:
        text = payload.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = payload.decode("latin-1", errors="replace")
    if "\x00" in text:
        raise ValueError("Uploaded CSV contains invalid binary content.")

    try:
        reader = csv.DictReader(io.StringIO(text))
    except csv.Error as exc:
        raise ValueError(f"Malformed CSV: {exc}") from exc

    if not reader.fieldnames:
        raise ValueError("CSV header row is missing.")

    fieldnames = [field.strip().lower() if field else "" for field in reader.fieldnames]
    missing_fields = [field for field in REQUIRED_COLUMNS if field not in fieldnames]
    if missing_fields:
        raise ValueError(f"CSV is missing required columns: {', '.join(missing_fields)}")

    valid_rows: list[dict[str, str]] = []
    errors: list[dict[str, Any]] = []
    seen_emails: set[str] = set()

    for row_number, row in enumerate(reader, start=2):
        if row is None or all((value or "").strip() == "" for value in row.values()):
            continue

        cleaned: dict[str, str] = {}
        for key, value in row.items():
            if key is None:
                errors.append({"row": row_number, "field": "row", "error": "Unexpected extra column(s) found."})
                continue
            cleaned[key.strip().lower()] = (value or "").strip()

        name = cleaned.get("name", "")
        email = cleaned.get("email", "")

        if not name:
            errors.append({"row": row_number, "field": "name", "error": "Name is required."})
        if not email:
            errors.append({"row": row_number, "field": "email", "error": "Email is required."})
        elif not EMAIL_RE.match(email):
            errors.append({"row": row_number, "field": "email", "error": "Invalid email address."})

        normalized_email = email.lower()
        if normalized_email and normalized_email in seen_emails:
            errors.append({"row": row_number, "field": "email", "error": "Duplicate email address found in the CSV."})
        elif normalized_email:
            seen_emails.add(normalized_email)

        if name and email and EMAIL_RE.match(email):
            valid_rows.append({"name": name, "email": email.lower()})

    if errors:
        return valid_rows, errors
    return valid_rows, []
