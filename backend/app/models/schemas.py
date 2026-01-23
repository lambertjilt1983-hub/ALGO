from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime

# User Schemas
class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str

class UserLogin(BaseModel):
    username: str
    password: str

class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    is_active: bool
    created_at: datetime

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

# Broker Credential Schemas
class BrokerCredentialCreate(BaseModel):
    broker_name: str
    api_key: str
    api_secret: str

class BrokerCredentialResponse(BaseModel):
    id: int
    broker_name: str
    is_active: bool
    created_at: datetime
    
    class Config:
        from_attributes = True

# Order Schemas
class OrderCreate(BaseModel):
    symbol: str
    order_type: str  # market, limit, stop_loss
    side: str  # buy, sell
    quantity: float
    price: Optional[float] = None
    stop_price: Optional[float] = None
    broker_id: int

class OrderResponse(BaseModel):
    id: int
    symbol: str
    order_type: str
    side: str
    quantity: float
    price: Optional[float]
    status: str
    filled_quantity: float
    average_price: Optional[float]
    created_at: datetime
    executed_at: Optional[datetime]
    
    class Config:
        from_attributes = True

# Strategy Schemas
class StrategyCreate(BaseModel):
    name: str
    description: Optional[str] = None
    strategy_type: str
    parameters: dict

class StrategyResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    strategy_type: str
    parameters: dict
    status: str
    is_live: bool
    created_at: datetime
    
    class Config:
        from_attributes = True

class BacktestRequest(BaseModel):
    strategy_id: int
    start_date: str
    end_date: str
    initial_capital: float = 100000

class BacktestResponse(BaseModel):
    total_return: float
    sharpe_ratio: float
    max_drawdown: float
    win_rate: float
    total_trades: int
    created_at: datetime
    
    class Config:
        from_attributes = True
