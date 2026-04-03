from fastapi import APIRouter

from ndi_api.api.dependencies import PluginDep
from ndi_api.schemas.schema import ColumnInfo, TableInfo

router = APIRouter(prefix="/schema")


@router.get("", response_model=list[TableInfo])
async def get_schema(plugin: PluginDep) -> list[TableInfo]:
    schema_info = plugin.get_schema()
    return [
        TableInfo(name=table.name, columns=[ColumnInfo(name=c.name, type=c.type) for c in table.columns])
        for table in schema_info.tables
    ]
