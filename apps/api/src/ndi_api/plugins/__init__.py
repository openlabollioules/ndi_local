"""Plugin system for NDI - Database backend abstraction.

This module provides a plugin architecture to support multiple database backends:
- SQL mode (DuckDB): Relational data with JOINs
- NoSQL mode (MongoDB): Document-oriented data

Usage:
    from ndi_api.plugins import get_plugin_manager

    plugin = get_plugin_manager().get_plugin()
    plugin.ingest_dataframe(df, "table_name")
    result = plugin.execute_query(query)
"""

from ndi_api.plugins.base import ColumnInfo, DataPlugin, QueryResult, TableSchema
from ndi_api.plugins.manager import PluginManager, get_plugin_manager

__all__ = [
    "DataPlugin",
    "QueryResult",
    "TableSchema",
    "ColumnInfo",
    "PluginManager",
    "get_plugin_manager",
]
