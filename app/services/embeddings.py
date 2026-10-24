from fastembed import TextEmbedding
from app.config import settings
from app.services.groq_service import AiUnavailable

# 768-dim model — matches the existing vector(768) column in Postgres.
# ONNX-based, no Torch dependency. Loads in ~50-200 MB of memory.
_model = TextEmbedding(model_name="BAAI/bge-base-en-v1.5")


def embed_texts(texts: list[str], batch_size: int = 32) -> list[list[float]]:
    try:
        # FastEmbed returns a generator of numpy arrays. Convert to plain lists.
        vectors = list(_model.embed(texts, batch_size=batch_size))
        return [v.tolist() for v in vectors]
    except Exception as exc:
        raise AiUnavailable("provider", str(exc)) from exc