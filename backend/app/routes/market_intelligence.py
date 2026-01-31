from kiteconnect import KiteConnect
import os
import json
import datetime
import sqlite3
import sys
from fastapi import APIRouter
router = APIRouter(prefix="/market", tags=["market"])

@router.get("/active-symbols")
async def get_active_symbols():
    # Load API key and access token
    API_KEY = os.getenv("ZERODHA_API_KEY", "30i4qnng2thn7mfd")
    # Load access token from DB
    sys.path.insert(0, 'F:/ALGO/backend')
    from app.core.security import encryption_manager
    conn = sqlite3.connect('F:/ALGO/algotrade.db')
    c = conn.cursor()
    c.execute('SELECT access_token FROM broker_credentials WHERE broker_name = ? AND is_active = 1 ORDER BY id DESC LIMIT 1', ('zerodha',))
    row = c.fetchone()
    conn.close()
    if not row:
        return []
    try:
        ACCESS_TOKEN = encryption_manager.decrypt_credentials(row[0])
    except Exception:
        ACCESS_TOKEN = row[0]
    kite = KiteConnect(api_key=API_KEY)
    kite.set_access_token(ACCESS_TOKEN)
    # Load cached instruments
    with open("instruments_cache.json", "r", encoding="utf-8") as f:
        instruments = json.load(f)
    from_date = datetime.datetime.now() - datetime.timedelta(days=5)
    to_date = datetime.datetime.now()
    results = []
    count = 0
    for i in instruments:
        if i.get("exchange") == "NSE":
            symbol = f"NSE:{i['tradingsymbol']}"
            token = i["instrument_token"]
            try:
                ohlcv = kite.historical_data(token, from_date, to_date, "day")
                if ohlcv:
                    results.append({
                        "symbol": symbol,
                        "exchange": "NSE",
                        "tradingsymbol": i['tradingsymbol'],
                        "token": token,
                        "ohlcv_count": len(ohlcv)
                    })
                    count += 1
                    if count >= 10:
                        break
            except Exception:
                continue
    return results
"""
Market Intelligence API Routes
News, sentiment analysis, and market trend endpoints
"""

from fastapi import APIRouter, HTTPException, Header
from typing import Dict, Any, List, Optional
from datetime import datetime

from ..strategies.market_intelligence import news_analyzer, trend_analyzer

router = APIRouter(prefix="/market", tags=["Market Intelligence"])


@router.get("/news")
async def get_latest_news(
    limit: int = 20,
    authorization: Optional[str] = Header(None)
) -> Dict[str, Any]:
    """Get latest market news with sentiment analysis"""
    try:
        news = news_analyzer.fetch_latest_news(limit=limit)
        
        return {
            "success": True,
            "news": news,
            "count": len(news),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch news: {str(e)}")


@router.get("/sentiment")
async def get_market_sentiment(
    authorization: Optional[str] = Header(None)
) -> Dict[str, Any]:
    """Get overall market sentiment from news analysis"""
    try:
        sentiment = news_analyzer.get_market_sentiment_summary()
        
        return {
            "success": True,
            "sentiment": sentiment,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to analyze sentiment: {str(e)}")


@router.get("/trends")
async def get_market_trends(
    authorization: Optional[str] = Header(None)
) -> Dict[str, Any]:
    """Get market trends for major indices"""
    try:
        trends = await trend_analyzer.get_market_trends()
        
        return {
            "success": True,
            "trends": trends,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch trends: {str(e)}")


@router.get("/sectors")
async def get_sector_rotation(
    authorization: Optional[str] = Header(None)
) -> Dict[str, Any]:
    """Get sector rotation analysis"""
    try:
        sectors = trend_analyzer.get_sector_rotation()
        
        return {
            "success": True,
            "sectors": sectors,
            "count": len(sectors),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch sectors: {str(e)}")


@router.get("/overview")
async def get_market_overview(
    authorization: Optional[str] = Header(None)
) -> Dict[str, Any]:
    """Get comprehensive market overview with news, sentiment, and trends"""
    try:
        news = news_analyzer.fetch_latest_news(limit=10)
        sentiment = news_analyzer.get_market_sentiment_summary()
        trends = await trend_analyzer.get_market_trends()
        sectors = trend_analyzer.get_sector_rotation()
        
        return {
            "success": True,
            "overview": {
                "sentiment": sentiment,
                "trends": trends,
                "top_news": news[:5],
                "top_sectors": sectors[:5]
            },
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch market overview: {str(e)}")
