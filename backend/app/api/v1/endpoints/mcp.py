"""FastAPI wiring for the ported MCP handler — exposes /api/v1/mcp (POST) and
/api/v1/mcp/functions (GET). The actual handler/schema logic lives in
app/mcp/handler.py and app/mcp/schema.py; this module just mounts them.
"""

from fastapi import APIRouter

from app.mcp.handler import MCPHandler

router = APIRouter(prefix="/mcp", tags=["mcp"])
_handler = MCPHandler()


@router.post("")
async def post_mcp(request: dict):
    return await _handler.process_request(request)


@router.get("/functions")
async def get_mcp_functions():
    return _handler.get_function_definitions()
