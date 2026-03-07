from typing import Any, Dict


def normalize_active_trade_metrics(trade: Dict[str, Any]) -> Dict[str, Any]:
    """Return a copy of active trade row with normalized live P&L fields."""
    normalized = dict(trade)
    entry_price = float(normalized.get("entry_price") or normalized.get("price") or 0.0)
    current_price = float(normalized.get("current_price") or entry_price)
    side = str(normalized.get("side") or normalized.get("action") or "BUY").upper()
    qty = float(normalized.get("quantity") or 0)

    pnl = (current_price - entry_price) * qty if side == "BUY" else (entry_price - current_price) * qty
    invested = entry_price * qty
    pnl_pct = (pnl / invested * 100.0) if invested > 0 else 0.0

    normalized["entry_price"] = entry_price
    normalized["current_price"] = current_price
    normalized["side"] = side
    normalized["pnl"] = round(pnl, 2)
    normalized["unrealized_pnl"] = round(pnl, 2)
    normalized["profit_loss"] = round(pnl, 2)
    normalized["pnl_percentage"] = round(pnl_pct, 2)
    normalized["pnl_percent"] = round(pnl_pct, 2)
    normalized["profit_percentage"] = round(pnl_pct, 2)
    return normalized
