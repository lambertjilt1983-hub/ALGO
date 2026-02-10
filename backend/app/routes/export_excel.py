import pandas as pd
from fastapi import APIRouter, Response
from app.engine.option_signal_generator import generate_signals_advanced
import io

router = APIRouter(prefix="/export", tags=["Export"])

@router.get("/option-signals/excel")
async def export_option_signals_to_excel(
    min_quality: int = 85,
    include_nifty50: bool = True,
    mode: str = "balanced",
    symbols: str | None = None,
):
    """Export all option signals to an Excel file."""
    symbol_list = [s.strip().upper() for s in symbols.split(",")] if symbols else None
    signals = await generate_signals_advanced(mode=mode, symbols=symbol_list, include_nifty50=include_nifty50)
    filtered = [s for s in signals if s.get("quality_score", 0) >= min_quality]
    if not filtered:
        return Response(content="No signals to export", media_type="text/plain", status_code=404)
    df = pd.DataFrame(filtered)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name="Signals")
    output.seek(0)
    headers = {
        'Content-Disposition': 'attachment; filename="option_signals.xlsx"'
    }
    return Response(content=output.read(), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers=headers)
