import json, re
from src.config import settings
from src.utils import logger

SYSTEM_PROMPT = '''Extract only facts explicitly present in the supplied source text.
Return one JSON object. Use null for missing values. Never invent companies, dates,
prices, authors, URLs, or metrics. Include source_url exactly as provided.'''

class LLMExtractor:
    async def extract(self, text: str, schema_hint: str, source_url: str):
        # Chunk before provider calls; retain overlap to reduce boundary loss.
        chunks = self._chunks(text, max_chars=12000, overlap=500)
        for chunk in chunks:
            result = await self._fallback(chunk, schema_hint, source_url)
            if result:
                return result
        return {"extraction_status": "no_llm_result", "source_url": source_url}

    def _chunks(self, text, max_chars=12000, overlap=500):
        if len(text) <= max_chars:
            return [text]
        chunks, start = [], 0
        while start < len(text):
            end = min(len(text), start + max_chars)
            chunks.append(text[start:end])
            if end == len(text): break
            start = end - overlap
        return chunks

    async def _fallback(self, text, schema_hint, source_url):
        # Provider adapters are optional; deterministic scraping remains usable without keys.
        if settings.gemini_api_key:
            try:
                import google.generativeai as genai
                genai.configure(api_key=settings.gemini_api_key)
                model = genai.GenerativeModel("gemini-1.5-flash")
                prompt = f"{SYSTEM_PROMPT}\nSchema: {schema_hint}\nSource URL: {source_url}\nText:\n{text[:12000]}"
                response = model.generate_content(prompt)
                return self._parse_json(response.text)
            except Exception as exc:
                logger.warning("Gemini extraction failed; trying next provider: %s", exc)
        # Groq / DeepSeek can be wired through OpenAI-compatible HTTP endpoints.
        providers = [
            ("GROQ_API_KEY", settings.groq_api_key, "https://api.groq.com/openai/v1/chat/completions", "llama-3.1-8b-instant"),
            ("DEEPSEEK_API_KEY", settings.deepseek_api_key, "https://api.deepseek.com/chat/completions", "deepseek-chat"),
        ]
        for _, key, endpoint, model in providers:
            if not key: continue
            try:
                import aiohttp
                payload = {"model": model, "messages": [{"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": f"Schema: {schema_hint}\nSource URL: {source_url}\n{text[:12000]}"}],
                    "temperature": 0}
                async with aiohttp.ClientSession() as session:
                    async with session.post(endpoint, json=payload, headers={"Authorization": f"Bearer {key}"}) as r:
                        if r.status == 429:
                            continue
                        r.raise_for_status()
                        data = await r.json()
                        return self._parse_json(data["choices"][0]["message"]["content"])
            except Exception as exc:
                logger.warning("%s extraction failed: %s", model, exc)
        return None

    @staticmethod
    def _parse_json(value):
        value = re.sub(r"^```(?:json)?|```$", "", value.strip(), flags=re.I|re.M)
        try: return json.loads(value)
        except json.JSONDecodeError: return None
