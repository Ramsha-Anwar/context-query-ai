from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str
    DIRECT_DATABASE_URL: str | None = None
    JWT_SECRET_KEY: str
    GROQ_API_KEY: str

    GROQ_MODEL: str = "openai/gpt-oss-120b"
    EMBEDDING_MODEL: str = "BAAI/bge-base-en-v1.5"
    EMBEDDING_DIM: int = 384

    CHUNK_SIZE_TOKENS: int = 500
    CHUNK_OVERLAP_TOKENS: int = 50
    INLINE_SYNC_MAX_CHARS: int = 20000
    RAG_TOP_K: int = 5
    RAG_MIN_SIMILARITY: float = 0.55
    RAG_FAITHFULNESS_MIN: float = 0.70
    RAG_RELEVANCY_MIN: float = 0.70
    CORS_ORIGINS: str = ""
    ENVIRONMENT: str = "development"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

settings = Settings()
