"""Request logging middleware for audit trail."""

import logging
import time
from collections.abc import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

# Configure audit logger
audit_logger = logging.getLogger("ndi_audit")
audit_logger.setLevel(logging.INFO)

# Create file handler for audit logs
audit_handler = logging.FileHandler("logs/audit.log")
audit_handler.setLevel(logging.INFO)

# Formatter
formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
audit_handler.setFormatter(formatter)
audit_logger.addHandler(audit_handler)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware to log all API requests for audit purposes."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip logging for health checks and static files
        if request.url.path in ["/health", "/api/health/health"] or "/static/" in request.url.path:
            return await call_next(request)

        start_time = time.time()

        # Extract client info
        client_ip = request.client.host if request.client else "unknown"
        method = request.method
        path = request.url.path

        # Get API key if present
        api_key = request.headers.get("X-API-Key", "none")

        # Process request
        try:
            response = await call_next(request)
            duration = time.time() - start_time

            # Log successful request
            audit_logger.info(
                f"{client_ip} | {method} {path} | {response.status_code} | "
                f"{duration:.3f}s | api_key={api_key[:8] + '...' if api_key != 'none' else 'none'}"
            )

            return response

        except Exception as e:
            duration = time.time() - start_time
            audit_logger.error(
                f"{client_ip} | {method} {path} | ERROR | {duration:.3f}s | "
                f"error={str(e)} | api_key={api_key[:8] + '...' if api_key != 'none' else 'none'}"
            )
            raise
