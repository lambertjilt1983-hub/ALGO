# AlgoTrade Pro - Quick Start Guide

## 5-Minute Setup

### Step 1: Backend (2 minutes)
```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
python -m app.main
```

### Step 2: Frontend (2 minutes)
```bash
cd frontend
npm install
npm run dev
```

### Step 3: Access Application (1 minute)
- Frontend: `http://localhost:3000`
- Backend API: `http://localhost:8000`
- API Docs: `http://localhost:8000/docs`

## Default Configuration
- Database: PostgreSQL (localhost)
- Backend Port: 8000
- Frontend Port: 3000

## First Trade

1. **Register Account**
   - Go to http://localhost:3000
   - Click "Register"
   - Enter username, email, password

2. **Add Broker**
   - Login to your account
   - Go to Brokers page
   - Click "Add Broker"
   - Enter API credentials from your broker

3. **Place Order**
   - Go to Orders page
   - Click "New Order"
   - Select broker, symbol (e.g., INFY)
   - Choose side (Buy/Sell), quantity
   - Click "Place Order"

4. **View Dashboard**
   - Real-time account balance
   - Active positions
   - Order history
   - Strategy performance

## Key Passwords & Settings to Update

In `.env` file:
```
SECRET_KEY=generate-strong-key
ENCRYPTION_KEY=generate-encryption-key
DATABASE_URL=postgresql://user:password@localhost:5432/trading_db
```

## Production Deployment

1. Update all secrets in `.env`
2. Use PostgreSQL in production
3. Enable HTTPS
4. Configure CORS for your domain
5. Set up monitoring and logging
6. Deploy backend to cloud (AWS, Azure, GCP)
7. Deploy frontend to CDN or web server

## Support & Documentation

- API Docs: http://localhost:8000/docs
- Full README: See README.md
- GitHub Issues for bug reports

Happy Trading! 🚀
