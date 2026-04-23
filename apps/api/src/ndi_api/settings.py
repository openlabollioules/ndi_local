from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Path to the .env file — used by BaseSettings below
env_path = Path(__file__).parent.parent.parent / ".env"


def _normalize_openai_base_url(url: str) -> str:
    """Normalize a model server URL to an OpenAI-compatible ``.../v1`` base."""
    stripped = url.strip().rstrip("/")
    parsed = urlsplit(stripped)
    path = parsed.path.rstrip("/")
    if not path.endswith("/v1"):
        path = f"{path}/v1" if path else "/v1"
    return urlunsplit((parsed.scheme, parsed.netloc, path, parsed.query, parsed.fragment))


def _to_native_model_server_url(url: str) -> str:
    """Return the server root without a trailing OpenAI ``/v1`` suffix."""
    stripped = url.strip().rstrip("/")
    parsed = urlsplit(stripped)
    path = parsed.path.rstrip("/")
    if path.endswith("/v1"):
        path = path[:-3].rstrip("/")
    return urlunsplit((parsed.scheme, parsed.netloc, path, parsed.query, parsed.fragment))


class Settings(BaseSettings):
    app_name: str = "NDI NL-to-SQL API"
    api_prefix: str = "/api"
    environment: str = "local"
    allowed_origins: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    # Database Mode Configuration
    database_mode: str = Field(
        "sql",
        description="Database mode: 'sql' (DuckDB) or 'nosql' (document store) (NDI_DATABASE_MODE)",
    )

    # SQL Mode (DuckDB) settings
    data_dir: str = "data"
    duckdb_filename: str = "ndi.duckdb"

    # Vector store (Qdrant)
    qdrant_url: str = Field("http://localhost:6333", description="Qdrant server URL (NDI_QDRANT_URL)")
    qdrant_api_key: str | None = Field(None, description="Qdrant API key if auth enabled (NDI_QDRANT_API_KEY)")
    qdrant_collection: str = Field("schema_index", description="Qdrant collection name (NDI_QDRANT_COLLECTION)")

    # LLM — vLLM / OpenAI-compatible
    llm_base_url: str = Field("http://localhost:11434", description="Base URL du serveur LLM OpenAI-compatible (NDI_LLM_BASE_URL)")
    llm_api_key: str = Field("ollama", description="Clé API LLM (NDI_LLM_API_KEY)")
    llm_model: str = Field("qwen3:14b", description="Modèle LLM pour les requêtes (NDI_LLM_MODEL)")
    llm_reasoning_effort: str = Field(
        "high",
        description="Niveau de reasoning demandé au serveur OpenAI-compatible (NDI_LLM_REASONING_EFFORT)",
    )
    vision_model: str | None = Field(None, description="Modèle VLM pour l'analyse d'images (NDI_VISION_MODEL)")
    indexing_llm_model: str | None = Field(None, description="Modèle LLM pour l'indexation (NDI_INDEXING_LLM_MODEL)")
    llm_context_length: int = Field(32768, description="Taille du contexte LLM en tokens (NDI_LLM_CONTEXT_LENGTH)")

    # Embeddings — OpenAI-compatible
    embedding_base_url: str | None = Field(
        None, description="Base URL embeddings (NDI_EMBEDDING_BASE_URL) — si vide, utilise llm_base_url"
    )
    embedding_api_key: str | None = Field(
        None, description="Clé API embeddings (NDI_EMBEDDING_API_KEY) — si vide, utilise llm_api_key"
    )
    embedding_model: str = Field("nomic-embed-text", description="Modèle d'embedding (NDI_EMBEDDING_MODEL)")

    retrieval_top_k: int = 6
    indexing_enabled: bool = True

    # Query result limits
    sql_result_limit: int = Field(0, description="Maximum rows returned by SQL queries (0 = unlimited)")
    sql_result_default_limit: int = Field(0, description="Default rows returned by SQL queries (0 = unlimited)")

    # Open analysis settings
    analysis_max_rows: int = Field(0, description="Maximum rows for open analysis (0 = unlimited)")

    # Authentication
    api_key: str | None = Field(None, description="API key for authentication (NDI_API_KEY)")
    auth_enabled: bool = Field(True, description="Enable API key authentication (NDI_AUTH_ENABLED)")

    # Re-ranker configuration
    use_reranker: bool = Field(True, description="Enable re-ranker for retrieval (NDI_USE_RERANKER)")
    reranker_type: str = Field("lightweight", description="Re-ranker type: lightweight, none (NDI_RERANKER_TYPE)")
    reranker_model: str = Field("bge-reranker-v2-m3", description="Re-ranker model name (NDI_RERANKER_MODEL)")
    retrieval_k: int = Field(10, description="Number of documents to retrieve before re-ranking (NDI_RETRIEVAL_K)")
    reranker_final_k: int = Field(8, description="Documents to keep after re-ranking (NDI_RERANKER_FINAL_K)")

    # Cache TTLs (seconds, 0 = no caching)
    cache_ttl_query: int = Field(3600, description="TTL for NL-SQL query cache in seconds (NDI_CACHE_TTL_QUERY)")
    cache_ttl_schema: int = Field(300, description="TTL for schema cache in seconds (NDI_CACHE_TTL_SCHEMA)")
    cache_ttl_embedding: int = Field(600, description="TTL for embedding cache in seconds (NDI_CACHE_TTL_EMBEDDING)")

    # Agent prompts configuration (AGENTS.md + SKILL.md)
    agents_base_dir: str | None = Field(
        None, description="Base directory for AGENTS.md and skills (NDI_AGENTS_BASE_DIR)"
    )
    agents_memory_file: str = Field("AGENTS.md", description="Memory file name (NDI_AGENTS_MEMORY_FILE)")
    agents_skills_dir: str = Field("skills", description="Skills directory name (NDI_AGENTS_SKILLS_DIR)")

    # Computed helpers
    @property
    def effective_llm_base_url(self) -> str:
        return _normalize_openai_base_url(self.llm_base_url)

    @property
    def llm_native_base_url(self) -> str:
        return _to_native_model_server_url(self.llm_base_url)

    @property
    def effective_embedding_base_url(self) -> str:
        return _normalize_openai_base_url(self.embedding_base_url or self.llm_base_url)

    @property
    def embedding_native_base_url(self) -> str:
        return _to_native_model_server_url(self.embedding_base_url or self.llm_base_url)

    @property
    def effective_embedding_api_key(self) -> str:
        return self.embedding_api_key or self.llm_api_key

    @property
    def auth_required(self) -> bool:
        if not self.auth_enabled:
            return False
        if self.api_key not in {None, "", "EMPTY", "empty"}:
            return True
        return self.environment != "local"

    model_config = SettingsConfigDict(env_prefix="NDI_", env_file=env_path, extra="ignore")


settings = Settings()
