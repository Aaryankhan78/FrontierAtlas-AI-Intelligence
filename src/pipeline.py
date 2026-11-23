
import asyncio
from collections import defaultdict

from src.scrapers.http import HttpClient
from src.scrapers.rss import (
    NEWS_FEEDS,
    JOB_FEEDS,
    fetch_feed,
)
from src.scrapers.papers import (
    fetch_arxiv,
    enrich_github_stars,
)
from src.scrapers.directories import (
    fetch_yc_startups,
    fetch_all_ai_products,
)
from src.storage import get_store
from src.utils import logger, is_fresh, parse_date
from src.processors.resolution import EntityResolver


# ==================================================
# 1. FETCH NEWS AND JOB FEEDS
# ==================================================

async def _fetch_feeds(client):
    """Fetch all configured news and job feeds concurrently."""

    tasks = []

    for name, url in NEWS_FEEDS.items():
        tasks.append(fetch_feed(client, name, url, "NEWS"))

    for name, url in JOB_FEEDS.items():
        tasks.append(fetch_feed(client, name, url, "JOB"))

    results = await asyncio.gather(
        *tasks,
        return_exceptions=True,
    )

    records = []

    for result in results:
        if isinstance(result, Exception):
            logger.warning("Feed failed: %s", result)
            continue

        if result:
            records.extend(result)

    logger.info("Feed records collected: %d", len(records))
    return records


# ==================================================
# 2. FETCH RESEARCH PAPERS
# ==================================================

async def _fetch_research_papers(client, limit):
    """Fetch arXiv papers and enrich available GitHub metrics."""

    try:
        papers = await fetch_arxiv(client, limit)

        if not papers:
            logger.warning("No research papers were collected")
            return []

        papers = await enrich_github_stars(client, papers)

        logger.info("Research papers collected: %d", len(papers))
        return papers

    except Exception as exc:
        logger.exception("Research paper fetch failed: %s", exc)
        return []


# ==================================================
# 3. FETCH AI STARTUPS
# ==================================================

async def _fetch_startups(client, limit):
    """Fetch AI startups from the YC public dataset."""

    try:
        startups = await fetch_yc_startups(
            client,
            limit=limit,
            ai_only=True,
        )

        logger.info("AI startups collected: %d", len(startups))
        return startups

    except Exception as exc:
        logger.exception("Startup fetch failed: %s", exc)
        return []


# ==================================================
# 4. FETCH AI PRODUCTS FROM ALL SOURCES
# ==================================================

async def _fetch_products(client, limit):
    """Fetch and combine unique AI products from all datasets."""

    try:
        products = await fetch_all_ai_products(
            client,
            limit=limit,
        )

        logger.info(
            "Total unique AI products collected: %d",
            len(products),
        )

        return products

    except Exception as exc:
        logger.exception("Product fetch failed: %s", exc)
        return []


# ==================================================
# 5. FILTER LAST 24 HOURS
# ==================================================

def _filter_fresh_records(records):
    """
    Keep NEWS and JOB records published within the last 24 hours.
    Papers, startups and products are not subject to this filter.
    """

    fresh_records = []

    source_stats = defaultdict(
        lambda: {
            "total": 0,
            "fresh": 0,
            "old": 0,
            "invalid": 0,
        }
    )

    for record in records:
        record_type = record.recordType

        if record_type not in ("NEWS", "JOB"):
            fresh_records.append(record)
            continue

        source_name = record.source.get("name", "Unknown")
        stats = source_stats[source_name]
        stats["total"] += 1

        date_value = record.content.get("date")

        if not date_value:
            stats["invalid"] += 1
            continue

        published_at = parse_date(date_value)

        if published_at is None:
            stats["invalid"] += 1
            continue

        if is_fresh(published_at, hours=24):
            fresh_records.append(record)
            stats["fresh"] += 1
        else:
            stats["old"] += 1

    logger.info("========== 24-HOUR FILTER REPORT ==========")

    for source_name, stats in sorted(source_stats.items()):
        logger.info(
            "%s | Total: %d | Fresh: %d | Old: %d | Invalid: %d",
            source_name,
            stats["total"],
            stats["fresh"],
            stats["old"],
            stats["invalid"],
        )

    total_fresh = sum(s["fresh"] for s in source_stats.values())
    total_old = sum(s["old"] for s in source_stats.values())
    total_invalid = sum(s["invalid"] for s in source_stats.values())

    logger.info(
        "Filter summary | Fresh: %d | Old: %d | Invalid: %d",
        total_fresh,
        total_old,
        total_invalid,
    )

    logger.info("Records after filtering: %d", len(fresh_records))

    return fresh_records


# ==================================================
# 6. ENTITY RESOLUTION
# ==================================================

def _resolve_startup_names(records, resolver):
    """Resolve startup names while preserving original names."""

    for record in records:
        if record.recordType != "STARTUP":
            continue

        original_name = record.content.get("entityName")

        if not original_name:
            continue

        resolved_name = resolver.resolve(original_name)

        record.content["originalEntityName"] = original_name
        record.content["entityName"] = resolved_name

    return records


# ==================================================
# 7. DATABASE SUMMARY
# ==================================================

def _log_database_counts(all_records):
    """Print total stored records by record type."""

    counts = defaultdict(int)

    for record in all_records:
        if hasattr(record, "model_dump"):
            record = record.model_dump()
        elif hasattr(record, "dict"):
            record = record.dict()

        record_type = record.get("recordType", "UNKNOWN")
        counts[record_type] += 1

    counts = dict(counts)

    logger.info("Database record counts: %s", counts)

    total = sum(counts.values())
    logger.info("Total stored records: %d", total)

    return counts


# ==================================================
# 8. MAIN PIPELINE
# ==================================================

async def run_pipeline(
    paper_limit=100,
    startup_limit=1000,
    product_limit=1000,
):
    """
    Execute the complete FrontierAtlas collection pipeline.

    1. Fetch news and job feeds.
    2. Fetch research papers.
    3. Enrich available GitHub metrics.
    4. Fetch AI startups.
    5. Fetch AI products from multiple datasets.
    6. Apply 24-hour filtering to news and jobs.
    7. Resolve startup entities.
    8. Save records.
    9. Generate database summary.
    """

    records = []

    logger.info("Starting FrontierAtlas collection pipeline")

    async with HttpClient() as client:

        # 1. News and jobs
        feed_records = await _fetch_feeds(client)
        records.extend(feed_records)

        # 2. Research papers
        papers = await _fetch_research_papers(
            client,
            paper_limit,
        )
        records.extend(papers)

        # 3. AI startups
        startups = await _fetch_startups(
            client,
            startup_limit,
        )
        records.extend(startups)

        # 4. AI products from all configured datasets
        products = await _fetch_products(
            client,
            product_limit,
        )
        records.extend(products)

    logger.info(
        "Total records collected before filtering: %d",
        len(records),
    )

    # 5. Filter news and jobs
    records = _filter_fresh_records(records)

    # 6. Entity resolution
    resolver = EntityResolver()

    records = _resolve_startup_names(
        records,
        resolver,
    )

    logger.info(
        "Entity mappings generated: %d",
        len(resolver.mapping_log),
    )

    # 7. Save to database
    store = get_store()

    try:
        inserted = store.save_many(records)

        logger.info(
            "Pipeline completed: %d records processed, "
            "%d new records inserted",
            len(records),
            inserted,
        )

        all_records = store.all_records()

        _log_database_counts(all_records)

        return all_records, resolver.mapping_log

    finally:
        store.close()
