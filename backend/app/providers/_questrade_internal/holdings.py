"""Holdings retrieval — ported from Questrade-API/utils/holdings.py and
Questrade-API/utils/cli/holdings_utils.py (those two files were tightly
coupled in the original; kept together here as private helpers used only by
`QuestradeProvider`).

Holdings are represented as plain dicts (no Pydantic `SecurityHolding` model,
unlike the original) so the `security_type` field (see `get_account_positions`)
can be stashed without touching a separate schema module — Task 3's option
classifier reads it directly off the holdings dicts/DataFrame rows.
"""

import logging
import os
import random
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional, Union

import numpy as np
import pandas as pd
from qtrade import Questrade

logger = logging.getLogger(__name__)


def get_account_list(client: Questrade) -> List[Dict[str, Any]]:
    """Get the list of accounts for the authenticated user.

    qtrade doesn't expose account "type"/"clientAccountType" directly, so
    these are left as placeholder strings — a pre-existing limitation in the
    original code, not something this port attempts to fix.
    """
    logger.info("Retrieving account list")
    account_ids = client.get_account_id()
    accounts = []
    for account_id in account_ids:
        accounts.append(
            {
                "number": account_id,
                "type": "Unknown",  # qtrade doesn't provide this directly
                "clientAccountType": "Unknown",  # qtrade doesn't provide this directly
            }
        )
    return accounts


def get_account_positions(client: Questrade, account_id: str) -> Dict[str, Any]:
    """Get all positions (holdings) for a specific account.

    Returns a dict shaped like the old `AccountPosition` model:
    {"account_id", "account_name", "account_type", "holdings": [...]}
    where each holding dict carries `security_type` (from `ticker_information`'s
    `securityType` field) in addition to the original fields — stashed here so
    a later task's option classifier doesn't need a second API call.
    """
    logger.info(f"Retrieving positions for account {account_id}")

    accounts = get_account_list(client)
    account_info = next((acc for acc in accounts if acc.get("number") == account_id), None)

    if not account_info:
        raise ValueError(f"Account with ID {account_id} not found")

    try:
        positions = client.get_account_positions(account_id)
        logger.info(f"Retrieved {len(positions)} positions for account {account_id}")
    except Exception as e:
        logger.error(f"Error getting positions for account {account_id}: {e}")
        raise ValueError(f"Failed to get positions for account {account_id}: {e}")

    holdings = []
    for position in positions:
        symbol = position.get("symbol")
        if not symbol:
            logger.warning(f"No symbol found for position in account {account_id}")
            continue

        try:
            ticker_info = client.ticker_information([symbol])
            symbol_info = ticker_info[0] if ticker_info and len(ticker_info) > 0 else {}
        except Exception as e:
            logger.warning(f"Error getting ticker information for {symbol}: {e}")
            symbol_info = {}

        try:
            quotes = client.get_quote([symbol])
            quote = quotes[0] if isinstance(quotes, list) and quotes else {}
        except Exception as e:
            logger.warning(f"Error getting quote for {symbol}: {e}")
            quote = {}

        try:
            current_price = position.get("currentPrice") or quote.get("lastTradePrice", 0.0)
            holding = {
                "symbol": symbol,
                "name": symbol_info.get("description", ""),
                # securityType is captured (not just description) so Task 3's
                # option classifier can use it without a second API call.
                "security_type": symbol_info.get("securityType"),
                "currency": position.get("currency", "CAD")
                if symbol.endswith(".TO")
                else position.get("currency", "USD"),
                "current_price": current_price,
                "current_market_value": position.get("currentMarketValue", 0.0),
                "quantity": position.get("openQuantity", 0),
                "open_quantity": position.get("openQuantity", 0),
                "average_entry_price": position.get("averageEntryPrice", 0.0),
            }
            holdings.append(holding)
        except Exception as e:
            logger.error(f"Error creating holding for {symbol}: {e}")

    return {
        "account_id": account_id,
        "account_name": account_info.get("clientAccountType", ""),
        "account_type": account_info.get("type", ""),
        "holdings": holdings,
    }


def get_all_account_positions(client: Questrade) -> List[Dict[str, Any]]:
    """Get positions for all accounts the user has access to."""
    logger.info("Retrieving positions for all accounts")

    try:
        accounts = get_account_list(client)
        logger.info(f"Found {len(accounts)} accounts")
    except Exception as e:
        logger.error(f"Error retrieving account list: {e}")
        raise ValueError(f"Failed to retrieve account list: {e}")

    all_positions = []
    for account in accounts:
        account_id = account.get("number")
        if not account_id:
            logger.warning(f"Account missing ID: {account}")
            continue

        try:
            positions = get_account_positions(client, account_id)
            if positions and positions["holdings"]:
                all_positions.append(positions)
                logger.info(f"Added account {account_id} with {len(positions['holdings'])} holdings")
            else:
                logger.info(f"Account {account_id} has no holdings, skipping")
        except Exception as e:
            logger.error(f"Error retrieving positions for account {account_id}: {e}")

    return all_positions


def get_all_account_positions_multi(clients: List[Questrade]) -> List[Dict[str, Any]]:
    """Get positions for every account across multiple Questrade logins."""
    all_positions: List[Dict[str, Any]] = []
    for i, client in enumerate(clients):
        try:
            all_positions.extend(get_all_account_positions(client))
        except Exception as e:
            logger.error(f"Error retrieving positions for client index {i}: {e}")
    return all_positions


def get_holdings_dict(holding: Dict[str, Any]) -> Dict[str, Any]:
    """Identity passthrough — kept for parity with the original API surface.
    Holdings here are already plain dicts (no Pydantic model to unwrap).
    """
    return holding


def _gather_account_positions(client, account_ids):
    """Fetch positions for a list of account IDs on one client. Uses a thread
    pool when there's more than one account, sequential otherwise."""
    if len(account_ids) > 1:
        def get_positions_safe(account_id):
            try:
                return get_account_positions(client, account_id)
            except Exception as e:
                logger.error(f"Error retrieving positions for account {account_id}: {e}")
                return None

        with ThreadPoolExecutor(max_workers=min(len(account_ids), 4)) as executor:
            results = list(executor.map(get_positions_safe, account_ids))
            return [pos for pos in results if pos is not None]

    all_positions = []
    for account_id in account_ids:
        try:
            all_positions.append(get_account_positions(client, account_id))
        except Exception as e:
            logger.error(f"Error retrieving positions for account {account_id}: {e}")
    return all_positions


def _format_holdings_output(
    all_positions, quote_client, account_ids_for_fx, as_dataframe: bool, group_by_symbol: bool
):
    """Shared post-processing for holdings data: builds the DataFrame, applies
    price corrections, adds the fixed extra rows, and optionally groups by
    symbol. `quote_client` is the Questrade client used for market quotes and
    FX lookups.
    """
    if as_dataframe or group_by_symbol:
        all_holdings = [
            {
                **get_holdings_dict(holding),
                "account_id": pos["account_id"],
                "account_name": pos["account_name"],
                "account_type": pos["account_type"],
            }
            for pos in all_positions
            for holding in pos["holdings"]
        ]

        if all_holdings:
            df = pd.DataFrame(all_holdings)
            df = fix_average_entry_price(df)
            df = add_additional_rows(df, quote_client)
        else:
            columns = [
                "symbol",
                "name",
                "security_type",
                "currency",
                "current_price",
                "current_market_value",
                "quantity",
                "open_quantity",
                "average_entry_price",
                "account_id",
                "account_name",
                "account_type",
            ]
            df = pd.DataFrame(columns=columns)

        if group_by_symbol and not df.empty:
            def weighted_avg_price(prices, quantities):
                return np.sum(prices * quantities) / np.sum(quantities) if np.sum(quantities) > 0 else 0

            agg_dict = {
                "currency": "first",
                "current_price": "first",
                "current_market_value": "sum",
                "quantity": "sum",
                "open_quantity": "sum",
                "average_entry_price": lambda x: x.iloc[0],
            }
            if "security_type" in df.columns:
                agg_dict["security_type"] = "first"

            grouped = df.groupby("symbol").agg(agg_dict)

            for symbol in grouped.index:
                symbol_data = df[df["symbol"] == symbol]
                prices = symbol_data["average_entry_price"].values
                quantities = symbol_data["quantity"].values
                grouped.at[symbol, "average_entry_price"] = weighted_avg_price(prices, quantities)

            cad_usd = calc_usd_cad_exchange_rate(quote_client, account_ids_for_fx)
            grouped["current_market_value_CAD"] = grouped["current_market_value"]
            grouped.loc[grouped["currency"] == "USD", "current_market_value_CAD"] *= cad_usd

            grouped = grouped.sort_values("current_market_value", ascending=False)

            total_market_value = grouped["current_market_value_CAD"].sum()
            grouped["percentage"] = (grouped["current_market_value_CAD"] / total_market_value * 100).round(2)

            columns_order = [
                "symbol",
                "currency",
                "current_price",
                "current_market_value",
                "percentage",
                "quantity",
                "open_quantity",
                "average_entry_price",
                "current_market_value_CAD",
                "security_type",
            ]
            available_columns = [col for col in columns_order if col in grouped.columns]
            grouped = grouped[available_columns].reset_index()

            return grouped if as_dataframe else grouped.to_dict(orient="records")

        return df

    result = []
    for pos in all_positions:
        holdings_data = [get_holdings_dict(holding) for holding in pos["holdings"]]
        result.append(
            {
                "account_id": pos["account_id"],
                "account_name": pos["account_name"],
                "account_type": pos["account_type"],
                "holdings": holdings_data,
            }
        )
    return result


def get_all_accounts_holdings_multi(
    clients: List, as_dataframe: bool = False, group_by_symbol: bool = False
) -> Union[List[Dict[str, Any]], pd.DataFrame]:
    """Get holdings for all accounts across multiple Questrade logins.

    Each client's accounts are fetched independently and merged into a single
    result. Quotes and FX (for the additional rows / CAD conversion) use the
    first client.
    """
    if not clients:
        raise ValueError("get_all_accounts_holdings_multi requires at least one client")

    all_positions = []
    quote_client_account_ids: List[int] = []
    for i, client in enumerate(clients):
        try:
            if hasattr(client, "cached_account_ids") and client.cached_account_ids:
                account_ids = client.cached_account_ids
            else:
                account_ids = client.get_account_id()
                if hasattr(client, "cached_account_ids"):
                    client.cached_account_ids = account_ids
            if i == 0:
                quote_client_account_ids = list(account_ids)
            all_positions.extend(_gather_account_positions(client, account_ids))
        except Exception as e:
            logger.error(f"Error gathering holdings for client index {i}: {e}")

    return _format_holdings_output(
        all_positions, clients[0], quote_client_account_ids, as_dataframe, group_by_symbol
    )


def fix_average_entry_price(df: pd.DataFrame) -> pd.DataFrame:
    """Fix average entry prices with correct values from user data.

    PERSONAL DATA PATCH: these are the account owner's actual cost-basis
    prices, hand-verified against brokerage statements — ported verbatim,
    not to be "cleaned up" or pruned.
    """
    correct_average_entry_prices = pd.DataFrame(
        [
            {"symbol": "VOO", "correct_price": 343},
            {"symbol": "AAPL", "correct_price": 130},
            {"symbol": "TCEHY", "correct_price": 66},
            {"symbol": "MSFT", "correct_price": 230},
            {"symbol": "COST", "correct_price": 331},
            {"symbol": "META", "correct_price": 250},
            {"symbol": "DIS", "correct_price": 132},
            {"symbol": "AMZN", "correct_price": 161},
            {"symbol": "BSRTF", "correct_price": 9},
            {"symbol": "BABA", "correct_price": 227},
            {"symbol": "VWO", "correct_price": 53},
            {"symbol": "AMD", "correct_price": 88},
            {"symbol": "PLTR", "correct_price": 101},
            {"symbol": "CQQQ", "correct_price": 91},
            {"symbol": "ARKG", "correct_price": 111.67},  # First BATS:ARKG entry
            {"symbol": "CHIQ", "correct_price": 43},
            {"symbol": "BEKE", "correct_price": 56},
            # Note: Second BATS:ARKG entry with different price, using the exchange prefix to differentiate
            {"symbol": "ARKK", "correct_price": 151.48},
            {"symbol": "U", "correct_price": 126},
        ]
    )

    if "symbol" in df.columns:
        result_df = df.copy()
        merged = pd.merge(result_df, correct_average_entry_prices, on="symbol", how="left")
        mask = ~merged["correct_price"].isna()
        if mask.any():
            merged.loc[mask, "average_entry_price"] = merged.loc[mask, "correct_price"]
        merged = merged.drop("correct_price", axis=1)
        return merged

    return df


def add_additional_rows(df: pd.DataFrame, client: Questrade) -> pd.DataFrame:
    """Add additional rows for two more stocks in other accounts.

    PERSONAL DATA PATCH: BDX and IFC.TO are held in accounts not reachable via
    the Questrade API; quantities come from QTY_BDX/QTY_IFC env vars and the
    entry prices are the account owner's real cost basis — ported verbatim.
    """
    additional_rows = pd.DataFrame(
        [
            {
                "symbol": "BDX",
                "currency": "USD",
                "current_price": 0.0,
                "current_market_value": 0.0,
                "quantity": int(os.environ.get("QTY_BDX", 0)),
                "open_quantity": int(os.environ.get("QTY_BDX", 0)),
                "average_entry_price": 249.01,
            },
            {
                "symbol": "IFC.TO",
                "currency": "CAD",
                "current_price": 0.0,
                "current_market_value": 0.0,
                "quantity": int(os.environ.get("QTY_IFC", 0)),
                "open_quantity": int(os.environ.get("QTY_IFC", 0)),
                "average_entry_price": 216.32,
            },
        ]
    )

    numeric_cols = ["current_price", "current_market_value", "average_entry_price"]
    for col in numeric_cols:
        if col in additional_rows.columns:
            additional_rows[col] = additional_rows[col].astype(float)

    try:
        bdx_quote = client.get_quote("BDX")
        bdx_price = bdx_quote["lastTradePrice"] if "lastTradePrice" in bdx_quote else 0

        ifc_quote = client.get_quote("IFC.TO")
        ifc_price = ifc_quote["lastTradePrice"] if "lastTradePrice" in ifc_quote else 0

        additional_rows.loc[additional_rows["symbol"] == "BDX", "current_price"] = float(bdx_price)
        additional_rows.loc[additional_rows["symbol"] == "IFC.TO", "current_price"] = float(ifc_price)

        additional_rows["current_market_value"] = additional_rows["current_price"] * additional_rows[
            "quantity"
        ].astype(float)
    except Exception as e:
        logger.error(f"Error fetching quotes for additional symbols: {e}")

    return pd.concat([df, additional_rows], ignore_index=True)


def calc_usd_cad_exchange_rate(client: Questrade, account_ids: List[int]) -> float:
    """Calculate the exchange rate between USD and CAD."""
    account_id = int(random.choice(account_ids))
    balances = client.get_account_balances(account_id)["combinedBalances"]
    usd_balance = [item["marketValue"] for item in balances if item["currency"] == "USD"][0]
    cad_balance = [item["marketValue"] for item in balances if item["currency"] == "CAD"][0]
    return cad_balance / usd_balance
