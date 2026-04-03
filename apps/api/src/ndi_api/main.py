import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from ndi_api.api.router import api_router
from ndi_api.services.logging import RequestLoggingMiddleware
from ndi_api.services.rate_limiter import limiter
from ndi_api.settings import settings

# Configure root logger
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s | %(name)s | %(levelname)s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name, description="API pour Naval Data Intelligence - NL to SQL", version="0.2.0")

    # Add rate limiting
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    # Add audit logging middleware
    app.add_middleware(RequestLoggingMiddleware)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["Content-Type", "Authorization", "X-API-Key"],
    )

    # Global exception handler - no stack traces in production
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.error(f"Unhandled exception: {exc}", exc_info=settings.environment == "local")

        if settings.environment == "local":
            # In development, return detailed error
            return JSONResponse(status_code=500, content={"detail": f"Internal error: {str(exc)}"})
        else:
            # In production, return generic error
            return JSONResponse(
                status_code=500, content={"detail": "An internal error occurred. Please try again later."}
            )

    app.include_router(api_router, prefix=settings.api_prefix)
    return app


app = create_app()
