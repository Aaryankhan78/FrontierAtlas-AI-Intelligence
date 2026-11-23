
import json
import sqlite3
from pathlib import Path

from src.config import settings
from src.utils import logger


class SQLiteStore:
    def __init__(self, path=None):
        self.path = path or settings.sqlite_path

        Path(self.path).parent.mkdir(
            parents=True, exist_ok=True
        )

        self.conn = sqlite3.connect(self.path)

        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS records (
                source_hash TEXT PRIMARY KEY,
                record_type TEXT NOT NULL,
                payload TEXT NOT NULL,
                collected_at TEXT NOT NULL
            )
        """)

        self.conn.commit()

    def save_many(self, records):
        inserted = 0
        updated = 0

        for record in records:
            payload = record.model_dump(mode="json")
            payload_json = json.dumps(payload)

            collected_at = payload.get("collectedAt", "")

            try:
                existing = self.conn.execute(
                    "SELECT 1 FROM records WHERE source_hash = ?",
                    (record.source_hash,)
                ).fetchone()

                self.conn.execute("""
                    INSERT INTO records (
                        source_hash, record_type, payload, collected_at
                    )
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(source_hash) DO UPDATE SET
                        record_type = excluded.record_type,
                        payload = excluded.payload,
                        collected_at = excluded.collected_at
                """, (
                    record.source_hash,
                    record.recordType,
                    payload_json,
                    collected_at
                ))

                if existing:
                    updated += 1
                else:
                    inserted += 1

            except Exception as exc:
                logger.warning(
                    "SQLite write failed for %s: %s",
                    record.source_hash,
                    exc
                )

        self.conn.commit()

        logger.info(
            "Database: %d inserted, %d updated",
            inserted,
            updated
        )

        return inserted

    def all_records(self):
        rows = self.conn.execute(
            "SELECT payload FROM records"
        ).fetchall()

        return [json.loads(row[0]) for row in rows]

    def close(self):
        self.conn.close()


class MongoStore:
    def __init__(self):
        from pymongo import MongoClient

        self.client = MongoClient(settings.mongodb_uri)

        self.collection = self.client[
            settings.mongodb_database
        ]["records"]

        self.collection.create_index(
            "source_hash", unique=True
        )

    def save_many(self, records):
        inserted = 0
        updated = 0

        for record in records:
            doc = record.model_dump(mode="json")
            doc["source_hash"] = record.source_hash

            try:
                result = self.collection.update_one(
                    {"source_hash": record.source_hash},
                    {"$set": doc},
                    upsert=True
                )

                if result.upserted_id is not None:
                    inserted += 1
                elif result.modified_count > 0:
                    updated += 1

            except Exception as exc:
                logger.warning(
                    "Mongo write failed: %s", exc
                )

        logger.info(
            "MongoDB: %d inserted, %d updated",
            inserted,
            updated
        )

        return inserted

    def all_records(self):
        return list(
            self.collection.find({}, {"_id": 0})
        )

    def close(self):
        self.client.close()


def get_store():
    if settings.storage_backend == "mongodb":
        if not settings.mongodb_uri:
            raise ValueError(
                "MONGODB_URI is required for MongoDB backend"
            )

        return MongoStore()

    return SQLiteStore()
