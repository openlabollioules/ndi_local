"""Rate limiting configuration using slowapi."""

from slowapi import Limiter
from slowapi.util import get_remote_address

# Default rate: 100 requests per minute per IP
# In production, consider using Redis storage for distributed rate limiting
default_limit = "100/minute"

# Configure limiter - uses in-memory storage by default
# For production with multiple instances, use Redis:
# limiter = Limiter(key_func=get_remote_address, storage_uri="redis://localhost:6379")
limiter = Limiter(key_func=get_remote_address)

# Specific limits for different endpoint types
UPLOAD_LIMIT = "10/minute"  # File uploads are expensive
QUERY_LIMIT = "30/minute"  # NL-SQL queries involve LLM calls
EXPORT_LIMIT = "20/minute"  # Data export
PURGE_LIMIT = "3/minute"  # Destructive — strict limit
DEFAULT_LIMIT = "100/minute"  # Default for other endpoints
