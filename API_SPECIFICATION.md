# AlgoTrade Pro API Specification

## Base URL
```
http://localhost:8000/api
```

## Authentication
All endpoints (except `/auth/register` and `/auth/login`) require:
```
Authorization: Bearer {access_token}
```

## Rate Limiting
- Default: 100 requests per minute
- Per-endpoint limits specified in response headers

## Response Format
```json
{
  "data": {},
  "success": true,
  "error": null
}
```

## Error Codes
- `200` - Success
- `201` - Created
- `400` - Bad Request
- `401` - Unauthorized
- `403` - Forbidden
- `404` - Not Found
- `422` - Validation Error
- `429` - Too Many Requests
- `500` - Internal Server Error

---

## Auth Endpoints

### Register User
```
POST /auth/register
Content-Type: application/json

{
  "username": "trader1",
  "email": "trader@example.com",
  "password": "secure_password"
}

Response: 201
{
  "id": 1,
  "username": "trader1",
  "email": "trader@example.com",
  "is_active": true,
  "created_at": "2024-01-21T10:00:00Z"
}
```

### Login
```
POST /auth/login
Content-Type: application/json

{
  "username": "trader1",
  "password": "secure_password"
}

Response: 200
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "token_type": "bearer"
}
```

### Get Current User
```
GET /auth/me
Authorization: Bearer {token}

Response: 200
{
  "id": 1,
  "username": "trader1",
  "email": "trader@example.com",
  "is_active": true,
  "created_at": "2024-01-21T10:00:00Z"
}
```

### Refresh Token
```
POST /auth/refresh
Content-Type: application/json

{
  "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGc..."
}

Response: 200
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "token_type": "bearer"
}
```

---

## Broker Endpoints

### Add Broker Credentials
```
POST /brokers/credentials
Authorization: Bearer {token}
Content-Type: application/json

{
  "broker_name": "zerodha",
  "api_key": "your_api_key",
  "api_secret": "your_api_secret"
}

Response: 201
{
  "id": 1,
  "broker_name": "zerodha",
  "is_active": true,
  "created_at": "2024-01-21T10:00:00Z"
}
```

### List Broker Credentials
```
GET /brokers/credentials
Authorization: Bearer {token}

Response: 200
[
  {
    "id": 1,
    "broker_name": "zerodha",
    "is_active": true,
    "created_at": "2024-01-21T10:00:00Z"
  }
]
```

### Get Specific Broker
```
GET /brokers/credentials/{broker_name}
Authorization: Bearer {token}

Response: 200
{
  "id": 1,
  "broker_name": "zerodha",
  "is_active": true,
  "created_at": "2024-01-21T10:00:00Z"
}
```

### Delete Broker Credentials
```
DELETE /brokers/credentials/{broker_name}
Authorization: Bearer {token}

Response: 200
{
  "message": "Credentials deleted successfully"
}
```

---

## Orders Endpoints

### Place Order
```
POST /orders/
Authorization: Bearer {token}
Content-Type: application/json

{
  "broker_id": 1,
  "symbol": "INFY",
  "side": "buy",
  "order_type": "market",
  "quantity": 1.0,
  "price": null,
  "stop_price": null
}

Response: 201
{
  "id": 1,
  "symbol": "INFY",
  "order_type": "market",
  "side": "buy",
  "quantity": 1.0,
  "price": null,
  "status": "pending",
  "filled_quantity": 0.0,
  "average_price": null,
  "created_at": "2024-01-21T10:00:00Z",
  "executed_at": null
}
```

### List Orders
```
GET /orders/
Authorization: Bearer {token}

Response: 200
[
  {
    "id": 1,
    "symbol": "INFY",
    "order_type": "market",
    "side": "buy",
    "quantity": 1.0,
    "status": "filled",
    "created_at": "2024-01-21T10:00:00Z"
  }
]
```

### Get Order Details
```
GET /orders/{order_id}
Authorization: Bearer {token}

Response: 200
{
  "id": 1,
  "symbol": "INFY",
  "order_type": "market",
  "side": "buy",
  "quantity": 1.0,
  "status": "filled",
  "filled_quantity": 1.0,
  "average_price": 2500.50,
  "created_at": "2024-01-21T10:00:00Z",
  "executed_at": "2024-01-21T10:05:00Z"
}
```

### Cancel Order
```
DELETE /orders/{order_id}
Authorization: Bearer {token}

Response: 200
{
  "success": true,
  "message": "Order cancelled"
}
```

---

## Strategies Endpoints

### Create Strategy
```
POST /strategies/
Authorization: Bearer {token}
Content-Type: application/json

{
  "name": "MA Crossover Pro",
  "description": "Moving average crossover strategy",
  "strategy_type": "ma_crossover",
  "parameters": {
    "fast_period": 20,
    "slow_period": 50,
    "stop_loss_percent": 2,
    "take_profit_percent": 5
  }
}

Response: 201
{
  "id": 1,
  "name": "MA Crossover Pro",
  "description": "Moving average crossover strategy",
  "strategy_type": "ma_crossover",
  "parameters": {...},
  "status": "inactive",
  "is_live": false,
  "created_at": "2024-01-21T10:00:00Z"
}
```

### List Strategies
```
GET /strategies/
Authorization: Bearer {token}

Response: 200
[
  {
    "id": 1,
    "name": "MA Crossover Pro",
    "strategy_type": "ma_crossover",
    "status": "inactive",
    "is_live": false
  }
]
```

### Get Strategy Details
```
GET /strategies/{strategy_id}
Authorization: Bearer {token}

Response: 200
{
  "id": 1,
  "name": "MA Crossover Pro",
  "description": "...",
  "strategy_type": "ma_crossover",
  "parameters": {...},
  "status": "inactive",
  "is_live": false,
  "created_at": "2024-01-21T10:00:00Z"
}
```

### Backtest Strategy
```
POST /strategies/{strategy_id}/backtest
Authorization: Bearer {token}
Content-Type: application/json

{
  "start_date": "2023-01-01",
  "end_date": "2024-01-01",
  "initial_capital": 100000.0
}

Response: 201
{
  "total_return": 0.25,
  "sharpe_ratio": 1.5,
  "max_drawdown": -0.08,
  "win_rate": 0.65,
  "total_trades": 45,
  "created_at": "2024-01-21T10:00:00Z"
}
```

### Update Strategy
```
PUT /strategies/{strategy_id}
Authorization: Bearer {token}
Content-Type: application/json

{
  "name": "MA Crossover Updated",
  "description": "...",
  "strategy_type": "ma_crossover",
  "parameters": {...}
}

Response: 200
{...}
```

### Delete Strategy
```
DELETE /strategies/{strategy_id}
Authorization: Bearer {token}

Response: 200
{
  "message": "Strategy deleted"
}
```

---

## Supported Brokers

- `zerodha` - Zerodha Kite Connect
- `upstox` - Upstox API
- `angel_one` - Angel One SmartAPI
- `groww` - Groww Broker

## Supported Strategies

- `ma_crossover` - Moving Average Crossover
- `rsi` - Relative Strength Index
- `momentum` - Momentum Trading

## Webhook Notifications (Future)

Subscribe to order and strategy events:
```
POST /webhooks/subscribe
{
  "event": "order.filled",
  "url": "https://your-app.com/webhook"
}
```

---

**API Version: 1.0.0**
**Last Updated: 2024-01-21**
