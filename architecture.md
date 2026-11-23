# FrontierAtlas – AI Intelligence Ingestion Pipeline

## System Architecture & Technical Design

### 1. System Overview

FrontierAtlas is an asynchronous, source-backed AI intelligence ingestion pipeline designed to collect, normalize, validate, deduplicate, and store information from multiple public sources.

The system collects five categories:

- AI Startups
- AI Products
- Research Papers
- AI Jobs
- AI News

It uses asynchronous HTTP collection, source-specific scrapers, structured data normalization, freshness filtering, entity resolution, and persistent storage.

### 2. High-Level Architecture

The pipeline follows these stages:

1. Data Sources – Startup directories, product datasets, arXiv, news feeds, and job feeds.
2. Async Ingestion – HTTP clients, RSS/API adapters, and bounded concurrency.
3. Normalization and Validation – Common schemas, source URLs, date parsing, and required-field checks.
4. Quality Processing – 24-hour freshness filtering for news and jobs, entity resolution, and deduplication.
5. Optional LLM Extraction – Gemini Flash → Groq Llama → DeepSeek fallback.
6. Persistence and Export – SQLite, optional MongoDB, and Google Sheets.

### 3. Data Ingestion and Processing

**Source Collection:** The repository includes adapters for startup directories, AI product datasets, arXiv papers, AI news feeds, and job feeds.

**Normalization:** Validate names, source URLs, attribution, record types, required fields, and publication dates.

**Freshness:** News and jobs are checked against a rolling 24-hour publication window. Dates are normalized to UTC. Missing or invalid dates are not treated as fresh.

**Deduplication:** Canonical URL/source hashes identify duplicate records. Entity mapping decisions are stored in the Entity Mapping Log.

### 4. LLM Extraction and Error Handling

The extraction component supports:

Gemini Flash → Groq Llama → DeepSeek.

LLM output must be checked against the original source and URL. Missing facts must never be invented.

**HTTP 413:**
- Split long text into smaller overlapping chunks.
- Reduce chunk size and retry.
- Retain source URL and section metadata.

**HTTP 429:**
- Respect Retry-After.
- Use exponential backoff with jitter.
- Limit provider concurrency.
- Use fallback providers when appropriate.

Transient errors such as HTTP 503 should also use bounded retries.

### 5. Storage and Export Strategy

SQLite is the default local database. MongoDB is an optional backend.

Records contain source hash, record type, structured JSON payload, and collection timestamp.

Google Sheets export creates six tabs:

1. Startups
2. Products
3. Research Papers
4. Jobs
5. News
6. Entity Mapping Log

For production growth, PostgreSQL can serve as the canonical relational store. Raw snapshots can be retained in object storage.

### 6. Scalability Strategy – 500,000+ Records

The proposed production design includes:

- Source registry for crawl jobs.
- Redis Streams or Kafka as a durable queue.
- Stateless asynchronous workers.
- Per-domain concurrency limits.
- Distributed checkpoints and idempotency keys.
- Bulk database writes and object storage.
- Backpressure and centralized rate limiting.

This is a proposed scaling design, not a claim that a 500,000-record distributed deployment is already running.

### 7. Anti-Bot Strategy and Compliance

- Prefer official APIs, RSS feeds, open datasets, and licensed sources.
- Respect robots.txt, terms of service, rate limits, and access restrictions.
- Use conservative concurrency and caching.
- Use Playwright only for permitted JavaScript-rendered pages.
- Do not bypass CAPTCHAs, authentication, or access controls.
- If blocked, stop and seek permission or a supported API.

### 8. Current Implementation Status and Data Quality

Latest local database snapshot:

| Record Type | Stored Records |
|---|---:|
| Startups | 1,000 |
| Products | 1,000 |
| Research Papers | 1,000 |
| Jobs | 214 |
| News | 7 |
| **Total** | **3,221** |

These are stored database counts, not independent manual verification of every record. They may include records from earlier runs.

In the latest run:
- 10 arXiv papers were fetched.
- GitHub metrics were independently verified for 1 of those 10 papers.
- Unknown repository metrics are left blank rather than guessed.
- News and jobs are subject to freshness filtering.
- Source URLs are retained for traceability.

### 9. Conclusion

FrontierAtlas provides a modular foundation for AI intelligence collection and structured data processing.

Asynchronous ingestion, validation, freshness filtering, entity resolution, persistent storage, and Google Sheets export form a reproducible workflow.

The proposed queue-based worker architecture provides a path toward 500,000+ records while maintaining traceability, reliability, and responsible collection.

**GitHub Repository:**  
https://github.com/Aaryankhan78/FrontierAtlas-AI-Intelligence