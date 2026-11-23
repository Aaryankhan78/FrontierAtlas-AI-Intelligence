from dataclasses import dataclass
import os
from dotenv import load_dotenv

load_dotenv()

@dataclass(frozen=True)
class Settings:
    concurrency: int = int(os.getenv("MAX_CONCURRENCY", "12"))
    timeout: int = int(os.getenv("REQUEST_TIMEOUT", "25"))
    retries: int = int(os.getenv("REQUEST_RETRIES", "3"))
    user_agent: str = os.getenv("USER_AGENT", "FrontierAtlasResearchBot/1.0")
    storage_backend: str = os.getenv("STORAGE_BACKEND", "sqlite").lower()
    sqlite_path: str = os.getenv("SQLITE_PATH", "data/intelligence.db")
    mongodb_uri: str = os.getenv("MONGODB_URI", "")
    mongodb_database: str = os.getenv("MONGODB_DATABASE", "frontier_atlas")
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    groq_api_key: str = os.getenv("GROQ_API_KEY", "")
    deepseek_api_key: str = os.getenv("DEEPSEEK_API_KEY", "")
    sheets_id: str = os.getenv("GOOGLE_SHEETS_ID", "")
    service_account_json: str = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "credentials/service-account.json")

settings = Settings()
