import aiohttp
from tenacity import retry, stop_after_attempt, wait_exponential_jitter, retry_if_exception_type
from src.config import settings
from src.utils import logger

class HttpClient:
    def __init__(self):
        self.timeout = aiohttp.ClientTimeout(total=settings.timeout)
        self.semaphore = __import__("asyncio").Semaphore(settings.concurrency)
        self.session = None

    async def __aenter__(self):
        self.session = aiohttp.ClientSession(timeout=self.timeout, headers={"User-Agent": settings.user_agent})
        return self

    async def __aexit__(self, *args):
        await self.session.close()

    async def get_text(self, url: str) -> str:
        async with self.semaphore:
            for attempt in range(settings.retries):
                try:
                    async with self.session.get(url) as response:
                        if response.status in (429, 503):
                            retry_after = response.headers.get("Retry-After")
                            import asyncio
                            await asyncio.sleep(float(retry_after) if retry_after and retry_after.isdigit() else 2 ** attempt)
                            continue
                        response.raise_for_status()
                        return await response.text()
                except (aiohttp.ClientError, TimeoutError) as exc:
                    if attempt == settings.retries - 1:
                        logger.warning("Request failed for %s: %s", url, exc)
                        raise
                    import asyncio
                    await asyncio.sleep(min(20, 2 ** attempt))
            raise RuntimeError(f"Request retries exhausted: {url}")
