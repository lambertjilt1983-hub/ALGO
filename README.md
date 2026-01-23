# AlgoTrade Pro - Enterprise Algorithmic Trading Platform

A cutting-edge, production-ready algorithmic trading system designed for retail and professional traders. Built with Python FastAPI backend, React frontend, and seamless integration with multiple Indian brokers.

## 🚀 Features

### Broker Integration
- **Zerodha Kite Connect** - Full API support for NSE/BSE trading
- **Upstox** - REST API integration for efficient order execution
- **Angel One SmartAPI** - Advanced trading features
- **Groww** - Simplified broker API integration
- Extensible broker framework for easy addition of new brokers

### Authentication & Security
- OAuth2 token-based authentication
- JWT access/refresh token system
- Encrypted credential storage (AES encryption)
- Secure one-click login and automatic token refresh
- Role-based access control ready

### Trading Features
- **One-Click Trading**: Authenticate → Select Broker → Choose Stock → Enter Quantity → Trade
- Multiple order types: Market, Limit, Stop-Loss
- Buy/Sell order execution
- Real-time order status tracking
- Order confirmation and comprehensive error handling
- Position monitoring and P&L tracking

### Algorithmic Engine
- **Built-in Strategies**:
  - Moving Average Crossover (MA)
  - RSI (Relative Strength Index)
  - Momentum-based trading
- Strategy backtesting with historical data
- Live strategy execution with real-time feeds
- Customizable strategy parameters
- Performance metrics: Sharpe ratio, drawdown, win rate

### Risk Management
- Position size management (% of portfolio)
- Daily loss limits
- Stop-loss and take-profit automation
- Risk per trade configuration
- Drawdown monitoring

### Dashboard & Analytics
- Real-time account balance display
- Position overview with P&L
- Strategy performance metrics
- Order history and execution tracking
- Interactive charts and visualizations
- Trade analytics

## 📋 Tech Stack

### Backend
- **Framework**: FastAPI (Python)
- **Server**: Uvicorn (ASGI)
- **Database**: PostgreSQL with SQLAlchemy ORM
- **Authentication**: JWT, OAuth2
- **HTTP Client**: aiohttp (async)
- **Data Analysis**: Pandas, NumPy, TA-Lib

### Frontend
- **Framework**: React 18
- **Routing**: React Router v6
- **State Management**: Zustand
- **UI Components**: Tailwind CSS
- **Charts**: Recharts
- **HTTP Client**: Axios
- **Notifications**: react-hot-toast
- **Build Tool**: Vite

### DevOps
- Docker support (ready for containerization)
- Environment-based configuration
- Comprehensive logging system

## 🛠️ Installation & Setup

### Prerequisites
- Python 3.9+
- Node.js 16+
- PostgreSQL 12+
- Git

### Backend Setup

1. **Clone repository and navigate to backend**
```bash
cd backend
```

2. **Create virtual environment**
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Configure environment variables**
```bash
cp .env.example .env
# Edit .env with your settings:
# - Database connection string
# - Broker API keys
# - JWT secret key
# - Encryption key
```

5. **Create database tables**
```bash
python -m alembic upgrade head
```

6. **Run backend server**
```bash
python -m app.main
# Or with uvicorn directly:
# uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Backend will be available at: `http://localhost:8000`
API Documentation: `http://localhost:8000/docs`

### Frontend Setup

1. **Navigate to frontend**
```bash
cd frontend
```

2. **Install dependencies**
```bash
npm install
```

3. **Configure API endpoint** (if needed)
```bash
# Edit src/api/client.js or set environment variable:
export REACT_APP_API_URL=http://localhost:8000
```

4. **Run development server**
```bash
npm run dev
```

Frontend will be available at: `http://localhost:3000`

## 🔐 Security Configuration

### Encryption Setup
1. Generate a secure encryption key:
```python
from cryptography.fernet import Fernet
key = Fernet.generate_key()
print(key.decode())  # Use in .env as ENCRYPTION_KEY
```

2. Update `.env` with the generated key

### JWT Configuration
1. Generate a strong secret key:
```python
import secrets
secret = secrets.token_urlsafe(32)
print(secret)  # Use in .env as SECRET_KEY
```

2. Keep SECRET_KEY safe and never commit it to version control

## 📚 API Documentation

### Authentication Endpoints
- `POST /auth/register` - User registration
- `POST /auth/login` - User login
- `POST /auth/refresh` - Refresh access token
- `GET /auth/me` - Get current user profile

### Broker Endpoints
- `POST /brokers/credentials` - Add broker credentials
- `GET /brokers/credentials` - List all broker credentials
- `GET /brokers/credentials/{broker_name}` - Get specific broker
- `DELETE /brokers/credentials/{broker_name}` - Remove broker

### Orders Endpoints
- `POST /orders/` - Place a new order
- `GET /orders/` - List all orders
- `GET /orders/{order_id}` - Get order details
- `DELETE /orders/{order_id}` - Cancel order

### Strategies Endpoints
- `POST /strategies/` - Create strategy
- `GET /strategies/` - List strategies
- `GET /strategies/{strategy_id}` - Get strategy details
- `POST /strategies/{strategy_id}/backtest` - Run backtest
- `PUT /strategies/{strategy_id}` - Update strategy
- `DELETE /strategies/{strategy_id}` - Delete strategy

## 📖 Usage Examples

### 1. Register and Login
```javascript
// Frontend
const response = await authAPI.login({
  username: 'trader',
  password: 'secure_password'
});
localStorage.setItem('access_token', response.data.access_token);
```

### 2. Add Broker Credentials
```javascript
await brokerAPI.addCredentials({
  broker_name: 'zerodha',
  api_key: 'your_api_key',
  api_secret: 'your_api_secret'
});
```

### 3. Place an Order
```javascript
const response = await ordersAPI.placeOrder({
  broker_id: 1,
  symbol: 'INFY',
  side: 'buy',
  order_type: 'market',
  quantity: 1
});
```

### 4. Create and Backtest a Strategy
```javascript
// Create strategy
const strategy = await strategiesAPI.createStrategy({
  name: 'MA Crossover Pro',
  strategy_type: 'ma_crossover',
  parameters: {
    fast_period: 20,
    slow_period: 50,
    stop_loss_percent: 2,
    take_profit_percent: 5
  }
});

// Backtest
const backtest = await strategiesAPI.backtest(strategy.id, {
  start_date: '2023-01-01',
  end_date: '2024-01-01',
  initial_capital: 100000
});
```

## 🔄 Workflow

**Simple Trading Workflow:**
1. User registers/logs in
2. Adds broker credentials securely
3. Selects broker account from list
4. Chooses stock symbol (NSE/BSE)
5. Inputs trade quantity and order type
6. Executes buy/sell order with one click
7. Views order confirmation and status
8. Monitors positions and P&L in real-time

**Strategy Workflow:**
1. Define trading strategy with parameters
2. Backtest against historical data
3. Review performance metrics
4. Adjust parameters if needed
5. Deploy live to selected broker
6. Monitor execution and profits

## 📊 Database Schema

### Core Tables
- **users** - User accounts and authentication
- **broker_credentials** - Encrypted broker API keys
- **refresh_tokens** - JWT refresh token storage
- **orders** - Order execution history
- **positions** - Current open positions
- **strategies** - Strategy definitions
- **backtest_results** - Backtest performance data

## 🧪 Testing

### Backend Tests
```bash
pytest tests/
pytest tests/ -v --cov
```

### Frontend Tests
```bash
npm test
npm test -- --coverage
```

## 🚢 Deployment

### Docker Deployment
```bash
# Build Docker image
docker build -t algotrade-backend .

# Run container
docker run -p 8000:8000 --env-file .env algotrade-backend
```

### Production Checklist
- [ ] Change all default secrets in .env
- [ ] Enable HTTPS/SSL
- [ ] Set up database backups
- [ ] Configure logging and monitoring
- [ ] Set up rate limiting
- [ ] Enable CORS properly for production domain
- [ ] Use environment-specific configurations
- [ ] Set up CI/CD pipeline
- [ ] Configure health checks
- [ ] Set up alerting for trade execution failures

## 📈 Performance Considerations

- Async operations for API calls
- Database connection pooling
- Caching strategy results
- Real-time WebSocket for market data (future)
- Load balancing ready
- Horizontal scaling support

## 🐛 Troubleshooting

### Backend Issues
- **Import Errors**: Ensure all dependencies in requirements.txt are installed
- **Database Connection**: Check DATABASE_URL in .env
- **Authentication Failures**: Verify SECRET_KEY and ALGORITHM settings
- **Broker API Errors**: Validate broker credentials and API endpoints

### Frontend Issues
- **CORS Errors**: Check CORS middleware in FastAPI
- **API 401 Errors**: Clear localStorage and re-login
- **Blank Dashboard**: Check console for API errors
- **State Not Updating**: Verify Zustand store configuration

## 🔮 Future Enhancements

- [ ] WebSocket for real-time market data
- [ ] Machine learning strategy optimization
- [ ] Advanced risk analytics and reporting
- [ ] Multi-account management
- [ ] Strategy marketplace
- [ ] Performance attribution analysis
- [ ] Options trading support
- [ ] Advanced charting with TradingView
- [ ] Mobile app (React Native)
- [ ] Community strategy sharing

## 📄 License

MIT License - See LICENSE file for details

## 🤝 Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Submit a pull request with detailed description

## 📞 Support

For issues and questions:
- Create an issue on GitHub
- Check documentation at `/docs` endpoint
- Review API documentation at `/docs` in browser

## ⚠️ Disclaimer

This is a trading software that executes real trades through broker APIs. Users are responsible for:
- Understanding financial risks
- Testing strategies thoroughly before live trading
- Keeping API credentials secure
- Monitoring system for errors
- Complying with broker terms of service
- Tax implications of trading

Trade with caution. Past performance doesn't guarantee future results.

---

**Built with ❤️ for traders, by traders**

**Start trading algorithmically today! 🚀**
