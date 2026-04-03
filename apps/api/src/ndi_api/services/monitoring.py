"""Advanced monitoring and logging system for NDI.

Provides separate log files for different aspects of the application:
- ingestion.log: File upload and processing times
- indexing.log: Vector indexing performance
- query.log: NL-SQL query execution with user inputs and reasoning
- audit.log: Security and access logs (already exists)
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from functools import wraps
from pathlib import Path
from typing import Any

# Create logs directory
LOGS_DIR = Path("logs")
LOGS_DIR.mkdir(exist_ok=True)


class JSONFormatter(logging.Formatter):
    """Formatter that outputs JSON for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add extra fields if present
        if hasattr(record, "extra_data"):
            log_data.update(record.extra_data)

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data, default=str)


def setup_logger(name: str, filename: str, level: int = logging.INFO, json_format: bool = True) -> logging.Logger:
    """Setup a dedicated logger with file handler."""
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Remove existing handlers
    logger.handlers = []

    # File handler
    file_handler = logging.FileHandler(LOGS_DIR / filename)
    file_handler.setLevel(level)

    if json_format:
        formatter = JSONFormatter()
    else:
        formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S")

    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # Prevent propagation to root logger
    logger.propagate = False

    return logger


# Dedicated loggers
ingestion_logger = setup_logger("ndi.ingestion", "ingestion.log")
indexing_logger = setup_logger("ndi.indexing", "indexing.log")
query_logger = setup_logger("ndi.query", "query.log")
reasoning_logger = setup_logger("ndi.reasoning", "reasoning.log")


@dataclass
class QueryLogEntry:
    """Structured entry for query logging."""

    timestamp: str
    user_input: str
    schema_context: str
    sql_generated: str
    sql_valid: bool
    execution_time_ms: float
    total_time_ms: float
    rows_count: int
    cache_hit: bool
    error: str | None = None
    retrieval_info: dict | None = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class IngestionLogEntry:
    """Structured entry for ingestion logging."""

    timestamp: str
    filename: str
    file_size_bytes: int
    file_type: str
    processing_time_ms: float
    rows_processed: int
    columns_count: int
    table_name: str
    success: bool
    error: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class IndexingLogEntry:
    """Structured entry for indexing logging."""

    timestamp: str
    table_name: str
    columns_count: int
    indexing_time_ms: float
    llm_calls: int
    documents_indexed: int
    success: bool
    error: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


# Context managers for timing
@contextmanager
def log_ingestion_time(filename: str, file_size: int, file_type: str):
    """Context manager to log ingestion performance."""
    start = time.time()
    entry = {
        "filename": filename,
        "file_size_bytes": file_size,
        "file_type": file_type,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    }

    try:
        yield entry
        entry["processing_time_ms"] = (time.time() - start) * 1000
        entry["success"] = True
        entry["error"] = None
        ingestion_logger.info("Ingestion completed", extra={"extra_data": entry})
    except Exception as e:
        entry["processing_time_ms"] = (time.time() - start) * 1000
        entry["success"] = False
        entry["error"] = str(e)
        ingestion_logger.error("Ingestion failed", extra={"extra_data": entry})
        raise


@contextmanager
def log_indexing_time(table_name: str, columns_count: int):
    """Context manager to log indexing performance."""
    start = time.time()
    llm_calls = [0]  # Use list to allow modification in nested scope

    entry = {
        "table_name": table_name,
        "columns_count": columns_count,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "llm_calls": llm_calls,
    }

    try:
        yield entry, llm_calls
        entry["indexing_time_ms"] = (time.time() - start) * 1000
        entry["success"] = True
        entry["error"] = None
        indexing_logger.info("Indexing completed", extra={"extra_data": entry})
    except Exception as e:
        entry["indexing_time_ms"] = (time.time() - start) * 1000
        entry["success"] = False
        entry["error"] = str(e)
        indexing_logger.error("Indexing failed", extra={"extra_data": entry})
        raise


def log_indexing_complete(
    duration: float,
    table_count: int,
    document_count: int,
    llm_calls: int,
):
    """Log indexing completion with metrics."""
    entry = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "indexing_time_ms": duration * 1000,
        "table_count": table_count,
        "document_count": document_count,
        "llm_calls": llm_calls,
        "success": True,
    }
    indexing_logger.info("Indexing batch completed", extra={"extra_data": entry})


def log_query_complete(entry: QueryLogEntry):
    """Log a completed query with all details."""
    query_logger.info(f"Query executed: {entry.user_input[:50]}...", extra={"extra_data": entry.to_dict()})


def log_user_input(question: str, client_ip: str = "unknown"):
    """Log user input for analysis."""
    query_logger.info(
        "User input received",
        extra={
            "extra_data": {
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "question": question,
                "client_ip": client_ip,
                "question_length": len(question),
                "detected_language": "fr" if any(c in question for c in "éèàù") else "en",
            }
        },
    )


def log_reasoning_step(step: str, details: dict[str, Any]):
    """Log a reasoning step from the NL-SQL workflow."""
    query_logger.debug(
        f"Reasoning: {step}",
        extra={
            "extra_data": {
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "step": step,
                "details": details,
            }
        },
    )


class PerformanceMonitor:
    """Monitor and log performance metrics (bounded)."""

    _MAX_KEYS = 50  # max distinct metric names
    _MAX_VALUES = 500  # max values retained per metric

    def __init__(self):
        self.metrics: dict[str, list[float]] = {
            "ingestion": [],
            "indexing": [],
            "query": [],
            "embedding": [],
        }

    def record(self, metric_name: str, value_ms: float):
        """Record a metric value (auto-creates new metric keys)."""
        if metric_name not in self.metrics:
            # Evict least-used key if we hit the cap
            if len(self.metrics) >= self._MAX_KEYS:
                smallest = min(self.metrics, key=lambda k: len(self.metrics[k]))
                del self.metrics[smallest]
            self.metrics[metric_name] = []
        self.metrics[metric_name].append(value_ms)
        if len(self.metrics[metric_name]) > self._MAX_VALUES:
            self.metrics[metric_name] = self.metrics[metric_name][-self._MAX_VALUES :]

    def get_stats(self, metric_name: str) -> dict[str, float]:
        """Get statistics for a metric."""
        values = self.metrics.get(metric_name, [])
        if not values:
            return {"count": 0, "avg": 0, "min": 0, "max": 0, "p95": 0}

        sorted_values = sorted(values)
        p95_idx = int(len(sorted_values) * 0.95)

        return {
            "count": len(values),
            "avg": sum(values) / len(values),
            "min": min(values),
            "max": max(values),
            "p95": sorted_values[min(p95_idx, len(sorted_values) - 1)],
        }

    def get_summary(self) -> dict:
        """Get performance summary as dict."""
        return {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "metrics": {name: self.get_stats(name) for name in self.metrics if self.get_stats(name)["count"] > 0},
        }

    def reset(self) -> None:
        """Clear all collected metrics."""
        self.metrics.clear()


# Global monitor instance
monitor = PerformanceMonitor()


def timed(metric_name: str):
    """Decorator to time function execution."""

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            start = time.time()
            try:
                result = func(*args, **kwargs)
                elapsed = (time.time() - start) * 1000
                monitor.record(metric_name, elapsed)
                return result
            except Exception:
                elapsed = (time.time() - start) * 1000
                monitor.record(metric_name, elapsed)
                raise

        return wrapper

    return decorator


def get_monitoring_stats() -> dict[str, Any]:
    """Get current monitoring statistics."""
    return {
        "performance": monitor.get_summary(),
        "log_files": {
            "ingestion": str(LOGS_DIR / "ingestion.log"),
            "indexing": str(LOGS_DIR / "indexing.log"),
            "query": str(LOGS_DIR / "query.log"),
            "reasoning": str(LOGS_DIR / "reasoning.log"),
        },
    }
