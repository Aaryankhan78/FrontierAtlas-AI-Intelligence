
import sqlite3
import json
from urllib.parse import urlsplit, urlunsplit

DB_PATH = "data/intelligence.db"


def canonical_url(url):
    """Normalize URLs for duplicate detection."""

    if not isinstance(url, str):
        return ""

    url = url.strip()

    try:
        parts = urlsplit(url)

        if parts.scheme.lower() not in ("http", "https"):
            return ""

        if not parts.netloc:
            return ""

        return urlunsplit((
            parts.scheme.lower(),
            parts.netloc.lower(),
            parts.path.rstrip("/") or "/",
            parts.query,
            "",
        ))

    except ValueError:
        return ""


def validate_products():

    connection = sqlite3.connect(DB_PATH)
    cursor = connection.cursor()

    cursor.execute(
        "SELECT source_hash, payload FROM records "
        "WHERE record_type = ?",
        ("PRODUCT",),
    )

    rows = cursor.fetchall()

    total = len(rows)
    valid_names = 0
    valid_urls = 0
    missing_names = 0
    missing_urls = 0
    missing_sources = 0
    invalid_urls = 0

    seen_urls = set()
    duplicate_urls = 0

    source_counts = {}

    invalid_examples = []
    missing_examples = []

    for source_hash, payload in rows:

        try:
            record = json.loads(payload)
        except (json.JSONDecodeError, TypeError):
            invalid_urls += 1
            continue

        content = record.get("content", {})
        source = record.get("source", {})

        if not isinstance(content, dict):
            content = {}

        if not isinstance(source, dict):
            source = {}

        # Product name validation
        name = content.get("productName")

        if isinstance(name, str) and name.strip():
            valid_names += 1
        else:
            missing_names += 1
            missing_examples.append(str(source_hash))

        # Product URL validation
        url = content.get("url")
        normalized = canonical_url(url)

        if normalized:
            valid_urls += 1

            if normalized in seen_urls:
                duplicate_urls += 1
            else:
                seen_urls.add(normalized)

        else:
            if url:
                invalid_urls += 1
                invalid_examples.append(str(url))
            else:
                missing_urls += 1

        # Source attribution validation
        source_name = (
            source.get("name")
            or content.get("sourceAttribution")
        )

        if isinstance(source_name, str) and source_name.strip():
            source_counts[source_name] = (
                source_counts.get(source_name, 0) + 1
            )
        else:
            missing_sources += 1

    connection.close()

    print("\n========== PRODUCT VALIDATION ==========")

    print(f"Total product records: {total}")
    print(f"Valid product names: {valid_names}")
    print(f"Missing product names: {missing_names}")
    print(f"Valid product URLs: {valid_urls}")
    print(f"Missing product URLs: {missing_urls}")
    print(f"Invalid product URLs: {invalid_urls}")
    print(f"Duplicate product URLs: {duplicate_urls}")
    print(f"Missing source attribution: {missing_sources}")

    print("\n========== SOURCE-WISE COUNTS ==========")

    for source_name, count in sorted(source_counts.items()):
        print(f"{source_name}: {count}")

    if invalid_examples:
        print("\nInvalid URL examples:")
        for value in invalid_examples[:5]:
            print("-", value)

    if missing_examples:
        print("\nRecords with missing names (source hashes):")
        for value in missing_examples[:5]:
            print("-", value)

    print("\n========== VALIDATION COMPLETE ==========")

    if (
        total == 1000
        and missing_names == 0
        and missing_urls == 0
        and invalid_urls == 0
        and duplicate_urls == 0
        and missing_sources == 0
    ):
        print("All basic product validation checks passed.")
    else:
        print("Some checks need attention. Review the counts above.")


if __name__ == "__main__":
    validate_products()
