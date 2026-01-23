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
