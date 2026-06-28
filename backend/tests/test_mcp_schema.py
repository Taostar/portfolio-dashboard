"""Schema validation tests for the ported MCP request/response/argument models."""

import pytest
from pydantic import ValidationError

from app.mcp.schema import (
    FUNCTION_DEFINITIONS,
    GetAccountHoldingsArguments,
    GetAccountsArguments,
    GetAllHoldingsArguments,
    GetMarketDataArguments,
    MCPRequest,
    MCPResponse,
)


def test_get_account_holdings_arguments_accepts_account_id():
    args = GetAccountHoldingsArguments(account_id="123")
    assert args.account_id == "123"


def test_get_account_holdings_arguments_requires_account_id():
    with pytest.raises(ValidationError):
        GetAccountHoldingsArguments()


def test_get_accounts_arguments_takes_no_required_fields():
    GetAccountsArguments()


def test_get_all_holdings_arguments_takes_no_required_fields():
    GetAllHoldingsArguments()


def test_get_market_data_arguments_defaults():
    args = GetMarketDataArguments(symbol="AAPL")
    assert args.symbol == "AAPL"
    assert args.days == 30
    assert args.interval == "OneDay"


def test_get_market_data_arguments_requires_symbol():
    with pytest.raises(ValidationError):
        GetMarketDataArguments()


def test_function_definitions_has_exactly_four_entries():
    assert len(FUNCTION_DEFINITIONS) == 4


def test_function_definitions_names():
    names = {fn["name"] for fn in FUNCTION_DEFINITIONS}
    assert names == {
        "get_accounts",
        "get_account_holdings",
        "get_all_holdings",
        "get_market_data",
    }


def test_mcp_request_defaults():
    request = MCPRequest(function="get_accounts")
    assert request.type == "function"
    assert request.arguments == {}
    assert request.conversation_id is None


def test_mcp_response_requires_function_and_result():
    response = MCPResponse(function="get_accounts", result=[])
    assert response.status == "success"
    assert response.error is None
