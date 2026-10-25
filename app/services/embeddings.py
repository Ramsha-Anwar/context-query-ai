from fastembed import TextEmbedding
from app.config import settings
from app.services.groq_service import AiUnavailable

# A global variable to hold the model instance
_model = None

def _get_model():
    """Lazy-loads the embedding model on first use."""
    global _model
    if _model is None:
        print("Loading embedding model for the first time...")
        # 1. Switch to a smaller model (384-dim, ~46MB)
        # 2. Disable the CPU memory arena to prevent leaks
        _model = TextEmbedding(
            model_name="BAAI/bge-small-en-v1.5",
            session_options={"enable_cpu_mem_arena": False}
        )
    return _model

def embed_texts(texts: list[str], batch_size: int = 32) -> list[list[float]]:
    try:
        model = _get_model()
        # Use a smaller batch size for inference to keep peak memory low
        vectors = list(model.embed(texts, batch_size=batch_size))
        return [v.tolist() for v in vectors]
    except Exception as exc:
        raise AiUnavailable("provider", str(exc)) from exc