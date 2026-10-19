from google import genai
from google.genai import types
from app.config import settings
from app.services.gemini import AiUnavailable

_client = genai.Client(api_key=settings.GEMINI_API_KEY, http_options=types.HttpOptions(timeout=15_000))

def embed_texts(texts: list[str], batch_size: int = 20) -> list[list[float]]:
    out: list[list[float]] = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        try:
            r = _client.models.embed_content(model=settings.GEMINI_EMBEDDING_MODEL, contents=batch)
            out.extend([e.values for e in r.embeddings])
        except Exception as exc:
            raise AiUnavailable("provider", str(exc)) from exc
    return out