# Architecture – FrontierAtlas ingestion demo

## 1. Scale strategy
Use a source registry that emits crawl jobs to a durable queue. Stateless async workers consume jobs
with per-domain concurrency limits, checkpoints, and idempotency keys. Horizontal scaling adds workers
without changing crawler logic. For a 500k+ target, use Kafka/Redis Streams or a managed queue, object
storage for raw snapshots, and bulk database writes. Apply backpressure when downstream LLM or storage
capacity is saturated.

## 2. 413 and 429 handling
Extract relevant page sections before LLM calls. Split long text into bounded chunks with overlap and
preserve source URL + section metadata. On 413, reduce chunk size and retry once; on 429, honor Retry-After,
then exponential backoff with jitter and provider-specific concurrency budgets. Circuit-break a provider
after repeated failures and continue through Gemini, Groq, then DeepSeek. Validate JSON against a schema.

## 3. Freshness and duplicate prevention
Normalize publication dates to UTC, retain raw date strings and extraction provenance, and reject jobs/news
outside the 24-hour window. Use canonical URL hashes and unique database constraints so multiple workers
cannot insert the same item. Persist crawl checkpoints and use conditional writes/leases for distributed
workers. If a source has no date, compare stable item IDs against the previous crawl; do not claim a
24-hour guarantee without reliable evidence.

## 4. Storage strategy
Use PostgreSQL as the canonical relational store for entities, source records, timestamps, and unique
constraints. Use object storage for raw HTML snapshots. Add a graph database (Neo4j) when relationship
queries become central; use pgvector or a dedicated vector store for semantic retrieval. The demo uses
SQLite by default for easy local setup and supports MongoDB as an optional document store.

## 5. Anti-bot and compliance
Prefer official APIs, RSS, open datasets, and licensed access. For permitted JS-rendered pages, use
Playwright with caching and low concurrency. Respect robots.txt, terms, rate limits, and CAPTCHAs. Do not
evade access controls; blocked sources require permission or a supported API.
