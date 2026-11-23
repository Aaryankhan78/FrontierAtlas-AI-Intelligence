
import json
from urllib.parse import urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup

from src.models import Record
from src.utils import stable_hash, logger


# ==================================================
# DATA SOURCES
# ==================================================

YC_COMPANIES_URL = (
    "https://yc-oss.github.io/api/companies/all.json"
)

SUBMITMYSAAS_API = (
    "https://submitmysaas.com/api/public/products"
)

TIORAI_JSON_URL = (
    "https://raw.githubusercontent.com/"
    "tioraicom/ai-tools-dataset/main/data/ai-tools.json"
)

HARPD_PRODUCTS_URL = (
    "https://raw.githubusercontent.com/"
    "harpd-dev/harpd-ai-datasets/main/data/products/products.json"
)

GLOBAL_AI_INDEX_URL = (
    "https://globalaiproductindex.com/api/products.json"
)

AI_USE_CASES_URL = (
    "https://aiusecases.dev/data.json"
)


# ==================================================
# GENERAL HELPERS
# ==================================================

def _as_list(data):
    """Normalize common JSON catalog response shapes."""

    if isinstance(data, list):
        return data

    if isinstance(data, dict):
        for key in (
            "products",
            "tools",
            "companies",
            "data",
            "results",
            "items",
        ):
            value = data.get(key)

            if isinstance(value, list):
                return value

    return []


def _first_text(item, *keys):
    """Return the first available non-empty string."""

    if not isinstance(item, dict):
        return ""

    for key in keys:
        value = item.get(key)

        if isinstance(value, str) and value.strip():
            return value.strip()

    return ""


def _absolute_url(value, base_url):
    """Convert relative URLs to absolute URLs."""

    if not isinstance(value, str) or not value.strip():
        return None

    value = value.strip()

    if value.startswith(("http://", "https://")):
        return value

    if value.startswith("/"):
        return urljoin(base_url, value)

    return None


def _canonical_url(url):
    """Normalize URLs for duplicate detection."""

    if not isinstance(url, str):
        return ""

    url = url.strip()

    if not url.startswith(("http://", "https://")):
        return ""

    parts = urlsplit(url)

    return urlunsplit((
        parts.scheme.lower(),
        parts.netloc.lower(),
        parts.path.rstrip("/") or "/",
        parts.query,
        "",
    ))


def _normalize_pricing(value):
    """Normalize known pricing labels."""

    if isinstance(value, list):
        value = " ".join(str(x) for x in value)

    if not isinstance(value, str):
        return None

    value = value.strip().lower()

    if "freemium" in value:
        return "FREEMIUM"

    if "free trial" in value:
        return "FREE_TRIAL"

    if "open source" in value or value == "open":
        return "OPEN_SOURCE"

    if "free" in value:
        return "FREE"

    if "paid" in value:
        return "PAID"

    if "enterprise" in value:
        return "ENTERPRISE"

    return None


# ==================================================
# AI STARTUP FILTER
# ==================================================

def _is_ai_startup(company):
    """Identify AI-related startup records."""

    tags = company.get("tags", [])

    if not isinstance(tags, list):
        tags = []

    text = " ".join([
        str(company.get("name", "")),
        str(company.get("one_liner", "")),
        str(company.get("long_description", "")),
        str(company.get("industry", "")),
        str(company.get("subindustry", "")),
        " ".join(str(tag) for tag in tags),
    ]).lower()

    keywords = (
        "artificial intelligence",
        "machine learning",
        "generative ai",
        "llm",
        "large language model",
        "deep learning",
        "computer vision",
        "natural language",
        "ai ",
        " ai",
        "agentic",
        "robotics",
    )

    return any(keyword in text for keyword in keywords)


# ==================================================
# Y COMBINATOR STARTUPS
# ==================================================

async def fetch_yc_startups(client, limit=1000, ai_only=True):
    """Fetch public YC company records."""

    try:
        raw = await client.get_text(YC_COMPANIES_URL)
        data = json.loads(raw)
    except Exception as exc:
        logger.exception("YC startup dataset failed: %s", exc)
        return []

    companies = _as_list(data)
    records = []
    seen = set()

    for company in companies:

        if not isinstance(company, dict):
            continue

        name = _first_text(company, "name")
        slug = _first_text(company, "slug")

        if not name or not slug:
            continue

        if ai_only and not _is_ai_startup(company):
            continue

        profile_url = (
            f"https://www.ycombinator.com/companies/{slug}"
        )

        if profile_url in seen:
            continue

        seen.add(profile_url)

        team_size = company.get("team_size")

        if not isinstance(team_size, int):
            team_size = None

        website = _absolute_url(
            company.get("website"),
            profile_url,
        )

        records.append(
            Record(
                recordType="STARTUP",
                source={
                    "name": "Y Combinator public directory",
                    "url": YC_COMPANIES_URL,
                },
                content={
                    "entityName": name,
                    "url": website,
                    "description": _first_text(
                        company,
                        "long_description",
                        "one_liner",
                    ),
                    "oneLiner": _first_text(
                        company,
                        "one_liner",
                    ),
                    "industry": company.get("industry"),
                    "tags": company.get("tags", []),
                    "batch": company.get("batch"),
                    "status": company.get("status"),
                    "location": company.get("all_locations"),
                    "data": {
                        "employeeCount": team_size,
                    },
                },
                source_hash=stable_hash(profile_url),
            )
        )

        if len(records) >= limit:
            break

    logger.info(
        "YC startup source: collected %d records (AI filter=%s)",
        len(records),
        ai_only,
    )

    return records


# ==================================================
# PRODUCT RECORD NORMALIZATION
# ==================================================

def _normalize_product(
    item,
    source_name,
    dataset_url,
    base_url=None,
):
    """Convert different product schemas into common records."""

    if not isinstance(item, dict):
        return None

    name = _first_text(
        item,
        "name",
        "title",
        "product_name",
        "productName",
    )

    raw_url = _first_text(
        item,
        "official_url",
        "website",
        "website_url",
        "url",
        "product_url",
        "canonical_url",
        "link",
    )

    if not name or not raw_url:
        return None

    product_url = _absolute_url(
        raw_url,
        base_url or dataset_url,
    )

    if not product_url:
        return None

    product_url = _canonical_url(product_url)

    if not product_url:
        return None

    company = _first_text(
        item,
        "company",
        "company_name",
        "startup_name",
        "maker_name",
        "maker",
        "vendor",
    )

    description = _first_text(
        item,
        "short_description",
        "description",
        "tagline",
        "one_liner",
    )

    category = _first_text(
        item,
        "primary_category",
        "secondary_category",
        "category",
        "industry",
    )

    pricing = _normalize_pricing(
        item.get("pricing_model")
        or item.get("business_model")
        or item.get("pricing")
    )

    content = {
        "productName": name,
        "startupName": company or None,
        "url": product_url,
        "description": description,
        "pricingModel": pricing,
        "category": category or None,
        "sourceAttribution": source_name,
    }

    optional_fields = {
        "platform": "platform",
        "tags": "tags",
        "lastVerified": "last_verified",
        "sourceUpdatedAt": "updated",
        "references": "sources",
        "openSource": "open_source",
        "apiAvailable": "api_available",
    }

    for output_key, input_key in optional_fields.items():
        if item.get(input_key) is not None:
            content[output_key] = item[input_key]

    return Record(
        recordType="PRODUCT",
        source={
            "name": source_name,
            "url": dataset_url,
        },
        content=content,
        source_hash=stable_hash(product_url),
    )


# ==================================================
# JSON DATASET FETCHER
# ==================================================

async def _fetch_json_catalog(
    client,
    source_name,
    dataset_url,
    limit=1000,
    base_url=None,
):
    """Fetch a public JSON catalog and normalize products."""

    try:
        raw = await client.get_text(dataset_url)
        payload = json.loads(raw)

    except Exception as exc:
        logger.exception(
            "%s dataset failed: %s",
            source_name,
            exc,
        )
        return []

    items = _as_list(payload)

    if not items:
        logger.warning(
            "%s returned no recognized product list",
            source_name,
        )
        return []

    records = []
    seen = set()

    for item in items:

        record = _normalize_product(
            item,
            source_name,
            dataset_url,
            base_url=base_url,
        )

        if record is None:
            continue

        product_url = record.content["url"]

        if product_url in seen:
            continue

        seen.add(product_url)
        records.append(record)

        if len(records) >= limit:
            break

    logger.info(
        "%s: collected %d products from %d source entries",
        source_name,
        len(records),
        len(items),
    )

    return records


# ==================================================
# SUBMITMYSAAS PRODUCTS
# ==================================================

async def fetch_submitmysaas_products(client, limit=1000):
    """Fetch products from SubmitMySaaS."""

    records = []
    seen = set()
    page = 1

    max_pages = (limit + 23) // 24 + 2

    while len(records) < limit and page <= max_pages:

        page_url = (
            f"{SUBMITMYSAAS_API}?category=ai&page={page}"
        )

        try:
            raw = await client.get_text(page_url)
            payload = json.loads(raw)

        except Exception as exc:
            logger.warning(
                "SubmitMySaaS page %d failed: %s",
                page,
                exc,
            )
            break

        items = _as_list(payload)

        if not items:
            logger.info(
                "SubmitMySaaS page %d returned no products",
                page,
            )
            break

        added_this_page = 0

        for item in items:

            record = _normalize_product(
                item,
                "SubmitMySaaS",
                page_url,
                base_url="https://submitmysaas.com",
            )

            if record is None:
                continue

            product_url = record.content["url"]

            if product_url in seen:
                continue

            seen.add(product_url)
            records.append(record)
            added_this_page += 1

            if len(records) >= limit:
                break

        logger.info(
            "SubmitMySaaS page %d: %d valid products",
            page,
            added_this_page,
        )

        if added_this_page == 0:
            break

        page += 1

    logger.info(
        "SubmitMySaaS total: collected %d products",
        len(records),
    )

    return records


# ==================================================
# TIORAI AI TOOLS DATASET
# ==================================================

async def fetch_tiorai_products(client, limit=1000):
    """Fetch TiorAI AI tools dataset."""

    return await _fetch_json_catalog(
        client,
        "TiorAI AI Tools Dataset",
        TIORAI_JSON_URL,
        limit=limit,
    )


# ==================================================
# HARPd AI PRODUCTS DATASET
# ==================================================

async def fetch_harpd_products(client, limit=1000):
    """Fetch Harpd AI products dataset."""

    return await _fetch_json_catalog(
        client,
        "Harpd AI Product Dataset",
        HARPD_PRODUCTS_URL,
        limit=limit,
    )


# ==================================================
# GLOBAL AI PRODUCT INDEX
# ==================================================

async def fetch_global_ai_products(client, limit=1000):
    """Fetch Global AI Product Index records."""

    return await _fetch_json_catalog(
        client,
        "Global AI Product Index",
        GLOBAL_AI_INDEX_URL,
        limit=limit,
        base_url="https://globalaiproductindex.com",
    )


# ==================================================
# AI USE CASES DATASET
# ==================================================

async def fetch_ai_use_cases_products(client, limit=1000):
    """Fetch AI Use Cases catalog."""

    return await _fetch_json_catalog(
        client,
        "AI Use Cases",
        AI_USE_CASES_URL,
        limit=limit,
        base_url="https://aiusecases.dev",
    )


# ==================================================
# COMBINE ALL PRODUCT SOURCES
# ==================================================

async def fetch_all_ai_products(client, limit=1000):
    """
    Collect products from all configured public datasets.

    All sources are attempted, even if an earlier source
    already supplies the requested number of records.

    Products are deduplicated using canonical URLs.
    """

    sources = [
        fetch_submitmysaas_products,
        fetch_harpd_products,
        fetch_tiorai_products,
        fetch_global_ai_products,
        fetch_ai_use_cases_products,
    ]

    all_records = []
    seen_urls = set()

    for fetcher in sources:

        remaining = max(limit - len(all_records), 0)

        # Request one record for source validation if
        # the overall limit has already been reached.
        source_limit = max(remaining, 1)

        try:
            source_records = await fetcher(
                client,
                limit=source_limit,
            )

        except Exception as exc:
            logger.exception(
                "Product source %s failed: %s",
                fetcher.__name__,
                exc,
            )
            continue

        added = 0
        duplicates = 0

        for record in source_records:

            product_url = _canonical_url(
                record.content.get("url", "")
            )

            if not product_url:
                continue

            if product_url in seen_urls:
                duplicates += 1
                continue

            if len(all_records) >= limit:
                continue

            seen_urls.add(product_url)
            all_records.append(record)
            added += 1

        logger.info(
            "%s | fetched: %d | added: %d | duplicates: %d",
            fetcher.__name__,
            len(source_records),
            added,
            duplicates,
        )

    logger.info(
        "Combined product collection: %d unique products",
        len(all_records),
    )

    return all_records


# ==================================================
# GENERIC HTML DIRECTORY SCRAPER
# ==================================================

async def scrape_directory(
    client,
    source_name: str,
    url: str,
    record_type: str,
    selectors: dict,
):
    """Generic HTML directory scraper."""

    try:
        html = await client.get_text(url)
    except Exception as exc:
        logger.exception(
            "%s directory request failed: %s",
            source_name,
            exc,
        )
        return []

    soup = BeautifulSoup(html, "html.parser")

    records = []
    seen = set()

    for card in soup.select(
        selectors.get("card", "article")
    ):

        name_node = card.select_one(
            selectors.get("name", "h2, h3, a")
        )

        if not name_node:
            continue

        name = name_node.get_text(" ", strip=True)

        link_node = card.select_one("a[href]")

        if not name or not link_node:
            continue

        link = urljoin(
            url,
            link_node.get("href", ""),
        )

        if not link.startswith(("http://", "https://")):
            continue

        canonical_link = _canonical_url(link)

        if not canonical_link or canonical_link in seen:
            continue

        seen.add(canonical_link)

        records.append(
            Record(
                recordType=record_type,
                source={
                    "name": source_name,
                    "url": url,
                },
                content={
                    "entityName": name,
                    "url": canonical_link,
                },
                source_hash=stable_hash(canonical_link),
            )
        )

    logger.info(
        "%s: collected %d records",
        source_name,
        len(records),
    )

    return records
