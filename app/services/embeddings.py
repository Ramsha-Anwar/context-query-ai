from google import genai
from google.genai import types
from app.config import settings
from app.services.gemini import _classify, AiUnavailable

_client = genai.Client(
    api_key=settings.GEMINI_API_KEY,
    http_options=types.HttpOptions(timeout=15_000)
)

def embed_texts(texts: list[str], batch_size: int = 20) -> list[list[float]]:
    """Embeds a list of texts, batching to respect rate limits. Raises AiUnavailable."""
    out: list[list[float]] = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        try:
            r = _client.models.embed_content(
                model=settings.GEMINI_EMBEDDING_MODEL, 
                contents=batch,
                # Tell Gemini exactly how many dimensions to return
                config=types.EmbedContentConfig(output_dimensionality=settings.EMBEDDING_DIM)
            )
            # Slice to ensure it perfectly matches our DB schema no matter what
            out.extend([e.values[:settings.EMBEDDING_DIM] for e in r.embeddings])
        except Exception as exc:
            raise AiUnavailable(_classify(exc), str(exc)) from exc
    return out