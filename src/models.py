from datetime import datetime, timezone
from typing import Any
from pydantic import BaseModel, Field, HttpUrl

def utc_now() -> datetime:
    return datetime.now(timezone.utc)

class Record(BaseModel):
    schemaVersion: str = "1.0"
    recordType: str
    source: dict[str, Any] = Field(default_factory=dict)
    content: dict[str, Any] = Field(default_factory=dict)
    collectedAt: datetime = Field(default_factory=utc_now)
    source_hash: str = ""

class CrawlResult(BaseModel):
    url: str
    status: str
    records: int = 0
    error: str | None = None
