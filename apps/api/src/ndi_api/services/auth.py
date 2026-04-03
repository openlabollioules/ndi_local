"""Authentication dependency for API endpoints.

Behaviour:
- ``NDI_AUTH_ENABLED=false`` → auth disabled, all requests pass.
- ``NDI_API_KEY`` set to a real value → header must match exactly.
- ``NDI_API_KEY`` empty / "EMPTY" / unset → **any non-empty** ``X-API-Key``
  header is accepted.  This lets users inject a key from the frontend
  dialog without configuring the server.
"""

from fastapi import HTTPException, Request, Security, status
from fastapi.security import APIKeyHeader

from ndi_api.settings import settings

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

_EMPTY_SENTINELS = {None, "", "EMPTY", "empty"}


def _server_key_configured() -> bool:
    """True if the server has a real API key (not empty/EMPTY)."""
    return settings.api_key not in _EMPTY_SENTINELS


def _extract_key(request: Request, header_key: str | None) -> str | None:
    """Extract API key from header OR query param ``api_key``.

    Query-param fallback is needed for EventSource/SSE endpoints which
    cannot send custom headers.
    """
    if header_key:
        return header_key
    return request.query_params.get("api_key")


def verify_api_key(
    request: Request,
    api_key: str | None = Security(api_key_header),
) -> str:
    """Verify API key (from header or query param).

    - Auth disabled → always pass.
    - Server key configured → key must match exactly.
    - Server key empty → accept any non-empty client key.
    - Local dev with no key at all → pass with "dev-mode".
    """
    key = _extract_key(request, api_key)

    if not settings.auth_enabled:
        return key or "dev-mode"

    if _server_key_configured():
        if key != settings.api_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API key",
            )
        return key

    # No server key configured — accept any non-empty client key
    if key and key not in _EMPTY_SENTINELS:
        return key

    if settings.environment == "local":
        return "dev-mode"

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="API key required. Configure it in the frontend settings.",
    )


def optional_auth(api_key: str | None = Security(api_key_header)) -> str | None:
    """Optional authentication — returns key if provided, None otherwise."""
    if not settings.auth_enabled:
        return api_key
    return api_key
