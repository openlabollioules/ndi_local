"""Plugin manager for NDI database backends.

Handles plugin registration, instantiation based on configuration,
and provides a singleton access pattern.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from ndi_api.settings import settings

if TYPE_CHECKING:
    from ndi_api.plugins.base import DataPlugin

_logger = logging.getLogger("ndi.plugins")


class PluginManager:
    """Manager for database plugins.

    Handles plugin discovery, registration, and lifecycle management.
    """

    _instance: PluginManager | None = None
    _plugin: DataPlugin | None = None

    def __new__(cls) -> PluginManager:
        """Singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialize the plugin manager."""
        self._plugins: dict[str, type[DataPlugin]] = {}
        self._register_builtin_plugins()

    def _register_builtin_plugins(self) -> None:
        """Register built-in plugins (SQL and NoSQL)."""
        # Import here to avoid circular imports
        try:
            from ndi_api.plugins.sql_plugin import SQLPlugin

            self.register_plugin(SQLPlugin)
        except ImportError as e:
            _logger.warning(f"SQL plugin not available: {e}")

        try:
            from ndi_api.plugins.nosql_plugin import NoSQLPlugin

            self.register_plugin(NoSQLPlugin)
        except ImportError as e:
            _logger.warning(f"NoSQL plugin not available: {e}")

    def register_plugin(self, plugin_class: type[DataPlugin]) -> None:
        """Register a plugin class.

        Args:
            plugin_class: Plugin class that implements DataPlugin
        """
        self._plugins[plugin_class.name] = plugin_class
        _logger.info(f"Registered plugin: {plugin_class.name} ({plugin_class.mode})")

    def get_available_plugins(self) -> list[dict]:
        """Get list of available plugins with their info.

        Returns:
            List of plugin info dictionaries
        """
        return [
            {
                "name": name,
                "mode": plugin_class.mode,
                "class": plugin_class.__name__,
            }
            for name, plugin_class in self._plugins.items()
        ]

    def get_plugin(self, name: str | None = None) -> DataPlugin:
        """Get or create a plugin instance.

        Args:
            name: Plugin name to use. If None, uses settings.database_mode.

        Returns:
            Plugin instance

        Raises:
            ValueError: If the plugin is not found
        """
        # Use configured mode if no name provided
        if name is None:
            name = getattr(settings, "database_mode", "sql")

        # Return cached instance if same type
        if self._plugin is not None and self._plugin.name == name:
            return self._plugin

        # Close existing plugin if switching
        if self._plugin is not None:
            _logger.info(f"Closing previous plugin: {self._plugin.name}")
            self._plugin.close()
            self._plugin = None

        # Create new plugin instance
        if name not in self._plugins:
            available = ", ".join(self._plugins.keys())
            raise ValueError(f"Unknown plugin: '{name}'. Available: {available}")

        plugin_class = self._plugins[name]
        _logger.info(f"Initializing plugin: {name}")
        self._plugin = plugin_class()
        self._plugin.initialize()

        return self._plugin

    def switch_plugin(self, name: str) -> DataPlugin:
        """Switch to a different plugin.

        Args:
            name: Name of the plugin to switch to

        Returns:
            New plugin instance
        """
        _logger.info(f"Switching plugin to: {name}")
        return self.get_plugin(name)

    def get_current_mode(self) -> str | None:
        """Get the current database mode.

        Returns:
            Current mode ("sql", "nosql") or None if no plugin active
        """
        if self._plugin is None:
            return None
        return self._plugin.mode

    def close(self) -> None:
        """Close the current plugin and cleanup."""
        if self._plugin is not None:
            _logger.info(f"Closing plugin: {self._plugin.name}")
            self._plugin.close()
            self._plugin = None


# Global singleton instance
_manager: PluginManager | None = None


def get_plugin_manager() -> PluginManager:
    """Get the global plugin manager instance.

    Returns:
        PluginManager singleton
    """
    global _manager
    if _manager is None:
        _manager = PluginManager()
    return _manager


def get_plugin(name: str | None = None) -> DataPlugin:
    """Convenience function to get the current plugin.

    Args:
        name: Plugin name, or None for configured default

    Returns:
        DataPlugin instance
    """
    return get_plugin_manager().get_plugin(name)
