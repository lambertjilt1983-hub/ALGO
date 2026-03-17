import sys, os
sys.path.insert(0, os.path.dirname(__file__))

# Patch market window to always return True for testing
import app.routes.auto_trading_simple as m
m._within_trade_window = lambda: True

from starlette.testclient import TestClient
from fastapi import FastAPI

app2 = FastAPI()

@app2.exception_handler(Exception)
async def all_exception_handler(request, exc):
    import traceback
    traceback.print_exc()
    from fastapi.responses import JSONResponse
    return JSONResponse(status_code=500, content={"detail": f"Unhandled server error: {type(exc).__name__}: {exc}"})

app2.include_router(m.router)

client = TestClient(app2, raise_server_exceptions=False)

payload = {
    'symbol': 'FINNIFTY26MAR25450CE',
    'price': 591.95,
    'quantity': 40,
    'side': 'BUY',
    'force_demo': True,
    'balance': 0,
    'broker_id': 1,
    'quality_score': 99,
    'confirmation_score': 98,
    'ai_edge_score': 85.0,
    'momentum_score': 82.0,
    'breakout_score': 78.0,
    'stop_loss': 560.0,
    'target': 640.0,
    'market_bias': 'BULLISH',
    'market_regime': 'TRENDING',
    'breakout_confirmed': True,
    'momentum_confirmed': True,
    'breakout_hold_confirmed': True,
    'timing_risk': 'NORMAL',
    'sudden_news_risk': 8.0,
    'liquidity_spike_risk': 8.0,
    'premium_distortion_risk': 5.0,
}

r = client.post('/execute', json=payload)
print('STATUS:', r.status_code)
print('BODY:', r.text[:3000])
