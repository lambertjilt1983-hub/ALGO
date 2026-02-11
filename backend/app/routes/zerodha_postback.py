# FastAPI endpoint to receive Zerodha postback events
from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse
from app.routes.auto_trading_simple import active_trades, history

router = APIRouter(prefix="/zerodha", tags=["Zerodha Postback"])

@router.post("/postback")
async def zerodha_postback(request: Request):
    """
    Zerodha will POST order updates here. Parse and process as needed.
    """
    try:
        data = await request.json()
        # Example Zerodha postback fields: order_id, status, tradingsymbol, filled_quantity, average_price, etc.
        order_id = data.get("order_id")
        status = data.get("status")
        tradingsymbol = data.get("tradingsymbol")
        filled_qty = data.get("filled_quantity")
        avg_price = data.get("average_price")
        # Find and update the active trade
        for trade in active_trades:
            if trade.get("symbol") == tradingsymbol and trade.get("status") == "OPEN":
                trade["status"] = status
                trade["filled_quantity"] = filled_qty
                trade["average_price"] = avg_price
                # If order is complete, move to history
                if status in ("COMPLETE", "FILLED", "CLOSED"):
                    trade["exit_time"] = data.get("order_timestamp")
                    history.append(trade)
                    active_trades.remove(trade)
                break
        logging.info(f"Updated trades on postback: {active_trades}, {history}")
        return JSONResponse({"status": "ok"}, status_code=status.HTTP_200_OK)
    except Exception as e:
        return JSONResponse({"status": "error", "detail": str(e)}, status_code=status.HTTP_400_BAD_REQUEST)
