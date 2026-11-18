from __future__ import annotations

from typing import Literal

from pydantic import AliasChoices, BaseModel, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class MongoSettings(BaseModel):
    """MongoDB connection and collection names used by the application."""

    uri: str = Field(
        default="mongodb://localhost:27017",
        validation_alias=AliasChoices("uri", "MONGODB_URI"),
    )
    database_name: str = Field(
        default="jurisai",
        validation_alias=AliasChoices("database_name", "DATABASE_NAME"),
    )
    schemes_collection: str = Field(
        default="schemes",
        validation_alias=AliasChoices("schemes_collection", "SCHEMES_COLLECTION"),
    )
    test_schemes_collection: str = Field(
        default="test_schemes",
        validation_alias=AliasChoices(
            "test_schemes_collection",
            "TEST_SCHEMES_COLLECTION",
        ),
    )
    schemes_enriched_collection: str = Field(
        default="schemes_enriched",
        validation_alias=AliasChoices(
            "schemes_enriched_collection",
            "SCHEMES_ENRICHED_COLLECTION",
        ),
    )
    test_schemes_enriched_collection: str = Field(
        default="test_schemes_enriched",
        validation_alias=AliasChoices(
            "test_schemes_enriched_collection",
            "TEST_SCHEMES_ENRICHED_COLLECTION",
        ),
    )


class QdrantSettings(BaseModel):
    """Qdrant connection details and collection/profile defaults."""

    url: str = Field(
        default="http://localhost:6333",
        validation_alias=AliasChoices("url", "QDRANT_URL"),
    )
    api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("api_key", "QDRANT_API_KEY"),
    )
    default_collection: str = Field(
        default="test_schemes_vectors",
        validation_alias=AliasChoices(
            "default_collection",
            "QDRANT_COLLECTION",
        ),
    )
    production_collection: str = Field(
        default="schemes_vectors",
        validation_alias=AliasChoices(
            "production_collection",
            "QDRANT_PRODUCTION_COLLECTION",
        ),
    )
    profiles: tuple[str, ...] = Field(
        default=("embedding_a", "embedding_b"),
        validation_alias=AliasChoices("profiles"),
    )
    dense_vector_name: str = Field(
        default="dense_vector",
        validation_alias=AliasChoices(
            "dense_vector_name",
            "QDRANT_DENSE_VECTOR_NAME",
        ),
    )
    sparse_vector_name: str = Field(
        default="keyword_sparse_vector",
        validation_alias=AliasChoices(
            "sparse_vector_name",
            "QDRANT_SPARSE_VECTOR_NAME",
        ),
    )
    sparse_keyword_dimensions: int = Field(
        default=32768,
        validation_alias=AliasChoices(
            "sparse_keyword_dimensions",
            "QDRANT_SPARSE_KEYWORD_DIMENSIONS",
        ),
    )


class EmbeddingSettings(BaseModel):
    """Embedding backend and model configuration for indexing and search."""

    backend: Literal["local", "gemini"] = Field(
        default="local",
        validation_alias=AliasChoices("backend", "EMBEDDING_BACKEND"),
    )
    model: str | None = Field(
        default=None,
        validation_alias=AliasChoices("model", "EMBEDDING_MODEL"),
    )
    local_model: str = Field(
        default="all-MiniLM-L6-v2",
        validation_alias=AliasChoices(
            "local_model",
            "LOCAL_EMBEDDING_MODEL",
        ),
    )
    gemini_model: str = Field(
        default="gemini-embedding-001",
        validation_alias=AliasChoices(
            "gemini_model",
            "GEMINI_EMBEDDING_MODEL",
        ),
    )


class GeminiSettings(BaseModel):
    """Gemini API credentials and model choices used across the app."""

    api_key: str | None = Field(
        default=None,
        description="Gemini Developer API key.",
        validation_alias=AliasChoices("api_key", "GEMINI_API_KEY"),
    )
    model: str = Field(
        default="models/gemini-flash-latest",
        validation_alias=AliasChoices("model", "GEMINI_MODEL"),
    )
    reasoning_model: str = Field(
        default="models/gemini-flash-latest",
        validation_alias=AliasChoices(
            "reasoning_model",
            "GEMINI_REASONING_MODEL",
        ),
    )
    intent_model: str = Field(
        default="models/gemini-flash-lite-latest",
        validation_alias=AliasChoices(
            "intent_model",
            "GEMINI_INTENT_MODEL",
        ),
    )


class LocalGenerationSettings(BaseModel):
    """Local OpenAI-compatible inference settings for self-hosted models."""

    base_url: str = Field(
        default="http://127.0.0.1:1234/v1",
        validation_alias=AliasChoices("base_url", "LOCAL_GENERATION_BASE_URL"),
    )
    api_key: str = Field(
        default="not-needed",
        validation_alias=AliasChoices("api_key", "LOCAL_GENERATION_API_KEY"),
    )
    model: str = Field(
        default="mlx-community/Qwen3.5-4B-MLX-4bit",
        validation_alias=AliasChoices("model", "LOCAL_GENERATION_MODEL"),
    )
    timeout_seconds: float = Field(
        default=60.0,
        validation_alias=AliasChoices(
            "timeout_seconds",
            "LOCAL_GENERATION_TIMEOUT_SECONDS",
        ),
    )
    enable_thinking: bool = Field(
        default=False,
        validation_alias=AliasChoices(
            "enable_thinking",
            "LOCAL_GENERATION_ENABLE_THINKING",
        ),
    )


class OpenRouterSettings(BaseModel):
    """OpenRouter configuration for hosted OpenAI-compatible generation."""

    api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("api_key", "OPENROUTER_API_KEY"),
    )
    base_url: str = Field(
        default="https://openrouter.ai/api/v1",
        validation_alias=AliasChoices("base_url", "OPENROUTER_BASE_URL"),
    )
    model: str = Field(
        default="openrouter/free",
        validation_alias=AliasChoices("model", "OPENROUTER_MODEL"),
    )
    timeout_seconds: float = Field(
        default=60.0,
        validation_alias=AliasChoices(
            "timeout_seconds",
            "OPENROUTER_TIMEOUT_SECONDS",
        ),
    )
    app_name: str | None = Field(
        default="JurisAI",
        validation_alias=AliasChoices("app_name", "OPENROUTER_APP_NAME"),
    )
    http_referer: str | None = Field(
        default=None,
        validation_alias=AliasChoices("http_referer", "OPENROUTER_HTTP_REFERER"),
    )
    enable_thinking: bool = Field(
        default=False,
        validation_alias=AliasChoices(
            "enable_thinking",
            "OPENROUTER_ENABLE_THINKING",
        ),
    )


class WorkflowSettings(BaseModel):
    """Model and runtime options for the agentic workflow."""

    generation_provider: Literal[
        "gemini", "llamaindex_google", "local_openai", "openrouter"
    ] = Field(
        default="openrouter",
        validation_alias=AliasChoices(
            "generation_provider",
            "WORKFLOW_GENERATION_PROVIDER",
        ),
    )
    generation_model: str = Field(
        default="openrouter/free",
        validation_alias=AliasChoices(
            "generation_model",
            "WORKFLOW_GENERATION_MODEL",
        ),
    )
    timeout_seconds: float = Field(
        default=180.0,
        validation_alias=AliasChoices(
            "timeout_seconds",
            "WORKFLOW_TIMEOUT_SECONDS",
        ),
    )
    intent_provider: Literal[
        "gemini", "llamaindex_google", "local_openai", "openrouter"
    ] = Field(
        default="openrouter",
        validation_alias=AliasChoices(
            "intent_provider",
            "WORKFLOW_INTENT_PROVIDER",
        ),
    )
    intent_model: str = Field(
        default="openrouter/free",
        validation_alias=AliasChoices(
            "intent_model",
            "WORKFLOW_INTENT_MODEL",
        ),
    )
    retrieval_limit: int = Field(
        default=5,
        validation_alias=AliasChoices(
            "retrieval_limit",
            "WORKFLOW_RETRIEVAL_LIMIT",
        ),
    )
    retrieval_strategy: Literal["dense", "hybrid", "sparse"] = Field(
        default="dense",
        validation_alias=AliasChoices("retrieval_strategy", "WORKFLOW_RETRIEVAL_STRATEGY"),
    )
    retrieval_filters_enabled: bool = Field(
        default=True,
        validation_alias=AliasChoices(
            "retrieval_filters_enabled",
            "WORKFLOW_RETRIEVAL_FILTERS_ENABLED",
        ),
    )
    retrieval_filter_mode: Literal[
        "all",
        "none",
        "state_only",
        "topics_only",
        "state_hard_topics_soft",
    ] = Field(
        default="state_only",
        validation_alias=AliasChoices(
            "retrieval_filter_mode",
            "WORKFLOW_RETRIEVAL_FILTER_MODE",
        ),
    )


class PhoenixSettings(BaseModel):
    """Phoenix tracing configuration for local or cloud observability."""

    project_name: str = Field(
        default="jurisai-agentic-poc",
        validation_alias=AliasChoices("project_name", "PHOENIX_PROJECT_NAME"),
    )
    collector_endpoint: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "collector_endpoint",
            "PHOENIX_COLLECTOR_ENDPOINT",
            "OTEL_EXPORTER_OTLP_ENDPOINT",
        ),
    )
    api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("api_key", "PHOENIX_API_KEY"),
    )


class ApiSettings(BaseModel):
    """HTTP API and frontend integration settings."""

    host: str = Field(
        default="127.0.0.1",
        validation_alias=AliasChoices("host", "API_HOST"),
    )
    port: int = Field(
        default=8000,
        validation_alias=AliasChoices("port", "API_PORT"),
    )
    reload: bool = Field(
        default=False,
        validation_alias=AliasChoices("reload", "API_RELOAD"),
    )
    cors_origins: tuple[str, ...] = Field(
        default=("http://127.0.0.1:5173", "http://localhost:5173"),
        validation_alias=AliasChoices("cors_origins", "API_CORS_ORIGINS"),
    )
    chat_sessions_collection: str = Field(
        default="chat_sessions",
        validation_alias=AliasChoices(
            "chat_sessions_collection",
            "CHAT_SESSIONS_COLLECTION",
        ),
    )
    chat_runs_collection: str = Field(
        default="chat_runs",
        validation_alias=AliasChoices(
            "chat_runs_collection",
            "CHAT_RUNS_COLLECTION",
        ),
    )
    frontend_dist_dir: str = Field(
        default="web/dist",
        validation_alias=AliasChoices("frontend_dist_dir", "FRONTEND_DIST_DIR"),
    )


class RetrievalEvalSettings(BaseModel):
    """Storage and artifact settings for retrieval evaluation datasets."""

    artifacts_root: str = Field(
        default="eval/retrieval",
        validation_alias=AliasChoices("artifacts_root"),
    )
    personas_collection: str = Field(
        default="eval_personas",
        validation_alias=AliasChoices("personas_collection"),
    )
    scheme_shortlists_collection: str = Field(
        default="eval_scheme_shortlists",
        validation_alias=AliasChoices("scheme_shortlists_collection"),
    )
    golden_records_collection: str = Field(
        default="eval_golden_records",
        validation_alias=AliasChoices("golden_records_collection"),
    )
    generation_runs_collection: str = Field(
        default="eval_generation_runs",
        validation_alias=AliasChoices("generation_runs_collection"),
    )
    review_events_collection: str = Field(
        default="eval_review_events",
        validation_alias=AliasChoices("review_events_collection"),
    )
    raw_subset_collection: str = Field(
        default="eval_persona_schemes_v1",
        validation_alias=AliasChoices("raw_subset_collection"),
    )
    enriched_subset_collection: str = Field(
        default="eval_persona_schemes_enriched_v1",
        validation_alias=AliasChoices("enriched_subset_collection"),
    )
    qdrant_collection: str = Field(
        default="eval_persona_schemes_vectors_v1",
        validation_alias=AliasChoices("qdrant_collection"),
    )


class Settings(BaseSettings):
    """Top-level application settings resolved from environment and `.env` values."""

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        env_nested_delimiter="__",
        nested_model_default_partial_update=True,
        env_ignore_empty=True,
        extra="ignore",
    )

    base_url: str = Field(
        default="https://www.myscheme.gov.in",
        validation_alias=AliasChoices("BASE_URL", "APP__BASE_URL"),
    )
    mongo: MongoSettings = Field(default_factory=MongoSettings)
    qdrant: QdrantSettings = Field(default_factory=QdrantSettings)
    embeddings: EmbeddingSettings = Field(default_factory=EmbeddingSettings)
    gemini: GeminiSettings = Field(default_factory=GeminiSettings)
    local_generation: LocalGenerationSettings = Field(
        default_factory=LocalGenerationSettings
    )
    openrouter: OpenRouterSettings = Field(default_factory=OpenRouterSettings)
    workflow: WorkflowSettings = Field(default_factory=WorkflowSettings)
    phoenix: PhoenixSettings = Field(default_factory=PhoenixSettings)
    api: ApiSettings = Field(default_factory=ApiSettings)
    eval: RetrievalEvalSettings = Field(default_factory=RetrievalEvalSettings)
    legacy_mongodb_uri: str | None = Field(
        default=None,
        validation_alias="MONGODB_URI",
        exclude=True,
    )
    legacy_database_name: str | None = Field(
        default=None,
        validation_alias="DATABASE_NAME",
        exclude=True,
    )
    legacy_schemes_collection: str | None = Field(
        default=None,
        validation_alias="SCHEMES_COLLECTION",
        exclude=True,
    )
    legacy_qdrant_url: str | None = Field(
        default=None,
        validation_alias="QDRANT_URL",
        exclude=True,
    )
    legacy_qdrant_collection: str | None = Field(
        default=None,
        validation_alias="QDRANT_COLLECTION",
        exclude=True,
    )
    legacy_qdrant_api_key: str | None = Field(
        default=None,
        validation_alias="QDRANT_API_KEY",
        exclude=True,
    )
    legacy_embedding_backend: Literal["local", "gemini"] | None = Field(
        default=None,
        validation_alias="EMBEDDING_BACKEND",
        exclude=True,
    )
    legacy_embedding_model: str | None = Field(
        default=None,
        validation_alias="EMBEDDING_MODEL",
        exclude=True,
    )
    legacy_local_embedding_model: str | None = Field(
        default=None,
        validation_alias="LOCAL_EMBEDDING_MODEL",
        exclude=True,
    )
    legacy_gemini_embedding_model: str | None = Field(
        default=None,
        validation_alias="GEMINI_EMBEDDING_MODEL",
        exclude=True,
    )
    legacy_gemini_api_key: str | None = Field(
        default=None,
        validation_alias="GEMINI_API_KEY",
        exclude=True,
    )
    legacy_gemini_model: str | None = Field(
        default=None,
        validation_alias="GEMINI_MODEL",
        exclude=True,
    )
    legacy_gemini_reasoning_model: str | None = Field(
        default=None,
        validation_alias="GEMINI_REASONING_MODEL",
        exclude=True,
    )
    legacy_openrouter_api_key: str | None = Field(
        default=None,
        validation_alias="OPENROUTER_API_KEY",
        exclude=True,
    )
    legacy_openrouter_base_url: str | None = Field(
        default=None,
        validation_alias="OPENROUTER_BASE_URL",
        exclude=True,
    )
    legacy_openrouter_model: str | None = Field(
        default=None,
        validation_alias="OPENROUTER_MODEL",
        exclude=True,
    )
    legacy_openrouter_timeout_seconds: float | None = Field(
        default=None,
        validation_alias="OPENROUTER_TIMEOUT_SECONDS",
        exclude=True,
    )
    legacy_openrouter_app_name: str | None = Field(
        default=None,
        validation_alias="OPENROUTER_APP_NAME",
        exclude=True,
    )
    legacy_openrouter_http_referer: str | None = Field(
        default=None,
        validation_alias="OPENROUTER_HTTP_REFERER",
        exclude=True,
    )
    legacy_openrouter_enable_thinking: bool | None = Field(
        default=None,
        validation_alias="OPENROUTER_ENABLE_THINKING",
        exclude=True,
    )
    legacy_workflow_generation_provider: Literal[
        "gemini", "llamaindex_google", "local_openai", "openrouter"
    ] | None = Field(
        default=None,
        validation_alias="WORKFLOW_GENERATION_PROVIDER",
        exclude=True,
    )
    legacy_workflow_generation_model: str | None = Field(
        default=None,
        validation_alias="WORKFLOW_GENERATION_MODEL",
        exclude=True,
    )
    legacy_workflow_intent_provider: Literal[
        "gemini", "llamaindex_google", "local_openai", "openrouter"
    ] | None = Field(
        default=None,
        validation_alias="WORKFLOW_INTENT_PROVIDER",
        exclude=True,
    )
    legacy_workflow_intent_model: str | None = Field(
        default=None,
        validation_alias="WORKFLOW_INTENT_MODEL",
        exclude=True,
    )
    legacy_workflow_retrieval_limit: int | None = Field(
        default=None,
        validation_alias="WORKFLOW_RETRIEVAL_LIMIT",
        exclude=True,
    )
    legacy_workflow_retrieval_strategy: Literal["dense", "hybrid", "sparse"] | None = Field(
        default=None, validation_alias="WORKFLOW_RETRIEVAL_STRATEGY", exclude=True,
    )
    legacy_phoenix_project_name: str | None = Field(
        default=None,
        validation_alias="PHOENIX_PROJECT_NAME",
        exclude=True,
    )
    legacy_phoenix_collector_endpoint: str | None = Field(
        default=None,
        validation_alias="PHOENIX_COLLECTOR_ENDPOINT",
        exclude=True,
    )
    legacy_phoenix_api_key: str | None = Field(
        default=None,
        validation_alias="PHOENIX_API_KEY",
        exclude=True,
    )

    @model_validator(mode="after")
    def apply_legacy_overrides(self) -> "Settings":
        if self.legacy_mongodb_uri is not None:
            self.mongo.uri = self.legacy_mongodb_uri
        if self.legacy_database_name is not None:
            self.mongo.database_name = self.legacy_database_name
        if self.legacy_schemes_collection is not None:
            self.mongo.schemes_collection = self.legacy_schemes_collection
        if self.legacy_qdrant_url is not None:
            self.qdrant.url = self.legacy_qdrant_url
        if self.legacy_qdrant_collection is not None:
            self.qdrant.default_collection = self.legacy_qdrant_collection
        if self.legacy_qdrant_api_key is not None:
            self.qdrant.api_key = self.legacy_qdrant_api_key
        if self.legacy_embedding_backend is not None:
            self.embeddings.backend = self.legacy_embedding_backend
        if self.legacy_embedding_model is not None:
            self.embeddings.model = self.legacy_embedding_model
        if self.legacy_local_embedding_model is not None:
            self.embeddings.local_model = self.legacy_local_embedding_model
        if self.legacy_gemini_embedding_model is not None:
            self.embeddings.gemini_model = self.legacy_gemini_embedding_model
        if self.legacy_gemini_api_key is not None:
            self.gemini.api_key = self.legacy_gemini_api_key
        if self.legacy_gemini_model is not None:
            self.gemini.model = self.legacy_gemini_model
        if self.legacy_gemini_reasoning_model is not None:
            self.gemini.reasoning_model = self.legacy_gemini_reasoning_model
        if self.legacy_openrouter_api_key is not None:
            self.openrouter.api_key = self.legacy_openrouter_api_key
        if self.legacy_openrouter_base_url is not None:
            self.openrouter.base_url = self.legacy_openrouter_base_url
        if self.legacy_openrouter_model is not None:
            self.openrouter.model = self.legacy_openrouter_model
        if self.legacy_openrouter_timeout_seconds is not None:
            self.openrouter.timeout_seconds = self.legacy_openrouter_timeout_seconds
        if self.legacy_openrouter_app_name is not None:
            self.openrouter.app_name = self.legacy_openrouter_app_name
        if self.legacy_openrouter_http_referer is not None:
            self.openrouter.http_referer = self.legacy_openrouter_http_referer
        if self.legacy_openrouter_enable_thinking is not None:
            self.openrouter.enable_thinking = self.legacy_openrouter_enable_thinking
        if self.legacy_workflow_generation_provider is not None:
            self.workflow.generation_provider = self.legacy_workflow_generation_provider
        if self.legacy_workflow_generation_model is not None:
            self.workflow.generation_model = self.legacy_workflow_generation_model
        if self.legacy_workflow_intent_provider is not None:
            self.workflow.intent_provider = self.legacy_workflow_intent_provider
        if self.legacy_workflow_intent_model is not None:
            self.workflow.intent_model = self.legacy_workflow_intent_model
        if self.legacy_workflow_retrieval_limit is not None:
            self.workflow.retrieval_limit = self.legacy_workflow_retrieval_limit
        if self.legacy_workflow_retrieval_strategy is not None:
            self.workflow.retrieval_strategy = self.legacy_workflow_retrieval_strategy
        if self.legacy_phoenix_project_name is not None:
            self.phoenix.project_name = self.legacy_phoenix_project_name
        if self.legacy_phoenix_collector_endpoint is not None:
            self.phoenix.collector_endpoint = self.legacy_phoenix_collector_endpoint
        if self.legacy_phoenix_api_key is not None:
            self.phoenix.api_key = self.legacy_phoenix_api_key
        return self

    @property
    def mongodb_uri(self) -> str:
        return self.mongo.uri

    @property
    def database_name(self) -> str:
        return self.mongo.database_name

    @property
    def schemes_collection(self) -> str:
        return self.mongo.schemes_collection

    @property
    def gemini_api_key(self) -> str | None:
        return self.gemini.api_key

    @property
    def gemini_model(self) -> str:
        return self.gemini.model

    @property
    def gemini_reasoning_model(self) -> str:
        return self.gemini.reasoning_model

    @property
    def openrouter_api_key(self) -> str | None:
        return self.openrouter.api_key

    @property
    def openrouter_model(self) -> str:
        return self.openrouter.model

    def embedding_model(self, backend: Literal["local", "gemini"] | None = None) -> str:
        if self.embeddings.model:
            return self.embeddings.model
        resolved_backend = backend or self.embeddings.backend
        if resolved_backend == "local":
            return self.embeddings.local_model
        return self.embeddings.gemini_model


settings = Settings()
