
import asyncio
import hashlib
import logging
import random
import re

from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse


# ==================================================
# 1. LOGGING CONFIGURATION
# ==================================================

logging.basicConfig(
    level=logging.INFO,
    format=(
        "%(asctime)s %(levelname)s "
        "%(name)s: %(message)s"
    ),
)

logger = logging.getLogger("frontier_atlas")


# ==================================================
# 2. STABLE HASH
# ==================================================

def stable_hash(value: str) -> str:
    """
    Generate a deterministic SHA256 hash.
    Used for record deduplication.
    """

    if not isinstance(value, str):
        value = str(value or "")

    normalized = value.strip().lower()

    return hashlib.sha256(
        normalized.encode("utf-8")
    ).hexdigest()


# ==================================================
# 3. COMPANY NAME NORMALIZATION
# ==================================================

def normalize_name(name: str) -> str:
    """
    Normalize company names for entity resolution.
    Removes common legal suffixes and special characters.
    """

    if not isinstance(name, str):
        return ""

    name = name.lower().strip()

    suffixes = (
        r"\bprivate\s+limited\b",
        r"\bpvt\.?\s*ltd\.?\b",
        r"\bincorporated\b",
        r"\bcorporation\b",
        r"\blimited\b",
        r"\binc\.?\b",
        r"\bllc\b",
        r"\bltd\.?\b",
        r"\bcorp\.?\b",
        r"\bgmbh\b",
        r"\bplc\b",
    )

    for suffix in suffixes:
        name = re.sub(
            suffix,
            "",
            name,
            flags=re.IGNORECASE,
        )

    return re.sub(
        r"[^a-z0-9]+",
        "",
        name,
    )


# ==================================================
# 4. DATE PARSING
# ==================================================

def parse_date(value: str | None):
    """
    Parse common publication date formats.

    Supported:
    - ISO 8601
    - RSS / RFC 2822
    - Relative dates such as '2 hours ago'
    - Common date formats
    - UTC timezone normalization
    """

    if not value:
        return None

    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(
                tzinfo=timezone.utc
            )

        return value.astimezone(timezone.utc)

    value = str(value).strip()

    if not value:
        return None

    now = datetime.now(timezone.utc)

    # Relative date parsing
    match = re.match(
        r"(\d+)\s+(minute|hour|day|week|month)s?\s+ago",
        value,
        re.IGNORECASE,
    )

    if match:
        number = int(match.group(1))
        unit = match.group(2).lower()

        durations = {
            "minute": timedelta(minutes=number),
            "hour": timedelta(hours=number),
            "day": timedelta(days=number),
            "week": timedelta(weeks=number),
            "month": timedelta(days=30 * number),
        }

        return now - durations[unit]

    # ISO 8601 parsing
    try:
        parsed = datetime.fromisoformat(
            value.replace("Z", "+00:00")
        )

        if parsed.tzinfo is None:
            return parsed.replace(
                tzinfo=timezone.utc
            )

        return parsed.astimezone(timezone.utc)

    except (ValueError, TypeError):
        pass

    # RSS / RFC 2822 date parsing
    try:
        parsed = parsedate_to_datetime(value)

        if parsed.tzinfo is None:
            return parsed.replace(
                tzinfo=timezone.utc
            )

        return parsed.astimezone(timezone.utc)

    except (ValueError, TypeError, OverflowError):
        pass

    # Common date formats
    formats = (
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%d-%m-%Y",
        "%d/%m/%Y",
        "%Y-%m-%d %H:%M:%S",
        "%Y/%m/%d %H:%M:%S",
    )

    for date_format in formats:
        try:
            parsed = datetime.strptime(
                value,
                date_format,
            )

            return parsed.replace(
                tzinfo=timezone.utc
            )

        except ValueError:
            continue

    return None


# ==================================================
# 5. 24-HOUR FRESHNESS FILTER
# ==================================================

def is_fresh(dt, hours=24):
    """
    Return True only if publication date is within
    the specified time window and not in the future.
    """

    if not dt:
        return False

    if not isinstance(dt, datetime):
        dt = parse_date(dt)

    if dt is None:
        return False

    if dt.tzinfo is None:
        dt = dt.replace(
            tzinfo=timezone.utc
        )

    dt = dt.astimezone(timezone.utc)

    now = datetime.now(timezone.utc)

    cutoff = now - timedelta(hours=hours)

    return cutoff <= dt <= now


# ==================================================
# 6. URL HOST EXTRACTION
# ==================================================

def host(url: str) -> str:
    """
    Extract hostname from a URL.
    """

    if not isinstance(url, str):
        return ""

    return urlparse(url).netloc.lower()


# ==================================================
# 7. EXPONENTIAL BACKOFF WITH JITTER
# ==================================================

async def backoff(attempt: int):
    """
    Retry delay with exponential backoff and jitter.
    Maximum delay is 30 seconds.
    """

    attempt = max(0, int(attempt))

    delay = min(
        30,
        (2 ** attempt) + random.random(),
    )

    await asyncio.sleep(delay)
