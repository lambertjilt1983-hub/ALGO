# Broker Integration Guide

## Adding a New Broker

### Step 1: Create Broker Class

Create a new file in `backend/app/brokers/your_broker.py`:

```python
from app.brokers.base import BrokerInterface, OrderData, OrderResponse, Position, Account, BrokerFactory
from app.core.logger import logger

class YourBrokerAPI(BrokerInterface):
    """Your Broker API integration"""
    
    BASE_URL = "https://api.yourbroker.com"
    
    async def authenticate(self) -> bool:
        # Implement authentication
        pass
    
    async def place_order(self, order: OrderData) -> OrderResponse:
        # Implement order placement
        pass
    
    async def cancel_order(self, order_id: str) -> bool:
        # Implement order cancellation
        pass
    
    # Implement other required methods...

# Register broker
BrokerFactory.register_broker("your_broker", YourBrokerAPI)
```

### Step 2: Implement Required Methods

All brokers must implement these methods:

```python
async def authenticate(self) -> bool
async def place_order(self, order: OrderData) -> OrderResponse
async def cancel_order(self, order_id: str) -> bool
async def modify_order(self, order_id: str, order: OrderData) -> OrderResponse
async def get_positions(self) -> List[Position]
async def get_account_info(self) -> Account
async def get_order_status(self, order_id: str) -> OrderResponse
async def get_historical_data(self, symbol: str, interval: str, from_date: datetime, to_date: datetime) -> List[Dict]
async def subscribe_to_stream(self, symbols: List[str]) -> None
def disconnect(self) -> None
```

### Step 3: Test Integration

```python
from app.brokers.base import BrokerFactory

broker = BrokerFactory.create_broker(
    "your_broker",
    api_key="test_key",
    api_secret="test_secret"
)

# Test authentication
await broker.authenticate()

# Test order placement
order = OrderData(
    symbol="INFY",
    order_type="market",
    side="buy",
    quantity=1
)
response = await broker.place_order(order)
```

## Broker-Specific Notes

### Zerodha (Kite Connect)
- API Base: https://api.kite.trade
- Auth: Token-based (requires session ID)
- Symbols: Use trading symbol from NSE/BSE

### Upstox
- API Base: https://api-v2.upstox.com
- Auth: OAuth2 with Bearer token
- Symbols: Use instrument tokens

### Angel One (SmartAPI)
- API Base: https://api.smartapi.angelbroking.com
- Auth: API key + session token
- Symbols: Use exchange tokens

### Groww
- API Base: https://api.groww.in
- Auth: Bearer token
- Symbols: Use standard NSE symbols

## Error Handling

Always handle these scenarios:

```python
try:
    response = await broker.place_order(order)
    if response.status == "failed":
        logger.log_error("Order failed", {"order_id": response.order_id})
except Exception as e:
    logger.log_error("Exception", {"error": str(e)})
```

## Logging

Use the provided logger for all operations:

```python
from app.core.logger import logger

logger.log_api_call("broker_name", "method_name", "success|failed")
logger.log_trade({
    "broker": "name",
    "symbol": "INFY",
    "side": "buy"
})
logger.log_error("Error message", {"context": "data"})
```

## Testing

Test your broker implementation:

```bash
# Run tests
pytest tests/brokers/test_your_broker.py

# Test with real credentials (be careful!)
python -c "
import asyncio
from app.brokers.your_broker import YourBrokerAPI

async def test():
    broker = YourBrokerAPI(api_key='key', api_secret='secret')
    auth = await broker.authenticate()
    print(f'Authenticated: {auth}')

asyncio.run(test())
"
```

## Rate Limiting

Be aware of broker rate limits:
- Zerodha: 100 requests/second
- Upstox: 50 requests/second
- Angel One: 30 requests/second
- Groww: Check documentation

Implement rate limiting in your broker class if needed.
