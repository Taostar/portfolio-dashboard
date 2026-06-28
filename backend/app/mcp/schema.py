"""Schema definitions for the MCP (Multi-modal Conversational Protocol) module.
These schemas define the function signatures that can be used by LLMs and AI agents.

Ported unchanged from Questrade-API/mcp/schema.py — this file has zero broker
coupling.
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class MCPRequest(BaseModel):
    """Base model for MCP requests."""
    type: str = Field("function", description="The type of request, default is 'function'")
    function: str = Field(..., description="The function name to call")
    arguments: Dict[str, Any] = Field(default_factory=dict, description="The arguments for the function")
    conversation_id: Optional[str] = Field(None, description="Optional conversation ID for tracking")


class MCPResponse(BaseModel):
    """Base model for MCP responses."""
    type: str = Field("function_result", description="The type of response")
    function: str = Field(..., description="The function that was called")
    result: Any = Field(..., description="The result of the function call")
    status: str = Field("success", description="The status of the function call")
    error: Optional[str] = Field(None, description="Error message if status is 'error'")
    conversation_id: Optional[str] = Field(None, description="Conversation ID from the request")


# Function-specific schemas
class GetAccountsArguments(BaseModel):
    """Arguments for get_accounts function."""
    pass


class GetAccountHoldingsArguments(BaseModel):
    """Arguments for get_account_holdings function."""
    account_id: str = Field(..., description="The account ID to get holdings for")


class GetAllHoldingsArguments(BaseModel):
    """Arguments for get_all_holdings function."""
    pass


class GetMarketDataArguments(BaseModel):
    """Arguments for get_market_data function."""
    symbol: str = Field(..., description="The symbol to get market data for")
    days: int = Field(30, description="Number of days of historical data to retrieve")
    interval: str = Field("OneDay", description="Interval for the data (OneDay, OneHour, etc.)")


# Order functionality removed as requested


# Function definitions in OpenAI format
FUNCTION_DEFINITIONS = [
    {
        "name": "get_accounts",
        "description": "Get all Questrade accounts the user has access to",
        "parameters": GetAccountsArguments.schema()
    },
    {
        "name": "get_account_holdings",
        "description": "Get holdings for a specific Questrade account",
        "parameters": GetAccountHoldingsArguments.schema()
    },
    {
        "name": "get_all_holdings",
        "description": "Get holdings for all Questrade accounts",
        "parameters": GetAllHoldingsArguments.schema()
    },
    {
        "name": "get_market_data",
        "description": "Get market performance data for a specific symbol",
        "parameters": GetMarketDataArguments.schema()
    }
]
