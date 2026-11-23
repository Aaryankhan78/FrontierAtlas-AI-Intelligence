# FrontierAtlas – AI Engineer Assignment

FrontierAtlas is a Python-based asynchronous AI intelligence collection pipeline. It collects startup, AI product, research paper, job, and AI news data from configured sources, applies freshness filtering and deduplication, and exports structured records to SQLite and Google Sheets.

## Features

- Asynchronous data collection using HTTP clients.
- AI startup collection from configured startup directories.
- AI product collection from multiple product directories and datasets.
- Research paper collection from arXiv.
- GitHub repository metrics enrichment when a repository can be independently verified.
- AI news and job collection through configured RSS/feed sources.
- 24-hour freshness filtering for news and jobs.
- Source-based deduplication and entity mapping.
- SQLite persistence with optional MongoDB support.
- Google Sheets export with six dedicated tabs.
- Optional LLM extraction with Gemini, Groq, and DeepSeek fallback.

## Current Collection Snapshot

The local database snapshot from the latest pipeline run contains:

| Record Type | Stored Records |
|---|---:|
| Startups | 1,000 |
| Products | 1,000 |
| Research Papers | 1,000 |
| Jobs | 214 |
| News | 7 |
| **Total** | **3,221** |

These are database counts, not a claim that every record has undergone independent manual verification. Each record should retain its source attribution and URL.

The latest research paper collection fetched 10 papers, and GitHub enrichment verified repository metrics for 1 of those 10 papers.

## Requirements

- Python 3.10+
- Optional Gemini, Groq, and DeepSeek API keys.
- Google Cloud service account JSON for Google Sheets export.
- Optional MongoDB URI. SQLite is supported by default.

## Setup (Windows PowerShell)

```powershell
py -3 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
```

Configure `.env` with the required settings.

## Run the Pipeline

```powershell
python -m src.main --papers 10 --startups 10 --products 1000
```

To export the collected data to Google Sheets:

```powershell
python -m src.main --papers 10 --startups 10 --products 1000 --export-sheets
```

Run tests:

```powershell
pytest -q
```

The pipeline stores records in `data/intelligence.db` and writes entity mapping information to `data/entity_mapping_log.json`.

## Google Sheets Integration

The project supports six Google Sheets tabs:

1. Startups
2. Products
3. Research Papers
4. Jobs
5. News
6. Entity Mapping Log

To configure Google Sheets:

1. Enable Google Sheets API and Google Drive API in Google Cloud.
2. Create a service account and download its JSON key.
3. Store the key at `credentials/service-account.json`.
4. Share the spreadsheet with the service account email as Editor.
5. Configure the following variables in `.env`:

```env
GOOGLE_SHEETS_ID=YOUR_SPREADSHEET_ID
GOOGLE_SERVICE_ACCOUNT_JSON=credentials/service-account.json
```

Run the pipeline with `--export-sheets` to upload the data.

## LLM Provider Fallback

The extraction component supports the following provider sequence:

1. Gemini Flash
2. Groq Llama
3. DeepSeek

The fallback is intended to handle provider failures and extraction workloads. LLM-generated fields must be validated against their original source URLs before persistence. The system must not invent missing facts.

## Reliability and Scalability

- Asynchronous HTTP collection with bounded concurrency.
- Retry and backoff handling for transient failures and rate limits.
- Chunking with overlap for large text inputs.
- SQLite source-hash deduplication.
- Optional MongoDB persistence with unique indexes.
- UTC-normalized publication timestamps and freshness filtering.
- A distributed architecture using queues such as Redis or Kafka, partitioned workers, bulk database writes, and checkpoints can support future scaling toward 500,000 records.

## Anti-Bot and Responsible Collection

- Prefer official APIs, RSS feeds, licensed datasets, and publicly permitted sources.
- Respect robots.txt, terms of service, rate limits, and access restrictions.
- Do not bypass CAPTCHAs, authentication, or other access controls.
- Use conservative concurrency and caching where crawling is permitted.
- Stop collection when a source blocks access or requires additional permission.

## Data Quality

- Preserve legitimate source URLs for collected records.
- Exclude records without valid publication dates from strict 24-hour filtering.
- Do not fabricate startup, product, research, or job records.
- Populate GitHub metrics only when the repository is independently identified and verified.
- Maintain deterministic entity mapping and deduplication.

## Project Structure

```text
AI-Engineer-Assignment/
├── src/
│   ├── scrapers/
│   ├── exporters/
│   ├── config.py
│   ├── models.py
│   ├── pipeline.py
│   ├── storage.py
│   └── main.py
├── credentials/
├── data/
├── tests/
├── .env.example
├── requirements.txt
└── README.md
```

## Responsible Data Policy

FrontierAtlas prioritizes traceable source-backed records, transparent collection limitations, and reproducible processing. Unverified information and guessed metrics are not treated as factual data.