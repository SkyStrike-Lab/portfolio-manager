import json
import logging
from datetime import datetime, timezone
from typing import List, Optional

import requests
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from core.calculations import calculate_holdings
from core.cache import rebuild_dashboard_sync
from core.database import get_connection
from services.fetch_exchange_rates import get_historical_exchange_rate
from services.rebuild_dashboard import load_config

logger = logging.getLogger(__name__)

router = APIRouter()


def get_options_tracker_base_url() -> str:
    """Resolves and cleans the base URL for the Options Tracker service."""
    config = load_config()
    raw = config.get("external_services", {}).get("options_tracker_url", "").strip()
    if not raw:
        return ""
    for sub in ["/api/positions", "/api/deliveries"]:
        if sub in raw:
            raw = raw.split(sub)[0]
    return raw.rstrip("/")


class DeliveryImportItem(BaseModel):
    delivery_id: str
    portfolio_id: Optional[int] = None
    price: Optional[float] = None
    notes: Optional[str] = None


class DeliveryImportRequest(BaseModel):
    items: List[DeliveryImportItem]


@router.get("/api/options/deliveries")
def list_option_deliveries(symbol: Optional[str] = None, since: Optional[str] = None):
    """
    Fetches option deliveries (assignments/exercises) from Options Tracker,
    cross-references against previously imported deliveries, and provides
    effective basis and default portfolio suggestions.
    """
    logger.info("GET /api/options/deliveries (symbol=%s, since=%s)", symbol, since)
    base_url = get_options_tracker_base_url()
    if not base_url:
        return {
            "status": "warning",
            "message": "Options tracker URL is not configured. Please set it in Control Center > Configuration.",
            "options_tracker_url": "",
            "deliveries": [],
            "portfolios": [],
            "default_portfolio_id": None,
            "default_portfolio_name": ""
        }

    api_url = f"{base_url}/api/deliveries"
    params = {}
    if symbol and symbol.strip():
        params["symbol"] = symbol.strip().upper()
    if since and since.strip():
        params["since"] = since.strip()

    try:
        resp = requests.get(api_url, params=params, timeout=10, verify=False)
        resp.raise_for_status()
        raw_deliveries = resp.json()
        if not isinstance(raw_deliveries, list):
            raw_deliveries = []
    except Exception as e:
        logger.error("Failed to query options deliveries from %s: %s", api_url, e)
        raise HTTPException(status_code=502, detail=f"Failed to fetch option deliveries from Options Tracker: {str(e)}")

    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT delivery_id, transaction_id, portfolio_id, settlement_date, imported_at 
            FROM option_deliveries
        """)
        imported_map = {row["delivery_id"]: dict(row) for row in cursor.fetchall()}

        cursor.execute("SELECT id, name, broker, classification FROM portfolios ORDER BY sort_order ASC, id ASC")
        portfolios = [dict(row) for row in cursor.fetchall()]

        # Find default portfolio ("Discord Trades" preferred)
        default_portfolio = next((p for p in portfolios if "discord" in (p["name"] or "").lower()), None)
        if not default_portfolio and portfolios:
            default_portfolio = portfolios[0]

        default_portfolio_id = default_portfolio["id"] if default_portfolio else None
        default_portfolio_name = default_portfolio["name"] if default_portfolio else ""

        enriched = []
        for item in raw_deliveries:
            deliv_id = str(item.get("delivery_id") or "")
            if not deliv_id:
                continue

            is_imported = deliv_id in imported_map
            imported_info = imported_map.get(deliv_id, {})

            strike = float(item.get("strike_price") or 0.0)
            eff_basis = float(item.get("effective_basis") or 0.0)
            # Use effective basis as primary trade price; fall back to strike price if missing
            trade_price = eff_basis if eff_basis > 0 else strike

            shares_count = int(item.get("shares_count") or abs(item.get("shares") or 0))

            enriched.append({
                "delivery_id": deliv_id,
                "position_id": item.get("position_id"),
                "group_id": item.get("group_id"),
                "campaign_id": item.get("campaign_id"),
                "symbol": str(item.get("symbol") or "").strip().upper(),
                "contract_name": item.get("contract_name") or "",
                "delivery_type": str(item.get("delivery_type") or "").upper(),
                "action": str(item.get("action") or "").upper(),
                "shares_count": shares_count,
                "strike_price": strike,
                "effective_basis": eff_basis,
                "trade_price": trade_price,
                "option_premium_per_share": float(item.get("option_premium_per_share") or 0.0),
                "total_premium_usd": float(item.get("total_premium_usd") or 0.0),
                "settlement_date": str(item.get("settlement_date") or "")[:10],
                "cash_flow_pnl_usd": float(item.get("cash_flow_pnl_usd") or 0.0),
                "broker_adjusted_pnl_usd": float(item.get("broker_adjusted_pnl_usd") or 0.0),
                "notes": item.get("notes") or "",
                "is_imported": is_imported,
                "transaction_id": imported_info.get("transaction_id"),
                "imported_at": imported_info.get("imported_at"),
                "target_portfolio_id": imported_info.get("portfolio_id") or default_portfolio_id
            })

        return {
            "status": "success",
            "options_tracker_url": base_url,
            "count": len(enriched),
            "default_portfolio_id": default_portfolio_id,
            "default_portfolio_name": default_portfolio_name,
            "portfolios": portfolios,
            "deliveries": enriched
        }
    finally:
        conn.close()


@router.post("/api/options/deliveries/import")
def import_option_deliveries(req: DeliveryImportRequest):
    """
    Imports selected option deliveries into transactions table at effective basis,
    ensuring strict deduplication by recording delivery_ids in option_deliveries.
    """
    logger.info("POST /api/options/deliveries/import - processing %d items", len(req.items))
    if not req.items:
        return {"status": "success", "imported": 0, "skipped": 0, "transaction_ids": []}

    base_url = get_options_tracker_base_url()
    if not base_url:
        raise HTTPException(status_code=400, detail="Options tracker URL is not configured.")

    conn = get_connection()
    try:
        cursor = conn.cursor()

        # Find default portfolio
        cursor.execute("SELECT id, name FROM portfolios ORDER BY sort_order ASC, id ASC")
        portfolios = [dict(row) for row in cursor.fetchall()]
        default_portfolio = next((p for p in portfolios if "discord" in (p["name"] or "").lower()), None)
        default_portfolio_id = default_portfolio["id"] if default_portfolio else (portfolios[0]["id"] if portfolios else 1)

        imported_tx_ids = []
        skipped_count = 0
        touched_portfolios = set()

        for item in req.items:
            deliv_id = item.delivery_id.strip()
            if not deliv_id:
                continue

            # Deduplication check
            cursor.execute("SELECT delivery_id FROM option_deliveries WHERE delivery_id = ?", (deliv_id,))
            if cursor.fetchone():
                logger.info("Delivery %s is already imported. Skipping duplicate.", deliv_id)
                skipped_count += 1
                continue

            # Fetch authoritative delivery memo
            deliv_url = f"{base_url}/api/deliveries/{deliv_id}"
            try:
                resp = requests.get(deliv_url, timeout=10, verify=False)
                resp.raise_for_status()
                memo = resp.json()
            except Exception as e:
                logger.error("Failed to fetch delivery %s from %s: %s", deliv_id, deliv_url, e)
                raise HTTPException(status_code=502, detail=f"Failed to fetch delivery '{deliv_id}' from Options Tracker: {str(e)}")

            symbol = str(memo.get("symbol") or "").strip().upper()
            if not symbol:
                raise HTTPException(status_code=400, detail=f"Delivery '{deliv_id}' has no ticker symbol.")

            action = str(memo.get("action") or "BUY").strip().upper()
            if action not in ["BUY", "SELL"]:
                action = "BUY"

            shares = int(memo.get("shares_count") or abs(memo.get("shares") or 100))
            if shares <= 0:
                shares = 100

            eff_basis = float(memo.get("effective_basis") or 0.0)
            strike = float(memo.get("strike_price") or 0.0)

            # Trade price: Item price override > effective basis > strike price
            if item.price is not None and item.price > 0:
                trade_price = float(item.price)
            elif eff_basis > 0:
                trade_price = eff_basis
            else:
                trade_price = strike

            target_portfolio_id = item.portfolio_id or default_portfolio_id
            clean_date = (memo.get("settlement_date") or datetime.now(timezone.utc).strftime("%Y-%m-%d"))[:10]

            # Ensure ticker exists
            cursor.execute("SELECT id FROM tickers WHERE symbol = ?", (symbol,))
            ticker_row = cursor.fetchone()
            if not ticker_row:
                logger.info("Ticker '%s' not found — auto-creating.", symbol)
                cursor.execute(
                    "INSERT INTO tickers (symbol, friendly_name, tax_rate, exchange) VALUES (?, ?, ?, ?)",
                    (symbol, symbol, 0.30, "")
                )
                ticker_id = cursor.lastrowid
                cursor.execute(
                    "INSERT OR IGNORE INTO ticker_prices (ticker_id, price, intraday_current, intraday_prev_close, currency, last_updated) VALUES (?, ?, ?, ?, 'USD', datetime('now'))",
                    (ticker_id, trade_price, trade_price, trade_price)
                )
            else:
                ticker_id = ticker_row["id"]

            # Cache exchange rate for settlement date
            get_historical_exchange_rate(clean_date, "USD", conn)

            # Build descriptive note
            contract = memo.get("contract_name") or ""
            deliv_type = memo.get("delivery_type") or "DELIVERY"
            memo_notes = memo.get("notes") or ""
            note_text = f"[Option Delivery: {deliv_id}] {contract} {deliv_type}. Strike: ${strike:.2f}, Eff Basis: ${eff_basis:.2f}"
            if memo_notes:
                note_text += f" | {memo_notes}"
            if item.notes:
                note_text = f"{item.notes} | {note_text}"

            created_at_utc = datetime.now(timezone.utc).isoformat()

            # Insert transaction
            cursor.execute("""
                INSERT INTO transactions (portfolio_id, ticker_id, date, action, price, quantity, currency, commission, notes, created_at)
                VALUES (?, ?, ?, ?, ?, ?, 'USD', 0.0, ?, ?)
            """, (target_portfolio_id, ticker_id, clean_date, action, trade_price, shares, note_text, created_at_utc))
            tx_id = cursor.lastrowid
            imported_tx_ids.append(tx_id)
            touched_portfolios.add(target_portfolio_id)

            # Insert option_deliveries record
            cursor.execute("""
                INSERT INTO option_deliveries (delivery_id, transaction_id, symbol, delivery_type, action, shares, strike_price, effective_basis, settlement_date, portfolio_id, imported_at, raw_memo)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                deliv_id,
                tx_id,
                symbol,
                deliv_type,
                action,
                shares,
                strike,
                eff_basis,
                clean_date,
                target_portfolio_id,
                created_at_utc,
                json.dumps(memo)
            ))

        # Recalculate cost basis & rebuild cache if new trades were imported
        if imported_tx_ids:
            for pid in touched_portfolios:
                calculate_holdings(pid, conn)
            conn.commit()
            rebuild_dashboard_sync(conn)
            logger.info("Imported %d delivery trades across %d portfolio(s). Dashboard rebuilt.", len(imported_tx_ids), len(touched_portfolios))

        return {
            "status": "success",
            "imported": len(imported_tx_ids),
            "skipped": skipped_count,
            "transaction_ids": imported_tx_ids
        }
    except Exception as e:
        conn.rollback()
        logger.error("Error importing option deliveries: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()
