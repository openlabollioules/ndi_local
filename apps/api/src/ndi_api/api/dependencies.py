"""FastAPI dependencies — centralised dependency injection.

Usage in routes::

    from ndi_api.api.dependencies import PluginDep, PluginManagerDep

    @router.get("/schema")
    async def get_schema(plugin: PluginDep):
        return plugin.get_schema()
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from ndi_api.plugins.base import DataPlugin
from ndi_api.plugins.manager import PluginManager, get_plugin_manager


def _get_plugin_manager() -> PluginManager:
    return get_plugin_manager()


def _get_plugin() -> DataPlugin:
    return get_plugin_manager().get_plugin()


PluginManagerDep = Annotated[PluginManager, Depends(_get_plugin_manager)]
PluginDep = Annotated[DataPlugin, Depends(_get_plugin)]
