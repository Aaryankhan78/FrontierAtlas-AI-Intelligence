
import json
from collections import defaultdict

from src.config import settings


TABS = [
    "Startups",
    "Products",
    "Research Papers",
    "Jobs",
    "News",
    "Entity Mapping Log",
]

BATCH_SIZE = 400


def serialize_value(value):
    """Convert nested values into Google Sheets compatible text."""

    if value is None:
        return ""

    if isinstance(value, (dict, list, tuple)):
        return json.dumps(
            value,
            ensure_ascii=False,
            default=str,
        )

    return str(value)


def flatten(record):
    """Flatten a database record into a spreadsheet row."""

    source = record.get("source") or {}
    content = record.get("content") or {}

    if not isinstance(source, dict):
        source = {}

    if not isinstance(content, dict):
        content = {}

    output = {
        "source_hash": record.get("source_hash", ""),
        "recordType": record.get("recordType", ""),
        "source_name": source.get("name", ""),
        "source_url": source.get("url", ""),
        "collectedAt": record.get("collectedAt", ""),
    }

    output.update(content)

    return {
        key: serialize_value(value)
        for key, value in output.items()
    }


def normalize_mapping(mapping):
    """Convert entity mapping entries into spreadsheet rows."""

    if isinstance(mapping, dict):
        return {
            key: serialize_value(value)
            for key, value in mapping.items()
        }

    return {"mapping": serialize_value(mapping)}


def column_letter(number):
    """Convert a 1-based column number to spreadsheet letters."""

    result = ""

    while number:
        number, remainder = divmod(number - 1, 26)
        result = chr(65 + remainder) + result

    return result


def export_tab(worksheet, rows):
    """Clear and upload one worksheet in manageable batches."""

    worksheet.clear()

    if not rows:
        worksheet.update(
            values=[["No verified records available"]],
            range_name="A1",
        )
        return 0

    # Keep important fields first and sort remaining fields.
    preferred = [
        "source_hash",
        "recordType",
        "productName",
        "entityName",
        "title",
        "startupName",
        "url",
        "source_name",
        "source_url",
        "collectedAt",
    ]

    all_headers = {
        key
        for row in rows
        for key in row.keys()
    }

    headers = [
        key for key in preferred
        if key in all_headers
    ]

    headers.extend(
        sorted(all_headers - set(headers))
    )

    total_columns = len(headers)
    total_rows = len(rows) + 1

    # Expand worksheet if required.
    worksheet.resize(
        rows=max(total_rows, 1),
        cols=max(total_columns, 1),
    )

    worksheet.update(
        values=[headers],
        range_name="A1",
    )

    last_column = column_letter(total_columns)

    # Upload records in batches.
    for start in range(0, len(rows), BATCH_SIZE):

        batch_rows = rows[start:start + BATCH_SIZE]

        values = [
            [row.get(header, "") for header in headers]
            for row in batch_rows
        ]

        start_row = start + 2
        end_row = start_row + len(values) - 1

        worksheet.update(
            values=values,
            range_name=f"A{start_row}:{last_column}{end_row}",
        )

    return len(rows)


def export_google_sheets(records, mapping_log=None):
    """
    Export all six assignment datasets to Google Sheets.
    """

    if not settings.sheets_id:
        raise RuntimeError(
            "GOOGLE_SHEETS_ID is missing from .env"
        )

    if not settings.service_account_json:
        raise RuntimeError(
            "GOOGLE_SERVICE_ACCOUNT_JSON is missing from .env"
        )

    import gspread

    client = gspread.service_account(
        filename=settings.service_account_json
    )

    spreadsheet = client.open_by_key(
        settings.sheets_id
    )

    grouped = defaultdict(list)

    for record in records:

        if hasattr(record, "model_dump"):
            record = record.model_dump()
        elif hasattr(record, "dict"):
            record = record.dict()

        record_type = record.get("recordType")

        if record_type:
            grouped[record_type].append(record)

    datasets = {
        "Startups": [
            flatten(record)
            for record in grouped["STARTUP"]
        ],

        "Products": [
            flatten(record)
            for record in grouped["PRODUCT"]
        ],

        "Research Papers": [
            flatten(record)
            for record in grouped["RESEARCH_PAPER"]
        ],

        "Jobs": [
            flatten(record)
            for record in grouped["JOB"]
        ],

        "News": [
            flatten(record)
            for record in grouped["NEWS"]
        ],

        "Entity Mapping Log": [
            normalize_mapping(item)
            for item in (mapping_log or [])
        ],
    }

    print("\n========== GOOGLE SHEETS EXPORT ==========")

    for title in TABS:

        try:
            worksheet = spreadsheet.worksheet(title)

        except gspread.WorksheetNotFound:
            worksheet = spreadsheet.add_worksheet(
                title=title,
                rows=1000,
                cols=20,
            )

        count = export_tab(
            worksheet,
            datasets[title],
        )

        print(f"{title}: {count} records exported")

    print("\nGoogle Sheets export completed successfully.")

    return True
