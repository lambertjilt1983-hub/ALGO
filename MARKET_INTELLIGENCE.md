# Market Intelligence Feature

## Overview
Real-time market news, sentiment analysis, and trend detection integrated into AlgoTrade Pro.

## Features

### 1. **News Aggregation**
- Fetches latest market news from multiple sources
- Real-time updates with timestamps
- Categorized by market type (index, sector, policy, etc.)

### 2. **Sentiment Analysis**
- AI-powered sentiment scoring for each news article
- Overall market sentiment (Bullish/Bearish/Neutral)
- Positive/Negative news percentage breakdown
- Confidence scores for each sentiment

### 3. **Market Trends**
- Real-time index data (NIFTY, BANKNIFTY, FINNIFTY, SENSEX)
- Technical indicators (RSI, MACD, Volume)
- Support and Resistance levels
- Trend strength analysis

### 4. **Sector Rotation**
- Performance analysis across 8 major sectors
- Outperforming/Underperforming trends
- Sector strength indicators
- Daily performance percentages

## API Endpoints

### Get Latest News
```
GET /market/news?limit=20
```
Returns latest market news with sentiment analysis.

### Get Market Sentiment
```
GET /market/sentiment
```
Returns overall market sentiment summary.

### Get Market Trends
```
GET /market/trends
```
Returns real-time index trends and technical indicators.

### Get Sector Performance
```
GET /market/sectors
```
Returns sector rotation analysis.

### Get Complete Overview
```
GET /market/overview
```
Returns comprehensive market overview with all data.

## Dashboard Integration

The Market Intelligence section is automatically displayed on the main dashboard with:
- **Market Sentiment Card**: Overall sentiment with score
- **Index Trends Grid**: Real-time data for 4 major indices  
- **Sector Performance**: Top 8 sectors ranked by performance
- **Latest News Feed**: Scrollable news with sentiment badges
- **Auto-refresh**: Optional 60-second auto-refresh

## Technical Implementation

### Backend
- **market_intelligence.py**: Core analysis engine
  - NewsAnalyzer class for news fetching and sentiment
  - MarketTrendAnalyzer for technical analysis
  
- **routes/market_intelligence.py**: FastAPI endpoints
  - JWT authentication required
  - Real-time data aggregation

### Frontend
- Integrated into Dashboard.jsx
- Real-time updates via API calls
- Color-coded sentiment indicators
- Responsive grid layout

## Sentiment Algorithm

The sentiment analyzer uses keyword matching:
- **Positive keywords**: rally, surge, bullish, gain, profit, growth, etc.
- **Negative keywords**: fall, crash, bearish, loss, decline, etc.
- **Scoring**: Positive count / Total keywords
  - > 0.6 = Positive
  - < 0.4 = Negative  
  - 0.4-0.6 = Neutral

## Future Enhancements
- Live RSS feed integration
- Machine learning sentiment models
- Real-time streaming data from exchanges
- Historical sentiment trends
- Custom news alerts
- Integration with trading strategies

## Usage

1. Login to AlgoTrade Pro
2. Navigate to Dashboard
3. Scroll to "Market Intelligence & News" section
4. View real-time sentiment, trends, and news
5. Click "Refresh" button for manual updates
6. Enable "Auto-refresh" for automatic 60s updates

All data is authentication-protected and requires a valid JWT token.
