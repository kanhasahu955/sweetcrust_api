"""AI-service settings = shared base + LLM / RAG / Twilio."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import AliasChoices, Field
from pydantic_settings import SettingsConfigDict

from package.common.env import service_env_files
from package.common.settings import Settings as BaseSettings, configure_settings

_ENV_FILES = service_env_files(Path(__file__))


class AISettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=_ENV_FILES, extra="ignore")

    service_name: str = "ai"
    service_version: str = "0.1.0"
    port: int = Field(default=8006, validation_alias=AliasChoices("SERVICE_PORT"))
    ai_chat_rate_limit: int = 60
    ai_chat_rate_window_sec: int = 3600

    twilio_account_sid: Optional[str] = None
    twilio_auth_token: Optional[str] = None
    twilio_from_number: Optional[str] = None
    twilio_webhook_base_url: Optional[str] = None

    llm_provider: str = "groq"
    llm_model: str = "llama-3.3-70b-versatile"
    llm_temperature: float = 0.2
    rag_max_tokens: int = 1024
    openai_api_key: Optional[str] = None
    openai_image_model: str = "gpt-image-1"
    google_api_key: Optional[str] = None
    groq_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    llama_api_key: Optional[str] = None
    ai_dev_mock_llm: bool = False

    # Optional permanent host for generated category covers
    imagekit_public_key: Optional[str] = None
    imagekit_private_key: Optional[str] = None
    imagekit_url_endpoint: Optional[str] = None

    embedding_provider: str = "openai"
    embedding_model: str = "text-embedding-3-small"

    vector_store: str = "bm25"
    rag_top_k: int = 4
    rag_score_threshold: float = 0.7
    vector_store_path: str = "./data/vector_store"
    pinecone_api_key: Optional[str] = None
    pinecone_env: str = "us-east-1"
    pinecone_index_name: str = "quickstart"
    pinecone_namespace: str = "__default__"
    rag_chunk_size: int = 800
    rag_chunk_overlap: int = 120

    ai_agent_max_iterations: int = 6
    guardrails_enabled: bool = True

    serper_api_key: Optional[str] = None
    tavily_api_key: Optional[str] = None
    langsmith_api_key: Optional[str] = None
    langsmith_project: str = "sweetcrust"

    @property
    def twilio_configured(self) -> bool:
        return bool(
            self.twilio_account_sid
            and self.twilio_auth_token
            and self.twilio_from_number
            and self.twilio_webhook_base_url
        )

    @property
    def llm_api_key(self) -> Optional[str]:
        mapping = {
            "groq": self.groq_api_key,
            "openai": self.openai_api_key,
            "google": self.google_api_key,
            "gemini": self.google_api_key,
            "anthropic": self.anthropic_api_key,
            "llama": self.llama_api_key,
        }
        return mapping.get(self.llm_provider.lower()) or self.openai_api_key or self.groq_api_key

    @property
    def llm_configured(self) -> bool:
        if self.ai_dev_mock_llm and self.is_dev:
            return True
        return bool(self.llm_api_key)

    def integration_status(self) -> dict:
        store = self.vector_store.lower()
        return {
            "database": bool(self.database_url),
            "redis": self.redis_configured,
            "llm": {
                "provider": self.llm_provider,
                "model": self.llm_model,
                "configured": self.llm_configured,
                "mock": self.ai_dev_mock_llm and self.is_dev,
            },
            "embeddings": {
                "provider": self.embedding_provider,
                "model": self.embedding_model,
                "configured": bool(
                    self.openai_api_key if self.embedding_provider == "openai" else self.llm_api_key
                ),
            },
            "vector_store": "bm25",
            "vector_store_configured": self.vector_store,
            "pinecone": False,
            "pinecone_stub": store == "pinecone",
            "pinecone_key_present": bool(self.pinecone_api_key),
            "langsmith": bool(self.langsmith_api_key),
            "twilio_voice": self.twilio_configured,
            "guardrails": self.guardrails_enabled,
            "chat_rate_limit": self.ai_chat_rate_limit,
        }


@lru_cache
def get_settings() -> AISettings:
    return AISettings()


def reload_settings() -> AISettings:
    get_settings.cache_clear()
    return get_settings()


def boot_settings() -> AISettings:
    """Wire AI settings into package (DB/CORS/JWT) before first engine use."""
    configure_settings(get_settings)
    return get_settings()
