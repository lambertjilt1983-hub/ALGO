"""
News and Market Trend Analysis Module
Fetches real-time news, analyzes sentiment, and detects market trends
"""

import requests
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from itertools import chain

class NewsAnalyzer:
    """Fetch and analyze market news with sentiment analysis"""
    
    def __init__(self):
        self.news_sources = {
            'economic_times': 'https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms',
            'moneycontrol': 'https://www.moneycontrol.com/rss/marketreports.xml',
            'business_standard': 'https://www.business-standard.com/rss/markets-106.rss'
        }
        self.request_timeout = 6
        
        # Sentiment keywords
        self.positive_keywords = [
            'rally', 'surge', 'bullish', 'gain', 'profit', 'growth', 'strong', 
            'rise', 'high', 'positive', 'upgrade', 'breakthrough', 'success',
            'record', 'boom', 'optimistic', 'outperform', 'buy'
        ]
        
        self.negative_keywords = [
            'fall', 'crash', 'bearish', 'loss', 'decline', 'weak', 'drop',
            'low', 'negative', 'downgrade', 'concern', 'risk', 'fear',
            'recession', 'crisis', 'sell', 'underperform', 'warning'
        ]
    
    def fetch_latest_news(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Fetch latest market news from live RSS feeds with sentiment"""
        all_news: List[Dict[str, Any]] = []

        # Try live feeds first; fall back to canned headlines if unavailable
        for source_key, url in self.news_sources.items():
            feed_items = self._fetch_rss_feed(url, source_key.replace('_', ' ').title(), limit=limit)
            for item in feed_items:
                sentiment = self.analyze_sentiment(item['title'])
                item['sentiment'] = sentiment
                item['sentiment_score'] = sentiment['score']
                all_news.append(item)

        sorted_news = sorted(all_news, key=lambda x: x['timestamp'], reverse=True)
        return sorted_news[:limit]

    def _fetch_rss_feed(self, url: str, source_name: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Fetch and parse an RSS feed into a normalized list"""
        items: List[Dict[str, Any]] = []

        try:
            response = requests.get(url, timeout=self.request_timeout)
            response.raise_for_status()
            root = ET.fromstring(response.content)

            for item in root.findall('.//item')[:limit]:
                title = (item.findtext('title') or '').strip()
                if not title:
                    continue

                raw_category = item.findtext('category') or 'market'
                raw_date = (
                    item.findtext('pubDate')
                    or item.findtext('{http://purl.org/dc/elements/1.1/}date')
                )

                items.append({
                    'title': title,
                    'source': source_name,
                    'timestamp': self._parse_pub_date(raw_date),
                    'category': raw_category.lower()
                })
        except Exception as exc:
            # Keep log lightweight; fall back handled by caller
            print(f"[MarketIntelligence] RSS fetch failed for {source_name}: {exc}")

        return items

    def _parse_pub_date(self, value: Optional[str]) -> datetime:
        """Parse RSS pubDate; fall back to now on failure"""
        if not value:
            return datetime.now()

        try:
            parsed = parsedate_to_datetime(value)
            return parsed if isinstance(parsed, datetime) else datetime.now()
        except Exception:
            return datetime.now()
    
    def analyze_sentiment(self, text: str) -> Dict[str, Any]:
        """Analyze sentiment of news headline"""
        text_lower = text.lower()
        
        positive_count = sum(1 for keyword in self.positive_keywords if keyword in text_lower)
        negative_count = sum(1 for keyword in self.negative_keywords if keyword in text_lower)
        
        total = positive_count + negative_count
        
        if total == 0:
            sentiment = 'neutral'
            score = 0.5
        else:
            score = positive_count / total
            if score > 0.6:
                sentiment = 'positive'
            elif score < 0.4:
                sentiment = 'negative'
            else:
                sentiment = 'neutral'
        
        return {
            'sentiment': sentiment,
            'score': round(score, 2),
            'positive_signals': positive_count,
            'negative_signals': negative_count
        }
    
    def get_market_sentiment_summary(self) -> Dict[str, Any]:
        """Get overall market sentiment from recent news"""
        news = self.fetch_latest_news(limit=20)
        
        total_news = len(news)
        positive_news = sum(1 for n in news if n['sentiment']['sentiment'] == 'positive')
        negative_news = sum(1 for n in news if n['sentiment']['sentiment'] == 'negative')
        neutral_news = total_news - positive_news - negative_news
        
        if total_news == 0:
            return {
                'overall_sentiment': 'Unknown',
                'sentiment_score': 0,
                'positive_news_count': 0,
                'negative_news_count': 0,
                'neutral_news_count': 0,
                'total_news': 0,
                'positive_percentage': 0,
                'last_updated': datetime.now().isoformat()
            }

        avg_score = sum(n['sentiment_score'] for n in news) / total_news if total_news > 0 else 0.5
        
        if avg_score > 0.6:
            overall_sentiment = 'Bullish'
        elif avg_score < 0.4:
            overall_sentiment = 'Bearish'
        else:
            overall_sentiment = 'Neutral'
        
        return {
            'overall_sentiment': overall_sentiment,
            'sentiment_score': round(avg_score, 2),
            'positive_news_count': positive_news,
            'negative_news_count': negative_news,
            'neutral_news_count': neutral_news,
            'total_news': total_news,
            'positive_percentage': round((positive_news / total_news) * 100, 1) if total_news > 0 else 0,
            'last_updated': datetime.now().isoformat()
        }


class MarketTrendAnalyzer:
    """Analyze market trends using technical indicators"""
    
    def __init__(self):
        self.indices = ['NIFTY', 'BANKNIFTY', 'FINNIFTY', 'SENSEX']
        # Primary Yahoo Finance symbols for key indices
        self.quote_symbols = {
            'NIFTY': '^NSEI',
            'BANKNIFTY': '^NSEBANK',
            'FINNIFTY': '^CNXFIN',  # Yahoo uses CNXFIN for FinNifty
            'SENSEX': '^BSESN'
        }
        # Extra symbol aliases to improve hit rate across regions
        self.quote_symbol_aliases = {
            'NIFTY': {'^NSEI', '^NIFTY', '^IXICN'},
            'BANKNIFTY': {'^NSEBANK', '^BANKNIFTY'},
            'FINNIFTY': {'^CNXFIN', '^NIFTYFIN'},
            'SENSEX': {'^BSESN', '^SENSEX'}
        }
        self.request_timeout = 6
    
    async def get_market_trends(self) -> Dict[str, Any]:
        """Get current market trends for major indices"""
        market_data = self._fetch_live_quotes()

        return {
            'indices': market_data,
            'market_status': self._determine_market_status(market_data),
            'last_updated': datetime.now().isoformat()
        }
    
    def _determine_market_status(self, market_data: Dict) -> str:
        """Determine overall market status"""
        uptrend_count = sum(1 for data in market_data.values() if data['trend'] == 'Uptrend')
        total_indices = len(market_data)
        
        if total_indices == 0:
            return 'Unknown'

        if uptrend_count / total_indices >= 0.75:
            return 'Strongly Bullish'
        elif uptrend_count / total_indices >= 0.5:
            return 'Moderately Bullish'
        elif uptrend_count / total_indices >= 0.25:
            return 'Mixed'
        else:
            return 'Bearish'

    def _fetch_live_quotes(self) -> Dict[str, Dict[str, Any]]:
        """Fetch live index quotes from Yahoo Finance"""
        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json'
        })

        market_data: Dict[str, Dict[str, Any]] = {}

        # Batch fetch first
        symbols = ','.join(self.quote_symbols.values())
        url = 'https://query1.finance.yahoo.com/v7/finance/quote'

        try:
            response = session.get(url, params={'symbols': symbols, 'lang': 'en-IN', 'region': 'IN'}, timeout=self.request_timeout)
            response.raise_for_status()
            results = response.json().get('quoteResponse', {}).get('result', [])
        except Exception as exc:
            print(f"[MarketIntelligence] Live quote fetch failed (batch): {exc}")
            results = []

        for quote in results:
            parsed = self._quote_to_market_row(quote)
            if parsed:
                market_data[parsed['index']] = parsed['row']

        # Per-symbol fallback for anything missing
        missing_indices = [idx for idx in self.indices if idx not in market_data]
        if missing_indices:
            for idx in missing_indices:
                for symbol in self._symbols_for_index(idx):
                    chart_row = self._fetch_chart_quote(session, symbol, idx)
                    if chart_row:
                        market_data[idx] = chart_row
                        break

        return market_data

    def _map_symbol_to_index(self, symbol: Optional[str]) -> Optional[str]:
        if not symbol:
            return None

        upper_symbol = symbol.upper()

        # Exact primary mapping first
        for index_name, mapped_symbol in self.quote_symbols.items():
            if upper_symbol == mapped_symbol.upper():
                return index_name

        # Fallback aliases
        for index_name, aliases in self.quote_symbol_aliases.items():
            if upper_symbol in aliases:
                return index_name

        return None

    def _symbols_for_index(self, index_name: str) -> List[str]:
        primary = self.quote_symbols.get(index_name)
        aliases = self.quote_symbol_aliases.get(index_name, set())
        symbols = [s for s in chain([primary] if primary else [], aliases) if s]
        return list(dict.fromkeys(symbols))  # dedupe while preserving order

    def _trend_direction(self, change_percent: float) -> str:
        if change_percent >= 0.1:
            return 'Uptrend'
        if change_percent <= -0.1:
            return 'Downtrend'
        return 'Flat'

    def _trend_strength(self, abs_change_percent: float) -> str:
        if abs_change_percent >= 1.0:
            return 'Strong'
        if abs_change_percent >= 0.5:
            return 'Moderate'
        return 'Weak'

    def _volume_bucket(self, volume: Optional[float]) -> str:
        if volume is None:
            return 'Average'
        if volume >= 5_000_000:
            return 'High'
        if volume <= 1_000_000:
            return 'Low'
        return 'Average'

    def _approximate_rsi(self, change_percent: float) -> float:
        # Simple heuristic to provide a live-feeling RSI when full history is unavailable
        estimated = 50 + (change_percent * 2)
        return max(0, min(100, round(estimated, 2)))

    def _quote_to_market_row(self, quote: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Convert Yahoo quote payload to our structure"""
        symbol = quote.get('symbol')
        index_name = self._map_symbol_to_index(symbol)
        price = quote.get('regularMarketPrice')

        if not index_name or price is None:
            return None

        change = quote.get('regularMarketChange', 0.0) or 0.0
        change_percent = quote.get('regularMarketChangePercent', 0.0) or 0.0

        trend = self._trend_direction(change_percent)
        strength = self._trend_strength(abs(change_percent))

        row = {
            'current': round(price, 2),
            'change': round(change, 2),
            'change_percent': round(change_percent, 2),
            'trend': trend,
            'strength': strength,
            'support': round(price * 0.985, 2),
            'resistance': round(price * 1.015, 2),
            'volume': self._volume_bucket(quote.get('regularMarketVolume')),
            'rsi': self._approximate_rsi(change_percent),
            'macd': 'Bullish' if change_percent > 0 else 'Bearish' if change_percent < 0 else 'Flat'
        }

        return {'index': index_name, 'row': row}

    def _fetch_chart_quote(self, session: requests.Session, symbol: str, index_name: str) -> Optional[Dict[str, Any]]:
        """Fallback: fetch chart endpoint for latest price when batch quote is empty"""
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"

        try:
            response = session.get(url, params={'range': '1d', 'interval': '1m'}, timeout=self.request_timeout)
            response.raise_for_status()
            result = response.json().get('chart', {}).get('result', [])
            if not result:
                return None

            meta = result[0].get('meta', {})
            price = meta.get('regularMarketPrice')
            prev_close = meta.get('previousClose')

            if price is None or prev_close is None:
                return None

            change = price - prev_close
            change_percent = (change / prev_close) * 100 if prev_close else 0.0

            trend = self._trend_direction(change_percent)
            strength = self._trend_strength(abs(change_percent))

            return {
                'current': round(price, 2),
                'change': round(change, 2),
                'change_percent': round(change_percent, 2),
                'trend': trend,
                'strength': strength,
                'support': round(price * 0.985, 2),
                'resistance': round(price * 1.015, 2),
                'volume': self._volume_bucket(meta.get('regularMarketVolume')),
                'rsi': self._approximate_rsi(change_percent),
                'macd': 'Bullish' if change_percent > 0 else 'Bearish' if change_percent < 0 else 'Flat'
            }
        except Exception as exc:
            print(f"[MarketIntelligence] Chart fetch failed for {symbol}: {exc}")
            return None
    
    def get_sector_rotation(self) -> List[Dict[str, Any]]:
        """Get sector rotation analysis (live data required)"""
        # No mock/placeholder data; return empty until a live source is integrated.
        return []


# Initialize analyzers
news_analyzer = NewsAnalyzer()
trend_analyzer = MarketTrendAnalyzer()
