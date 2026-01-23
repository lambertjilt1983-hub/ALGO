from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from app.auth.service import AuthService
from app.models.schemas import OrderCreate, OrderResponse
from app.models.auth import User
from app.models.trading import Order
from app.core.database import get_db
from app.core.trading_engine import OrderExecutor, RiskManager
from app.core.logger import logger
import asyncio

router = APIRouter(prefix="/orders", tags=["orders"])

@router.post("/", response_model=OrderResponse)
async def place_order(
    order_req: OrderCreate,
    db: Session = Depends(get_db),
    token: str = Depends(AuthService.verify_bearer_token)
):
    """Place a trading order"""
    try:
        payload = AuthService.verify_token(token)
        user_id = int(payload.get("sub"))
        
        # Get broker credentials
        broker_cred = db.query(BrokerCredential).filter(
            (BrokerCredential.user_id == user_id) &
            (BrokerCredential.id == order_req.broker_id)
        ).first()
        
        if not broker_cred:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Broker not found")
        
        # Create order executor
        executor = OrderExecutor(
            broker_cred.broker_name,
            {
                "api_key": broker_cred.api_key,
                "api_secret": broker_cred.api_secret,
                "access_token": broker_cred.access_token
            }
        )
        
        # Execute order
        response = await executor.execute_order(
            symbol=order_req.symbol,
            order_type=order_req.order_type,
            side=order_req.side,
            quantity=order_req.quantity,
            price=order_req.price,
            stop_price=order_req.stop_price
        )
        
        # Store in database
        db_order = Order(
            user_id=user_id,
            broker_id=order_req.broker_id,
            symbol=order_req.symbol,
            order_type=order_req.order_type,
            side=order_req.side,
            quantity=order_req.quantity,
            price=order_req.price,
            stop_price=order_req.stop_price,
            status=response.status,
            broker_order_id=response.order_id
        )
        db.add(db_order)
        db.commit()
        db.refresh(db_order)
        
        return db_order
    except Exception as e:
        logger.log_error("Order placement failed", {"error": str(e)})
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.get("/{order_id}", response_model=OrderResponse)
async def get_order(
    order_id: int,
    db: Session = Depends(get_db),
    token: str = Depends(AuthService.verify_bearer_token)
):
    """Get order details"""
    payload = AuthService.verify_token(token)
    user_id = int(payload.get("sub"))
    
    order = db.query(Order).filter(
        (Order.id == order_id) & (Order.user_id == user_id)
    ).first()
    
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    
    return order

@router.get("/", response_model=List[OrderResponse])
async def list_orders(
    db: Session = Depends(get_db),
    token: str = Depends(AuthService.verify_bearer_token)
):
    """List all orders for current user"""
    payload = AuthService.verify_token(token)
    user_id = int(payload.get("sub"))
    
    orders = db.query(Order).filter(Order.user_id == user_id).all()
    return orders

@router.delete("/{order_id}")
async def cancel_order(
    order_id: int,
    db: Session = Depends(get_db),
    token: str = Depends(AuthService.verify_bearer_token)
):
    """Cancel an order"""
    payload = AuthService.verify_token(token)
    user_id = int(payload.get("sub"))
    
    order = db.query(Order).filter(
        (Order.id == order_id) & (Order.user_id == user_id)
    ).first()
    
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    
    try:
        # Get broker credentials
        broker_cred = db.query(BrokerCredential).filter(
            (BrokerCredential.user_id == user_id) &
            (BrokerCredential.id == order.broker_id)
        ).first()
        
        # Create executor and cancel
        executor = OrderExecutor(
            broker_cred.broker_name,
            {
                "api_key": broker_cred.api_key,
                "api_secret": broker_cred.api_secret,
                "access_token": broker_cred.access_token
            }
        )
        
        success = await executor.cancel_order(order.broker_order_id)
        
        if success:
            order.status = "cancelled"
            db.commit()
        
        return {"success": success, "message": "Order cancelled" if success else "Failed to cancel"}
    except Exception as e:
        logger.log_error("Order cancellation failed", {"error": str(e)})
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

# Import here to avoid circular imports
from app.models.auth import BrokerCredential
