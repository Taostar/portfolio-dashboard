"""Handler for MCP (Multi-modal Conversational Protocol) requests.
This module processes MCP requests, calls the appropriate functions, and formats the responses.

Ported from Questrade-API/mcp/handler.py. `process_request()`, error-response
logic, `get_function_definitions()`, and `process_natural_language()` are
ported unchanged. The 4 `_get_*` methods are rewired to call through this
backend's already-ported `_questrade_internal` helpers / `QuestradeProvider`
instead of making raw `qtrade`/old-`utils.*` calls directly (see
backend/app/providers/_questrade_internal/ and backend/app/providers/questrade.py).

Shape notes (kept for the eventual live-parity check):
- get_accounts / get_account_holdings / get_all_holdings stay per-account
  (via _questrade_internal.holdings helpers), since QuestradeProvider.get_holdings()
  is grouped by symbol across all accounts and would lose that structure.
- get_market_data routes through QuestradeProvider.get_market_data(), whose
  DataFrame carries no symbol "name"/description field, so "name" is left as
  "" rather than re-fetching ticker_information just for this.
"""

import logging
import json
from datetime import datetime
from typing import Dict, Any, List, Optional, Union, Tuple

from pydantic import ValidationError

from app.providers._questrade_internal.auth import get_questrade_client, get_questrade_clients
from app.providers._questrade_internal.holdings import get_account_positions, get_all_account_positions_multi
from app.providers.questrade import QuestradeProvider
from app.mcp.schema import (
    MCPRequest,
    MCPResponse,
    GetAccountsArguments,
    GetAccountHoldingsArguments,
    GetAllHoldingsArguments,
    GetMarketDataArguments,
    FUNCTION_DEFINITIONS,
)

# Configure logging
logger = logging.getLogger(__name__)


class MCPHandler:
    """Handler for MCP requests."""

    def __init__(self):
        """Initialize the MCP handler."""
        self.function_map = {
            "get_accounts": self._get_accounts,
            "get_account_holdings": self._get_account_holdings,
            "get_all_holdings": self._get_all_holdings,
            "get_market_data": self._get_market_data
        }
        self.function_definitions = FUNCTION_DEFINITIONS

    def get_function_definitions(self) -> List[Dict[str, Any]]:
        """Get the function definitions in OpenAI format."""
        return self.function_definitions

    async def process_request(self, request_data: Union[str, Dict[str, Any]]) -> Dict[str, Any]:
        """
        Process an MCP request and return the response.

        Args:
            request_data: The request data, either as a JSON string or a dictionary

        Returns:
            The response as a dictionary
        """
        # Parse the request if it's a string
        if isinstance(request_data, str):
            try:
                request_data = json.loads(request_data)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse request JSON: {e}")
                return self._create_error_response(
                    "invalid_request",
                    "Failed to parse request JSON",
                    None
                )

        # Validate the request
        try:
            request = MCPRequest(**request_data)
        except ValidationError as e:
            logger.error(f"Invalid request format: {e}")
            return self._create_error_response(
                "invalid_request",
                f"Invalid request format: {e}",
                request_data.get("function") if isinstance(request_data, dict) else None,
                request_data.get("conversation_id") if isinstance(request_data, dict) else None
            )

        # Check if the function exists
        if request.function not in self.function_map:
            logger.error(f"Unknown function: {request.function}")
            return self._create_error_response(
                "unknown_function",
                f"Unknown function: {request.function}",
                request.function,
                request.conversation_id
            )

        # Call the function
        try:
            result = await self.function_map[request.function](request.arguments)
            return MCPResponse(
                function=request.function,
                result=result,
                status="success",
                conversation_id=request.conversation_id
            ).dict()
        except Exception as e:
            logger.error(f"Error executing function {request.function}: {e}")
            return self._create_error_response(
                "execution_error",
                f"Error executing function: {e}",
                request.function,
                request.conversation_id
            )

    def process_natural_language(self, query: str) -> Tuple[Dict[str, Any], Optional[Dict[str, Any]]]:
        """
        Process a natural language query and determine the appropriate function to call.
        This is a placeholder for future implementation with an LLM.

        Args:
            query: The natural language query

        Returns:
            A tuple containing (function_call_info, response)
            If a function call is needed, function_call_info will contain the details and response will be None
            If a direct response is possible, response will contain the response and function_call_info will be None
        """
        # This would typically use an LLM to parse the query and determine the function
        # For now, we'll return a simple message about the capability
        return None, {
            "type": "text",
            "content": "Natural language processing is not yet implemented. Please use the function calling format."
        }

    def _create_error_response(
        self,
        error_type: str,
        error_message: str,
        function: Optional[str] = None,
        conversation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create an error response."""
        return {
            "type": "function_result",
            "function": function or "unknown",
            "result": None,
            "status": "error",
            "error": f"{error_type}: {error_message}",
            "conversation_id": conversation_id
        }

    async def _get_accounts(self, arguments: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get all accounts across every configured Questrade login."""
        try:
            GetAccountsArguments(**arguments)
        except ValidationError as e:
            logger.error(f"Invalid arguments for get_accounts: {e}")
            raise ValueError(f"Invalid arguments: {e}")

        merged: List[Dict[str, Any]] = []
        seen = set()
        for client in get_questrade_clients():
            try:
                for acc in client.get_accounts().get('accounts', []):
                    key = acc.get('number')
                    if key in seen:
                        continue
                    seen.add(key)
                    merged.append(acc)
            except Exception as e:
                logger.warning(f"Failed to fetch accounts from one client: {e}")
        return merged

    async def _get_account_holdings(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Get holdings for a specific account. Searches every configured login
        to find the one that owns the requested account_id."""
        try:
            args = GetAccountHoldingsArguments(**arguments)
        except ValidationError as e:
            logger.error(f"Invalid arguments for get_account_holdings: {e}")
            raise ValueError(f"Invalid arguments: {e}")

        owning_client = None
        try:
            target = int(args.account_id)
        except (TypeError, ValueError):
            target = args.account_id
        for client in get_questrade_clients():
            try:
                ids = client.get_account_id()
            except Exception as e:
                logger.warning(f"Could not list accounts on a client: {e}")
                continue
            if target in ids or str(target) in [str(i) for i in ids]:
                owning_client = client
                break
        if owning_client is None:
            raise ValueError(f"Account {args.account_id} not found in any configured login")

        # get_account_positions now returns a plain dict (already JSON-shaped),
        # not a Pydantic AccountPosition — no .dict() unwrapping needed.
        return get_account_positions(owning_client, args.account_id)

    async def _get_all_holdings(self, arguments: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get holdings for every account across every configured Questrade login."""
        try:
            GetAllHoldingsArguments(**arguments)
        except ValidationError as e:
            logger.error(f"Invalid arguments for get_all_holdings: {e}")
            raise ValueError(f"Invalid arguments: {e}")

        # get_all_account_positions_multi already returns plain dicts shaped
        # {"account_id", "account_name", "account_type", "holdings": [...]} —
        # no .dict() unwrapping needed, unlike the original.
        return get_all_account_positions_multi(get_questrade_clients())

    async def _get_market_data(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Get market performance data for a symbol, routed through QuestradeProvider."""
        # Validate arguments
        try:
            args = GetMarketDataArguments(**arguments)
        except ValidationError as e:
            logger.error(f"Invalid arguments for get_market_data: {e}")
            raise ValueError(f"Invalid arguments: {e}")

        df = await QuestradeProvider().get_market_data(
            [args.symbol], days=args.days, interval=args.interval
        )

        symbol_df = df[df["symbol"] == args.symbol] if not df.empty else df

        metrics = self._calculate_performance_metrics(args.symbol, symbol_df)

        candles_output = [
            {
                "date": row["date"] if isinstance(row["date"], str) else row["date"].strftime("%Y-%m-%d"),
                "open": row["open"],
                "high": row["high"],
                "low": row["low"],
                "close": row["close"],
                "volume": row["volume"],
            }
            for _, row in symbol_df.sort_values("date").iterrows()
        ]

        return {
            "symbol": args.symbol,
            "name": "",
            "metrics": metrics,
            "candles": candles_output,
        }

    @staticmethod
    def _calculate_performance_metrics(symbol: str, symbol_df) -> Dict[str, Any]:
        """Calculate performance metrics from a single symbol's rows of the
        long-format market data DataFrame. Same formulas as the original
        calculate_performance_metrics (Questrade-API/utils/market.py), adapted
        to read DataFrame columns (close, volume, sorted by date descending)
        instead of MarketCandle object attributes.
        """
        if symbol_df.empty:
            return {
                "symbol": symbol,
                "performance_1d": None,
                "performance_1w": None,
                "performance_1m": None,
                "average_volume": None,
            }

        sorted_df = symbol_df.sort_values("date", ascending=False).reset_index(drop=True)
        closes = sorted_df["close"]
        latest_price = closes.iloc[0]
        n = len(sorted_df)

        if n >= 2:
            performance_1d = (latest_price - closes.iloc[1]) / closes.iloc[1] * 100
        else:
            performance_1d = None

        week_index = min(5, n - 1)
        if n > week_index:
            performance_1w = (latest_price - closes.iloc[week_index]) / closes.iloc[week_index] * 100
        else:
            performance_1w = None

        month_index = min(21, n - 1)
        if n > month_index:
            performance_1m = (latest_price - closes.iloc[month_index]) / closes.iloc[month_index] * 100
        else:
            performance_1m = None

        average_volume = sorted_df["volume"].mean()

        return {
            "symbol": symbol,
            "current_price": latest_price,
            "performance_1d": performance_1d,
            "performance_1w": performance_1w,
            "performance_1m": performance_1m,
            "average_volume": average_volume,
        }

    # Order functionality removed as requested
