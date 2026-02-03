"""
Background tasks for token validation and refresh
Runs periodically to check token validity and trigger refresh if needed
Also handles market closing time exit for all open trades
"""
from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy.orm import sessionmaker
from app.core.database import engine
from app.models.auth import BrokerCredential
from app.models.trading import PaperTrade
from app.core.token_manager import token_manager
from app.core.logger import logger
from app.engine.paper_trade_updater import update_open_paper_trades
from datetime import datetime, time

# Create a session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

scheduler = BackgroundScheduler()

def validate_all_tokens():
    """Validate all broker tokens and log status"""
    db = SessionLocal()
    try:
        # Get all active Zerodha credentials
        credentials = db.query(BrokerCredential).filter(
            (BrokerCredential.broker_name.ilike("%zerodha%")) &
            (BrokerCredential.is_active == True)
        ).all()
        
        for credential in credentials:
            is_valid = token_manager.validate_zerodha_token(credential)
            
            if not is_valid and credential.access_token:
                logger.log_error("Token validation failed", {
                    "broker_id": credential.id,
                    "user_id": credential.user_id,
                    "broker_name": credential.broker_name,
                    "action": "user_should_re-authenticate"
                })
    
    except Exception as e:
        logger.log_error("Token validation task failed", {"error": str(e)})
    finally:
        db.close()

def close_market_close_trades():
    """Close all open trades at market closing time (3:25 PM IST)"""
    db = SessionLocal()
    try:
        # Get current time in IST (India Standard Time)
        current_time = datetime.now()
        
        # Market closing time: 3:25 PM (15:25)
        market_close = time(15, 25)
        
        # Check if current time is within market close window (3:25 PM - 3:30 PM)
        current_time_only = current_time.time()
        if market_close <= current_time_only <= time(15, 30):
            # Close all open trades
            open_trades = db.query(PaperTrade).filter(PaperTrade.status == "OPEN").all()
            
            closed_count = 0
            for trade in open_trades:
                trade.status = "EXPIRED"
                trade.exit_time = datetime.utcnow()
                closed_count += 1
            
            if closed_count > 0:
                db.commit()
                logger.log_error("Market close - Trades auto-exited", {
                    "closed_count": closed_count,
                    "time": current_time.isoformat(),
                    "reason": "Market closing time (3:25 PM IST)"
                })
    
    except Exception as e:
        db.rollback()
        logger.log_error("Market close exit task failed", {"error": str(e)})
    finally:
        db.close()


def update_open_paper_trades_task():
    """Periodically update open paper trades to enforce SL even if frontend is idle."""
    db = SessionLocal()
    try:
        update_open_paper_trades(db)
    except Exception as e:
        logger.log_error("Paper trade update task failed", {"error": str(e)})
    finally:
        db.close()

def start_background_tasks():
    """Initialize and start background scheduler"""
    try:
        # Remove any existing jobs
        if scheduler.running:
            scheduler.shutdown(wait=False)
        
        # Add token validation task - runs every 30 minutes
        scheduler.add_job(
            validate_all_tokens,
            'interval',
            minutes=30,
            id='validate_tokens',
            name='Validate all broker tokens',
            replace_existing=True
        )
        
        # Add market close exit task - runs every 1 minute (checks if it's 3:30-3:35 PM)
        scheduler.add_job(
            close_market_close_trades,
            'interval',
            minutes=1,
            id='market_close_exit',
            name='Auto-exit open trades at market close',
            replace_existing=True
        )

        # Add paper trade price updates - runs every 10 seconds
        scheduler.add_job(
            update_open_paper_trades_task,
            'interval',
            seconds=10,
            id='paper_trade_updates',
            name='Update open paper trades (SL enforcement)',
            replace_existing=True
        )
        
        scheduler.start()
        logger.log_info("Background tasks started", {
            "jobs": len(scheduler.get_jobs()),
            "market_close_time": "3:25 PM IST (3:25-3:30 PM IST window)"
        })
        
    except Exception as e:
        logger.log_error("Failed to start background tasks", {"error": str(e)})

def stop_background_tasks():
    """Stop background scheduler"""
    try:
        if scheduler.running:
            scheduler.shutdown(wait=True)
            logger.log_error("Background tasks stopped", {})
    except Exception as e:
        logger.log_error("Failed to stop background tasks", {"error": str(e)})
