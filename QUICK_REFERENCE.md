# AlgoTrade Pro - Quick Reference Guide

## Installation Checklist

- [ ] Python 3.9+ installed
- [ ] Node.js 16+ installed
- [ ] PostgreSQL installed and running
- [ ] Git installed

## Step-by-Step Setup

### 1. Backend Setup (3 minutes)
```bash
# Navigate to project root
cd algotrade

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
cd backend
pip install -r requirements.txt

# Copy environment template
cd ..
cp .env.example .env
```

### 2. Configure Environment (.env)
```bash
# Database
DATABASE_URL=postgresql://user:password@localhost:5432/trading_db

# Security Keys (generate strong keys)
SECRET_KEY=your-generated-secret-key
ENCRYPTION_KEY=your-generated-encryption-key

# Broker APIs (add your own credentials)
ZERODHA_API_KEY=your_key
ZERODHA_API_SECRET=your_secret
# ... (add for other brokers as needed)
```

### 3. Setup Database
```bash
# Using Docker (recommended)
docker run --name algotrade-db -e POSTGRES_PASSWORD=password -d postgres:15

# Or use local PostgreSQL
# Ensure database exists and user has access
```

### 4. Start Backend
```bash
cd backend
python -m app.main

# API will be available at http://localhost:8000
# API docs at http://localhost:8000/docs
```

### 5. Start Frontend (in another terminal)
```bash
cd frontend
npm install
npm run dev

# Frontend will be available at http://localhost:3000
```

## First Trade Workflow

### 1. Register Account
```bash
curl -X POST "http://localhost:8000/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "trader1",
    "email": "trader@example.com",
    "password": "SecurePassword123"
  }'
```

### 2. Login
```bash
curl -X POST "http://localhost:8000/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "trader1",
    "password": "SecurePassword123"
  }'

# Save the access_token from response
```

### 3. Add Broker Credentials
```bash
curl -X POST "http://localhost:8000/brokers/credentials" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "broker_name": "zerodha",
    "api_key": "YOUR_ZERODHA_API_KEY",
    "api_secret": "YOUR_ZERODHA_API_SECRET"
  }'
```

### 4. Place Order
```bash
curl -X POST "http://localhost:8000/orders/" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "broker_id": 1,
    "symbol": "INFY",
    "side": "buy",
    "order_type": "market",
    "quantity": 1
  }'
```

### 5. Create Strategy
```bash
curl -X POST "http://localhost:8000/strategies/" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "My MA Strategy",
    "strategy_type": "ma_crossover",
    "parameters": {
      "fast_period": 20,
      "slow_period": 50,
      "stop_loss_percent": 2,
      "take_profit_percent": 5
    }
  }'
```

## File Structure Quick Reference

```
📁 backend/
   📁 app/
      ├── main.py                 # Start app: python -m app.main
      ├── brokers/               # Broker implementations
      ├── strategies/            # Strategy engine
      ├── auth/                  # Authentication
      ├── routes/                # API endpoints
      ├── models/                # Database & schemas
      └── core/                  # Core utilities

📁 frontend/
   ├── src/
   │  ├── pages/                # Pages (Login, Dashboard, etc)
   │  ├── components/           # Reusable components
   │  ├── api/client.js         # API client
   │  └── store/index.js        # State management
   └── vite.config.js           # Build config

📄 .env                          # Configuration (create from .env.example)
📄 docker-compose.yml            # Docker setup
📄 README.md                      # Full documentation
```

## Common Commands

### Backend
```bash
# Start dev server
python -m app.main

# Run tests
pytest

# Check code style
flake8 app/

# Format code
black app/
```

### Frontend
```bash
# Install dependencies
npm install

# Start dev server
npm run dev

# Build for production
npm run build

# Preview production build
npm run preview
```

### Docker
```bash
# Build and start all services
docker-compose up -d

# View logs
docker-compose logs -f backend

# Stop services
docker-compose down

# Rebuild images
docker-compose up -d --build
```

## API Endpoints Summary

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/auth/register` | Register user |
| POST | `/auth/login` | Login user |
| GET | `/auth/me` | Get current user |
| POST | `/brokers/credentials` | Add broker |
| GET | `/brokers/credentials` | List brokers |
| POST | `/orders/` | Place order |
| GET | `/orders/` | List orders |
| DELETE | `/orders/{id}` | Cancel order |
| POST | `/strategies/` | Create strategy |
| GET | `/strategies/` | List strategies |
| POST | `/strategies/{id}/backtest` | Backtest strategy |

## Troubleshooting

### "Connection refused" - Backend not running
```bash
# Make sure backend is running
cd backend
python -m app.main
```

### "Module not found" error
```bash
# Reinstall dependencies
pip install -r requirements.txt

# Check virtual environment is activated
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate      # Windows
```

### "Database connection error"
```bash
# Check PostgreSQL is running
# Update DATABASE_URL in .env
# Ensure database exists
```

### Frontend can't reach API
```bash
# Check CORS is enabled in backend
# Check API URL in frontend/src/api/client.js
# Ensure backend is running on port 8000
```

## Performance Tips

1. **Use async/await** for non-blocking operations
2. **Enable query caching** for frequently accessed data
3. **Optimize images** in dashboard
4. **Use pagination** for large result sets
5. **Monitor database** performance
6. **Enable compression** in production

## Security Checklist

- [ ] Change SECRET_KEY in .env
- [ ] Change ENCRYPTION_KEY in .env
- [ ] Use strong database password
- [ ] Enable HTTPS in production
- [ ] Configure firewall rules
- [ ] Use environment variables for secrets
- [ ] Enable CORS only for trusted domains
- [ ] Keep dependencies updated
- [ ] Use secure broker API keys
- [ ] Enable logging and monitoring

## Development Workflow

```
1. Create feature branch
   git checkout -b feature/my-feature

2. Make changes
   Edit files, test locally

3. Commit changes
   git add .
   git commit -m "feat: Add new feature"

4. Push to remote
   git push origin feature/my-feature

5. Create Pull Request
   Describe changes and submit
```

## Testing Workflow

### Backend Tests
```bash
cd backend
pytest tests/
pytest tests/ -v --cov  # With coverage
```

### Frontend Tests
```bash
cd frontend
npm test
npm test -- --coverage
```

## Deployment Checklist

- [ ] Update all secrets in .env
- [ ] Run database migrations
- [ ] Test all broker integrations
- [ ] Enable HTTPS/SSL
- [ ] Configure domain name
- [ ] Setup error monitoring
- [ ] Configure logging
- [ ] Setup backups
- [ ] Performance testing
- [ ] Load testing

## Useful Resources

- API Docs: http://localhost:8000/docs
- Frontend Development: http://localhost:3000
- Database Admin: Use pgAdmin or DBeaver
- Broker Docs:
  - Zerodha: https://kite.trade/docs
  - Upstox: https://docs.upstox.com
  - Angel One: https://smartapi.angelbroking.com/docs
  - Groww: https://www.groww.in/api

## Key Configurations

### Environment Variables
```
DATABASE_URL          # PostgreSQL connection
SECRET_KEY           # JWT signing key
ENCRYPTION_KEY       # Credential encryption key
ZERODHA_API_KEY      # Zerodha API key
UPSTOX_API_KEY       # Upstox API key
ANGEL_API_KEY        # Angel One API key
GROWW_API_KEY        # Groww API key
LOG_LEVEL            # Logging level (INFO/DEBUG)
```

### Database
- Driver: PostgreSQL 12+
- ORM: SQLAlchemy 2.0+
- Migrations: Alembic (setup ready)

### Frontend
- Node: v16+
- React: 18+
- CSS Framework: Tailwind CSS 3+
- Build Tool: Vite

## Next Steps

1. ✅ Complete setup
2. ✅ Test API endpoints
3. ✅ Connect broker account
4. ✅ Place test order
5. ✅ Create test strategy
6. ✅ Backtest strategy
7. ✅ Review documentation
8. ✅ Deploy to production

---

**Need help?** Check README.md, API_SPECIFICATION.md, or create an issue on GitHub!

**Happy Trading!** 🚀📈
