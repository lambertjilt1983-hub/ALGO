import React, { useState, useEffect } from 'react';
import config from '../config/api';

const REFRESH_INTERVAL_MS = 5000; // 5 second auto-refresh cadence

const MarketIntelligencePage = () => {
  const [sentiment, setSentiment] = useState(null);
  const [trends, setTrends] = useState(null);
  const [news, setNews] = useState([]);
  const [sectors, setSectors] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [autoRefresh, setAutoRefresh] = useState(true);

  const fetchMarketData = async () => {
    const token = localStorage.getItem('access_token');
    if (!token) {
      setError('Please login to view market intelligence');
      setLoading(false);
      return;
    }

    try {
      // Fetch all market data in parallel
      const [sentimentRes, trendsRes, newsRes, sectorsRes] = await Promise.all([
        config.authFetch(config.endpoints.market.sentiment),
        config.authFetch(config.endpoints.market.trends),
        config.authFetch(config.getUrl(config.endpoints.market.news, { limit: 15 })),
        config.authFetch(config.endpoints.market.sectors)
      ]);

      const sentimentData = await sentimentRes.json();
      const trendsData = await trendsRes.json();
      const newsData = await newsRes.json();
      const sectorsData = await sectorsRes.json();

      if (sentimentData.success) setSentiment(sentimentData.sentiment);
      if (trendsData.success) setTrends(trendsData.trends);
      if (newsData.success) setNews(newsData.news);
      if (sectorsData.success) setSectors(sectorsData.sectors);

      setLoading(false);
      setError(null);
    } catch (err) {
      console.error('Error fetching market data:', err);
      setError('Failed to fetch market data');
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchMarketData();

    // Auto-refresh every second if enabled
    let interval;
    if (autoRefresh) {
      interval = setInterval(() => {
        fetchMarketData();
      }, REFRESH_INTERVAL_MS);
    }

    return () => {
      if (interval) clearInterval(interval);
    };
  }, [autoRefresh]);

  const getSentimentColor = (sentiment) => {
    if (sentiment === 'Bullish' || sentiment === 'Strongly Bullish') return 'text-green-600';
    if (sentiment === 'Bearish') return 'text-red-600';
    return 'text-yellow-600';
  };

  const getSentimentBgColor = (sentiment) => {
    if (sentiment === 'positive') return 'bg-green-100 text-green-800';
    if (sentiment === 'negative') return 'bg-red-100 text-red-800';
    return 'bg-gray-100 text-gray-800';
  };

  const getTrendColor = (change) => {
    return change >= 0 ? 'text-green-600' : 'text-red-600';
  };

  const formatTime = (timestamp) => {
    const date = new Date(timestamp);
    const now = new Date();
    const diff = Math.floor((now - date) / 1000 / 60); // minutes

    if (diff < 1) return 'Just now';
    if (diff < 60) return `${diff}m ago`;
    if (diff < 1440) return `${Math.floor(diff / 60)}h ago`;
    return date.toLocaleDateString();
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">Loading market intelligence...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="bg-red-50 border border-red-200 rounded-lg p-6 max-w-md">
          <p className="text-red-800">{error}</p>
          <button
            onClick={fetchMarketData}
            className="mt-4 bg-red-600 text-white px-4 py-2 rounded hover:bg-red-700"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="flex justify-between items-center mb-6">
          <div>
            <h1 className="text-3xl font-bold text-gray-800">Market Intelligence</h1>
            <p className="text-gray-600 mt-1">Real-time news, sentiment, and trend analysis</p>
          </div>
          <div className="flex items-center space-x-4">
            <label className="flex items-center space-x-2 text-sm text-gray-700">
              <input
                type="checkbox"
                checked={autoRefresh}
                onChange={(e) => setAutoRefresh(e.target.checked)}
                className="rounded"
              />
              <span>Auto-refresh (1s)</span>
            </label>
            <button
              onClick={fetchMarketData}
              className="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700 flex items-center space-x-2"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
              <span>Refresh</span>
            </button>
          </div>
        </div>

        {/* Market Sentiment Overview */}
        {sentiment && (
          <div className="bg-white rounded-lg shadow-md p-6 mb-6">
            <h2 className="text-xl font-bold text-gray-800 mb-4 flex items-center">
              <svg className="w-6 h-6 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
              </svg>
              Market Sentiment
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <div className="text-center">
                <p className="text-gray-600 text-sm mb-1">Overall Sentiment</p>
                <p className={`text-2xl font-bold ${getSentimentColor(sentiment.overall_sentiment)}`}>
                  {sentiment.overall_sentiment}
                </p>
                <p className="text-gray-500 text-sm mt-1">Score: {sentiment.sentiment_score}</p>
              </div>
              <div className="text-center">
                <p className="text-gray-600 text-sm mb-1">Positive News</p>
                <p className="text-2xl font-bold text-green-600">{sentiment.positive_news_count}</p>
                <p className="text-gray-500 text-sm mt-1">{sentiment.positive_percentage}%</p>
              </div>
              <div className="text-center">
                <p className="text-gray-600 text-sm mb-1">Negative News</p>
                <p className="text-2xl font-bold text-red-600">{sentiment.negative_news_count}</p>
                <p className="text-gray-500 text-sm mt-1">{((sentiment.negative_news_count / sentiment.total_news) * 100).toFixed(1)}%</p>
              </div>
              <div className="text-center">
                <p className="text-gray-600 text-sm mb-1">Neutral News</p>
                <p className="text-2xl font-bold text-gray-600">{sentiment.neutral_news_count}</p>
                <p className="text-gray-500 text-sm mt-1">{((sentiment.neutral_news_count / sentiment.total_news) * 100).toFixed(1)}%</p>
              </div>
            </div>
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
          {/* Market Trends */}
          {trends && trends.indices && (
            <div className="bg-white rounded-lg shadow-md p-6">
              <h2 className="text-xl font-bold text-gray-800 mb-4 flex items-center">
                <svg className="w-6 h-6 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
                </svg>
                Market Trends
              </h2>
              <div className="mb-3">
                <span className={`inline-block px-3 py-1 rounded-full text-sm font-semibold ${getSentimentColor(trends.market_status)} bg-opacity-10`}>
                  {trends.market_status}
                </span>
              </div>
              <div className="space-y-3">
                {Object.entries(trends.indices).map(([name, data]) => (
                  <div key={name} className="border-b border-gray-100 pb-3 last:border-0">
                    <div className="flex justify-between items-start">
                      <div>
                        <p className="font-semibold text-gray-800">{name}</p>
                        <p className="text-sm text-gray-600">
                          {data.trend} • {data.strength} • RSI: {data.rsi}
                        </p>
                      </div>
                      <div className="text-right">
                        <p className="font-bold text-gray-800">{data.current.toFixed(2)}</p>
                        <p className={`text-sm font-semibold ${getTrendColor(data.change)}`}>
                          {data.change > 0 ? '+' : ''}{data.change.toFixed(2)} ({data.change_percent > 0 ? '+' : ''}{data.change_percent}%)
                        </p>
                      </div>
                    </div>
                    <div className="mt-2 grid grid-cols-2 gap-2 text-xs text-gray-600">
                      <div>Support: {data.support}</div>
                      <div>Resistance: {data.resistance}</div>
                      <div>Volume: {data.volume}</div>
                      <div>MACD: {data.macd}</div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Sector Rotation */}
          {sectors && sectors.length > 0 && (
            <div className="bg-white rounded-lg shadow-md p-6">
              <h2 className="text-xl font-bold text-gray-800 mb-4 flex items-center">
                <svg className="w-6 h-6 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 12l3-3 3 3 4-4M8 21l4-4 4 4M3 4h18M4 4h16v12a1 1 0 01-1 1H5a1 1 0 01-1-1V4z" />
                </svg>
                Sector Performance
              </h2>
              <div className="space-y-2">
                {sectors.map((sector, idx) => {
                  const perfValue = parseFloat(sector.performance.replace('%', ''));
                  return (
                    <div key={idx} className="flex items-center justify-between p-2 hover:bg-gray-50 rounded">
                      <div className="flex items-center space-x-3">
                        <span className="text-sm font-semibold text-gray-700 w-20">{sector.name}</span>
                        <span className={`text-xs px-2 py-1 rounded ${
                          sector.trend === 'Outperforming' ? 'bg-green-100 text-green-800' :
                          sector.trend === 'Underperforming' ? 'bg-red-100 text-red-800' :
                          'bg-gray-100 text-gray-800'
                        }`}>
                          {sector.trend}
                        </span>
                      </div>
                      <div className="flex items-center space-x-3">
                        <span className="text-xs text-gray-600">{sector.strength}</span>
                        <span className={`text-sm font-bold ${getTrendColor(perfValue)}`}>
                          {sector.performance}
                        </span>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>

        {/* Latest News */}
        {news && news.length > 0 && (
          <div className="bg-white rounded-lg shadow-md p-6">
            <h2 className="text-xl font-bold text-gray-800 mb-4 flex items-center">
              <svg className="w-6 h-6 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 20H5a2 2 0 01-2-2V6a2 2 0 012-2h10a2 2 0 012 2v1m2 13a2 2 0 01-2-2V7m2 13a2 2 0 002-2V9a2 2 0 00-2-2h-2m-4-3H9M7 16h6M7 8h6v4H7V8z" />
              </svg>
              Latest Market News
            </h2>
            <div className="space-y-3">
              {news.map((item, idx) => (
                <div key={idx} className="border-b border-gray-100 pb-3 last:border-0">
                  <div className="flex justify-between items-start">
                    <div className="flex-1">
                      <p className="font-medium text-gray-800 mb-1">{item.title}</p>
                      <div className="flex items-center space-x-3 text-sm text-gray-600">
                        <span>{item.source}</span>
                        <span>•</span>
                        <span>{formatTime(item.timestamp)}</span>
                        <span>•</span>
                        <span className="capitalize">{item.category}</span>
                      </div>
                    </div>
                    <div className="ml-4">
                      <span className={`text-xs px-2 py-1 rounded ${getSentimentBgColor(item.sentiment.sentiment)}`}>
                        {item.sentiment.sentiment.toUpperCase()}
                      </span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default MarketIntelligencePage;

