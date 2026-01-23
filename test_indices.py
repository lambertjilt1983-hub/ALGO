import sys
sys.path.insert(0, 'F:\\ALGO\\backend')

from app.routes.auto_trading_simple import get_live_index_price
from app.core.database import SessionLocal
import asyncio

async def test():
    db = SessionLocal()
    try:
        nifty = await get_live_index_price('NIFTY', db)
        banknifty = await get_live_index_price('BANKNIFTY', db)
        print(f'NIFTY: {nifty}')
        print(f'BANKNIFTY: {banknifty}')
    except Exception as e:
        print(f'Error: {e}')
        import traceback
        traceback.print_exc()
    finally:
        db.close()

asyncio.run(test())
