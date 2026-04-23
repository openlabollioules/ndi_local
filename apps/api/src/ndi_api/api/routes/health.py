import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ndi_api.api.dependencies import PluginManagerDep
from ndi_api.services.agent_prompts import invalidate_cache as invalidate_agent_prompts_cache
from ndi_api.services.cache import get_cache_stats, invalidate_schema_cache
from ndi_api.services.llm import get_current_model, reset_current_model, set_current_model
from ndi_api.services.monitoring import monitor
from ndi_api.services.vector_store import reset_client as reset_vector_client
from ndi_api.settings import settings

# Public liveness probe (no auth required)
router = APIRouter(prefix="/health")

# Protected debug/admin endpoints (auth applied via router.py)
admin_router = APIRouter(prefix="/health")


class ModelChangeRequest(BaseModel):
    model: str


@router.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@admin_router.get("/cache/stats")
def cache_stats() -> dict:
    """Get cache statistics for performance monitoring."""
    return get_cache_stats()


@admin_router.get("/config")
def get_config() -> dict:
    return {
        "llm_model": get_current_model(),
        "indexing_llm_model": settings.indexing_llm_model or get_current_model(),
        "embedding_model": settings.embedding_model,
        "llm_base_url": settings.effective_llm_base_url,
        "llm_native_base_url": settings.llm_native_base_url,
        "auth_enabled": settings.auth_enabled,
        "auth_required": settings.auth_required,
        "llm_provider": "ollama" if "11434" in settings.llm_native_base_url else "openai-compatible",
        "database_mode": settings.database_mode,
    }


@admin_router.get("/models")
async def list_models() -> dict:
    """Liste tous les modèles disponibles sur le serveur LLM.

    Essaie d'abord ``/v1/models`` puis fallback sur ``/api/tags`` pour Ollama.
    """
    openai_error = "Échec de /v1/models"
    try:
        headers = {}
        if settings.llm_api_key and settings.llm_api_key != "EMPTY":
            headers["Authorization"] = f"Bearer {settings.llm_api_key}"

        async with httpx.AsyncClient(timeout=10.0) as client:
            openai_response = await client.get(
                f"{settings.effective_llm_base_url.rstrip('/')}/models",
                headers=headers,
            )
            openai_response.raise_for_status()
            data = openai_response.json()
            models = [m["id"] for m in data.get("data", []) if m.get("id")]
            if models:
                return {"models": models, "current": get_current_model()}
    except httpx.HTTPStatusError as e:
        openai_error = f"{e.response.status_code} sur /v1/models"
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Timeout lors de la connexion au serveur LLM.")
    except httpx.RequestError as e:
        openai_error = str(e)
    else:
        openai_error = "Aucun modèle retourné par /v1/models"

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            ollama_response = await client.get(
                f"{settings.llm_native_base_url.rstrip('/')}/api/tags",
            )
            ollama_response.raise_for_status()
            data = ollama_response.json()
            models = [m["name"] for m in data.get("models", []) if m.get("name")]
            return {"models": models, "current": get_current_model()}
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Timeout lors de la connexion à Ollama.")
    except httpx.RequestError as e:
        raise HTTPException(
            status_code=503,
            detail=f"Impossible de contacter le serveur LLM: {openai_error}; fallback Ollama: {str(e)}",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur: {str(e)}")


@admin_router.post("/model")
async def change_model(request: ModelChangeRequest) -> dict:
    """Change le modèle LLM temporairement (ne modifie pas le .env)."""
    set_current_model(request.model)
    return {"message": f"Modèle changé temporairement en: {request.model}", "current": request.model}


@admin_router.post("/model/reset")
async def reset_model() -> dict:
    """Réinitialise le modèle LLM à la valeur du .env."""
    reset_current_model()
    return {"message": "Modèle réinitialisé à la valeur par défaut.", "current": get_current_model()}


@admin_router.get("/performance")
def performance_stats() -> dict:
    """Stats de performance par étape du pipeline (avg, p95, min, max)."""
    steps = [
        "query",
        "retrieval_ms",
        "reranking_ms",
        "sql_generate_ms",
        "sql_execute_ms",
        "sql_correct_ms",
        "response_ms",
    ]
    return {step: monitor.get_stats(step) for step in steps if monitor.get_stats(step)["count"] > 0}


# =============================================================================
# Database Mode & Plugin Management
# =============================================================================


@admin_router.get("/database/mode")
def get_database_mode(manager: PluginManagerDep) -> dict:
    """Get current database mode and available plugins."""
    active = manager.get_current_mode()
    return {
        "current_mode": active if active is not None else settings.database_mode,
        "active_plugin_mode": active,
        "available_plugins": manager.get_available_plugins(),
        "supports_relations": active == "sql" if active else False,
    }


class ModeChangeRequest(BaseModel):
    mode: str  # "sql" or "nosql"


@admin_router.post("/database/mode")
def change_database_mode(request: ModeChangeRequest, manager: PluginManagerDep) -> dict:
    """Switch database mode (requires restart to take effect permanently)."""

    try:
        plugin = manager.switch_plugin(request.mode)
        return {
            "message": f"Mode changé en: {request.mode}",
            "current_mode": request.mode,
            "plugin": plugin.name,
            "supports_relations": plugin.supports_relations(),
            "note": "Pour rendre permanent, modifiez NDI_DATABASE_MODE dans .env",
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@admin_router.get("/database/plugins")
def list_plugins(manager: PluginManagerDep) -> dict:
    """List all available database plugins."""
    return {
        "available": manager.get_available_plugins(),
        "current": manager.get_current_mode(),
    }


@admin_router.post("/cache/invalidate")
def invalidate_cache() -> dict:
    """Invalidate all caches sans supprimer les données du vector store."""
    invalidate_schema_cache()
    invalidate_agent_prompts_cache()
    reset_vector_client()

    return {
        "message": "Caches vidés avec succès (schéma, requêtes, prompts). Le vector store est conservé.",
        "caches_cleared": ["schema", "nl_sql", "agent_prompts", "vector_client"],
        "note": "Les données du vector store sont conservées. Utilisez 'Purger Vector Store' pour les supprimer.",
    }
