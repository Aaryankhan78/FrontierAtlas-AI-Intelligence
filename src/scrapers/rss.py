
import feedparser
from datetime import datetime, timezone

from src.utils import parse_date, stable_hash, logger
from src.models import Record


# ==================================================
# NEWS SOURCES - 5
# ==================================================

NEWS_FEEDS = {
    "TechCrunch AI": (
        "https://techcrunch.com/category/artificial-intelligence/feed/"
    ),
    "OpenAI News": (
        "https://openai.com/news/rss.xml"
    ),
    "Google DeepMind": (
        "https://deepmind.google/blog/rss.xml"
    ),
    "Hugging Face Blog": (
        "https://huggingface.co/blog/feed.xml"
    ),
    "MarkTechPost": (
        "https://www.marktechpost.com/feed/"
    ),
}


# ==================================================
# JOB SOURCES - 5
# ==================================================

JOB_FEEDS = {
    "We Work Remotely": (
        "https://weworkremotely.com/categories/remote-programming-jobs.rss"
    ),
    "Himalayas": (
        "https://himalayas.app/jobs/rss"
    ),
    "RemoteFirstJobs AI": (
        "https://remotefirstjobs.com/rss/jobs/ai.rss"
    ),
    "Remotive": (
        "https://remotive.com/remote-jobs/feed"
    ),
    "Jobicy": (
        "https://jobicy.com/?feed=job_feed"
    ),
}


# ==================================================
# AI KEYWORDS
# ==================================================

AI_KEYWORDS = (
    "artificial intelligence",
    "machine learning",
    "deep learning",
    "generative ai",
    "large language model",
    "ai engineer",
    "ai developer",
    "ai researcher",
    "ml engineer",
    "mlops",
    "computer vision",
    "natural language processing",
    "nlp",
    "robotics",
    "data scientist",
    "prompt engineer",
    "agentic",
    "llm",
    "rag",
    "generative model",
    "ai/ml",
)


# ==================================================
# DATE NORMALIZATION
# ==================================================

def _get_published_date(entry):
    """
    Extract publication date and normalize it to UTC.
    Supports RSS and Atom date fields.
    """

    for field in ("published_parsed", "updated_parsed"):
        parsed_value = entry.get(field)

        if parsed_value:
            try:
                return datetime(
                    *parsed_value[:6],
                    tzinfo=timezone.utc,
                )
            except (TypeError, ValueError):
                pass

    raw_date = (
        entry.get("published")
        or entry.get("updated")
        or entry.get("pubDate")
        or entry.get("date")
    )

    if not raw_date:
        return None

    try:
        parsed = parse_date(raw_date)

        if parsed is None:
            return None

        if parsed.tzinfo is None:
            parsed = parsed.replace(
                tzinfo=timezone.utc
            )

        return parsed.astimezone(timezone.utc)

    except (ValueError, TypeError, AttributeError):
        return None


# ==================================================
# DESCRIPTION EXTRACTION
# ==================================================

def _get_description(entry):
    """
    Extract available description or full content.
    """

    content_list = entry.get("content", [])

    if isinstance(content_list, list):
        for item in content_list:
            value = item.get("value", "")

            if value:
                return value

    return (
        entry.get("summary")
        or entry.get("description")
        or ""
    )


# ==================================================
# AI JOB FILTER
# ==================================================

def _is_ai_job(title, description):
    """
    Identify AI and machine-learning related jobs.
    """

    text = f"{title} {description}".lower()

    return any(
        keyword in text
        for keyword in AI_KEYWORDS
    )


# ==================================================
# COMPANY EXTRACTION
# ==================================================

def _get_company(entry, title):
    """
    Extract company name from available feed fields.
    """

    possible_fields = (
        "company",
        "author",
        "himalayasjobs_companyname",
        "himalayasJobs_companyName",
        "company_name",
    )

    for field in possible_fields:
        value = entry.get(field)

        if isinstance(value, str) and value.strip():
            return value.strip()

    # Some job feeds use Company: Job title format.
    if ":" in title:
        return title.split(":", 1)[0].strip()

    return ""


# ==================================================
# ROLE CLASSIFICATION
# ==================================================

def _get_role_family(title, description):
    """
    Classify AI job roles using title and description.
    """

    text = f"{title} {description}".lower()

    engineering_keywords = (
        "engineer",
        "developer",
        "software",
        "programmer",
        "mlops",
    )

    data_keywords = (
        "data scientist",
        "data engineer",
        "data analyst",
    )

    research_keywords = (
        "researcher",
        "research scientist",
        "research engineer",
    )

    if any(word in text for word in research_keywords):
        return "Research"

    if any(word in text for word in data_keywords):
        return "Data Science"

    if any(word in text for word in engineering_keywords):
        return "Engineering"

    return "AI/ML"


# ==================================================
# REMOTE JOB DETECTION
# ==================================================

def _is_remote(title, description, entry):
    """
    Identify remote roles using available feed information.
    """

    text = (
        f"{title} {description} "
        f"{entry.get('location', '')} "
        f"{entry.get('category', '')}"
    ).lower()

    remote_keywords = (
        "remote",
        "work from home",
        "work-from-home",
        "distributed team",
        "anywhere",
    )

    return any(
        keyword in text
        for keyword in remote_keywords
    )


# ==================================================
# MAIN RSS FETCHER
# ==================================================

async def fetch_feed(
    client,
    source_name,
    feed_url,
    record_type,
):
    """
    Fetch and normalize RSS/Atom entries.

    Features:
    - Publication date normalization
    - AI-related job filtering
    - Duplicate URL checking
    - Source attribution
    - Structured record creation
    """

    if record_type not in ("NEWS", "JOB"):
        logger.warning(
            "Unsupported record type: %s",
            record_type,
        )
        return []

    try:
        xml = await client.get_text(feed_url)

        parsed = feedparser.parse(xml)

    except Exception as exc:
        logger.warning(
            "Could not fetch %s: %s",
            source_name,
            exc,
        )
        return []

    if parsed.bozo and not parsed.entries:
        logger.warning(
            "Invalid RSS feed from %s: %s",
            source_name,
            parsed.bozo_exception,
        )
        return []

    if parsed.bozo:
        logger.warning(
            "%s returned a partially malformed feed; "
            "processing available entries",
            source_name,
        )

    output = []
    seen = set()

    for entry in parsed.entries:

        # ------------------------------------------
        # Extract title and URL
        # ------------------------------------------

        link = entry.get("link", "")
        title = entry.get("title", "")

        if not isinstance(link, str):
            continue

        if not isinstance(title, str):
            continue

        link = link.strip()
        title = title.strip()

        if not link or not title:
            continue

        # ------------------------------------------
        # Duplicate checking
        # ------------------------------------------

        if link in seen:
            continue

        seen.add(link)

        # ------------------------------------------
        # Extract description and date
        # ------------------------------------------

        description = _get_description(entry)

        published = _get_published_date(entry)

        if published is None:
            logger.debug(
                "Skipping entry without valid date: %s",
                title,
            )
            continue

        # ------------------------------------------
        # Build JOB record
        # ------------------------------------------

        if record_type == "JOB":

            if not _is_ai_job(title, description):
                continue

            content = {
                "title": title,
                "url": link,
                "description": description,
                "full_text": description,
                "date": published.isoformat(),
                "company": _get_company(entry, title),
                "is_remote": _is_remote(
                    title,
                    description,
                    entry,
                ),
                "role_family": _get_role_family(
                    title,
                    description,
                ),
            }

        # ------------------------------------------
        # Build NEWS record
        # ------------------------------------------

        else:

            content = {
                "title": title,
                "url": link,
                "description": description,
                "full_text": description,
                "date": published.isoformat(),
            }

        # ------------------------------------------
        # Create structured record
        # ------------------------------------------

        output.append(
            Record(
                recordType=record_type,
                source={
                    "name": source_name,
                    "url": feed_url,
                },
                content=content,
                source_hash=stable_hash(link),
            )
        )

    logger.info(
        "%s: collected %d %s records",
        source_name,
        len(output),
        record_type,
    )

    return output
