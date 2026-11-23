
import os
import re
import asyncio
import aiohttp
import xml.etree.ElementTree as ET

from urllib.parse import urlparse

from src.models import Record
from src.utils import stable_hash, logger


ARXIV_API = (
    "https://export.arxiv.org/api/query?"
    "search_query=cat:cs.AI&start=0&max_results={limit}"
    "&sortBy=submittedDate&sortOrder=descending"
)

ATOM_NS = "http://www.w3.org/2005/Atom"
ARXIV_NS = "http://arxiv.org/schemas/atom"

GITHUB_PATTERN = re.compile(
    r"https?://(?:www\.)?github\.com/"
    r"([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)",
    re.IGNORECASE
)


def find_github_repo(text):
    if not text:
        return None

    match = GITHUB_PATTERN.search(text)

    if not match:
        return None

    owner = match.group(1)
    repo = match.group(2).rstrip(".,;:)")

    ignored = {
        "issues", "pull", "pulls",
        "orgs", "features", "topics"
    }

    if repo.lower() in ignored:
        return None

    return f"https://github.com/{owner}/{repo}"


async def fetch_arxiv(client, limit=1000):
    limit = max(1, min(int(limit), 2000))

    xml = await client.get_text(
        ARXIV_API.format(limit=limit)
    )

    root = ET.fromstring(xml)

    ns = {
        "a": ATOM_NS,
        "arxiv": ARXIV_NS
    }

    records = []

    for item in root.findall("a:entry", ns):
        title = " ".join(
            item.findtext(
                "a:title", default="", namespaces=ns
            ).split()
        )

        paper_url = item.findtext(
            "a:id", default="", namespaces=ns
        )

        published = item.findtext(
            "a:published", default="", namespaces=ns
        )

        abstract = " ".join(
            item.findtext(
                "a:summary", default="", namespaces=ns
            ).split()
        )

        authors = [
            author.findtext(
                "a:name", default="", namespaces=ns
            )
            for author in item.findall("a:author", ns)
        ]

        comment = item.findtext(
            "arxiv:comment", default="", namespaces=ns
        )

        if not title or not paper_url:
            continue

        source_text = abstract + " " + comment
        github_url = find_github_repo(source_text)

        records.append(
            Record(
                recordType="RESEARCH_PAPER",
                source={
                    "name": "arXiv",
                    "url": paper_url
                },
                content={
                    "title": title,
                    "authors": authors,
                    "paper_url": paper_url,
                    "abstract": abstract,
                    "github_url": github_url,
                    "github_stars": None,
                    "published_date": published
                },
                source_hash=stable_hash(paper_url)
            )
        )

    logger.info("Fetched %d papers from arXiv", len(records))

    return records


async def fetch_github_repo(session, semaphore, record):
    repo_url = record.content.get("github_url")

    if not repo_url:
        record.content["github_stars"] = None
        return

    parsed = urlparse(repo_url)

    if parsed.netloc.lower() not in {
        "github.com", "www.github.com"
    }:
        record.content["github_stars"] = None
        return

    parts = [
        part for part in parsed.path.split("/") if part
    ]

    if len(parts) != 2:
        record.content["github_stars"] = None
        return

    owner, repo = parts
    repo = repo.removesuffix(".git")

    api_url = (
        f"https://api.github.com/repos/{owner}/{repo}"
    )

    async with semaphore:
        for attempt in range(3):
            try:
                async with session.get(api_url) as response:

                    if response.status == 200:
                        data = await response.json()

                        record.content["github_url"] = data.get(
                            "html_url", repo_url
                        )

                        record.content["github_stars"] = data.get(
                            "stargazers_count"
                        )

                        return

                    if response.status == 404:
                        logger.info(
                            "GitHub repository not found: %s",
                            repo_url
                        )
                        record.content["github_stars"] = None
                        return

                    if response.status == 403:
                        logger.warning(
                            "GitHub API rate limit or access denied"
                        )
                        record.content["github_stars"] = None
                        return

                    if response.status == 429 or response.status >= 500:
                        await asyncio.sleep(2 ** attempt)
                        continue

                    logger.warning(
                        "GitHub API status %s: %s",
                        response.status,
                        repo_url
                    )
                    record.content["github_stars"] = None
                    return

            except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
                logger.warning(
                    "GitHub request failed for %s: %s",
                    repo_url,
                    exc
                )
                await asyncio.sleep(2 ** attempt)

        record.content["github_stars"] = None


async def enrich_github_stars(client, records):
    token = os.getenv("GITHUB_TOKEN", "").strip()

    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "FrontierAtlas-AI-Research"
    }

    if token:
        headers["Authorization"] = f"Bearer {token}"

    timeout = aiohttp.ClientTimeout(total=25)

    semaphore = asyncio.Semaphore(5)

    async with aiohttp.ClientSession(
        headers=headers,
        timeout=timeout
    ) as session:

        tasks = [
            fetch_github_repo(session, semaphore, record)
            for record in records
        ]

        await asyncio.gather(*tasks)

    verified = sum(
        isinstance(record.content.get("github_stars"), int)
        for record in records
    )

    logger.info(
        "GitHub enrichment completed: %d verified metrics out of %d papers",
        verified,
        len(records)
    )

    return records
