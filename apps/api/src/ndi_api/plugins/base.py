"""Base interface for NDI data plugins.

Defines the contract that all database plugins must implement.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import pandas as pd


@dataclass
class ColumnInfo:
    """Column metadata."""

    name: str
    type: str  # Native database type or normalized type
    nullable: bool = True
    description: str | None = None


@dataclass
class TableSchema:
    """Schema definition for a table/collection."""

    name: str
    columns: list[ColumnInfo] = field(default_factory=list)
    # For NoSQL: store sample fields from documents
    sample_fields: dict[str, Any] = field(default_factory=dict)


@dataclass
class QueryResult:
    """Result of a query execution."""

    rows: list[dict] = field(default_factory=list)
    columns: list[str] = field(default_factory=list)
    total_count: int = 0
    query_text: str = ""  # The actual query executed (SQL or NoSQL equivalent)
    error: str | None = None


@dataclass
class SchemaInfo:
    """Complete schema information for the database."""

    tables: list[TableSchema] = field(default_factory=list)
    # For SQL: relationships between tables
    relations: list[dict] = field(default_factory=list)


class DataPlugin(ABC):
    """Abstract base class for database plugins.

    All database backends (DuckDB, MongoDB, etc.) must implement this interface.
    """

    name: str = "base"
    mode: str = "abstract"  # "sql" or "nosql"

    # -----------------------------------------------------------------------
    # Connection & Lifecycle
    # -----------------------------------------------------------------------

    @abstractmethod
    def initialize(self) -> None:
        """Initialize the database connection and ensure data structures exist."""
        pass

    @abstractmethod
    def close(self) -> None:
        """Close database connections and cleanup resources."""
        pass

    @abstractmethod
    def purge(self) -> bool:
        """Delete all data and reset the database. Returns True if successful."""
        pass

    # -----------------------------------------------------------------------
    # Ingestion
    # -----------------------------------------------------------------------

    @abstractmethod
    def ingest_dataframe(
        self,
        df: pd.DataFrame,
        name: str,
        on_step: Callable[[str, str], None] | None = None,
    ) -> str:
        """Ingest a DataFrame into the database.

        Args:
            df: DataFrame to ingest
            name: Desired name for the table/collection
            on_step: Optional callback for progress updates

        Returns:
            The actual name assigned (may be modified to avoid collisions)
        """
        pass

    @abstractmethod
    def read_file(self, file_bytes: bytes, filename: str, sheet_name: str | int | None = None) -> pd.DataFrame:
        """Read a file into a DataFrame.

        Args:
            file_bytes: Raw file content
            filename: Original filename (used to determine format)
            sheet_name: For Excel files, specific sheet to read

        Returns:
            DataFrame containing the file data
        """
        pass

    # -----------------------------------------------------------------------
    # Schema & Metadata
    # -----------------------------------------------------------------------

    @abstractmethod
    def list_tables(self) -> list[str]:
        """List all tables/collections in the database."""
        pass

    @abstractmethod
    def get_schema(self) -> SchemaInfo:
        """Get complete schema information for all tables/collections."""
        pass

    @abstractmethod
    def get_table_schema(self, name: str) -> TableSchema | None:
        """Get schema for a specific table/collection."""
        pass

    @abstractmethod
    def table_exists(self, name: str) -> bool:
        """Check if a table/collection exists."""
        pass

    # -----------------------------------------------------------------------
    # Querying
    # -----------------------------------------------------------------------

    @abstractmethod
    def execute_query(self, query: str, limit: int | None = None) -> QueryResult:
        """Execute a raw query (SQL for SQL mode, query expression for NoSQL).

        Args:
            query: Query string
            limit: Maximum number of rows to return

        Returns:
            QueryResult containing rows and metadata
        """
        pass

    @abstractmethod
    def preview_table(self, name: str, limit: int = 50, offset: int = 0) -> QueryResult:
        """Get a preview of a table/collection with pagination.

        Args:
            name: Table/collection name
            limit: Number of rows to return
            offset: Number of rows to skip

        Returns:
            QueryResult containing paginated data
        """
        pass

    # -----------------------------------------------------------------------
    # NL-to-Query specific
    # -----------------------------------------------------------------------

    @abstractmethod
    def get_query_context(self, question: str, relevant_items: list[str]) -> str:
        """Build query context for NL-to-Query generation.

        Args:
            question: The natural language question
            relevant_items: Relevant schema items from vector search

        Returns:
            Context string for the LLM prompt
        """
        pass

    @abstractmethod
    def validate_query(self, query: str) -> tuple[bool, str]:
        """Validate a query for safety (read-only, no dangerous operations).

        Args:
            query: Query string to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        pass

    @abstractmethod
    def get_system_prompt(self) -> str:
        """Get the system prompt for NL-to-Query generation.

        Returns:
            System prompt tailored for this database type
        """
        pass

    # -----------------------------------------------------------------------
    # Relations (SQL mode mainly)
    # -----------------------------------------------------------------------

    def supports_relations(self) -> bool:
        """Return True if this plugin supports table relations (SQL only)."""
        return self.mode == "sql"

    def get_relations(self) -> list[dict]:
        """Get declared relations between tables (SQL mode only).

        Returns:
            List of relation dictionaries
        """
        return []

    def save_relation(self, relation: dict) -> bool:
        """Save a relation between tables (SQL mode only).

        Args:
            relation: Relation dictionary with from_table, from_column, etc.

        Returns:
            True if successful
        """
        return False

    # -----------------------------------------------------------------------
    # Stats & Sampling
    # -----------------------------------------------------------------------

    @abstractmethod
    def get_table_stats(self, name: str) -> dict[str, Any]:
        """Get statistics about a table/collection.

        Args:
            name: Table/collection name

        Returns:
            Dictionary with stats (row_count, column_stats, etc.)
        """
        pass

    @abstractmethod
    def get_sample_data(self, name: str, limit: int = 100) -> list[dict]:
        """Get sample data from a table/collection.

        Args:
            name: Table/collection name
            limit: Number of rows to sample

        Returns:
            List of row dictionaries
        """
        pass
