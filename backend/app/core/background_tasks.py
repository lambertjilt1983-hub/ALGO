"""
Background tasks for token validation and refresh
Runs periodically to check token validity and trigger refresh if needed
"""
from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy.orm import sessionmaker
from app.core.database import engine
from app.models.auth import BrokerCredential
from app.core.token_manager import token_manager
from app.core.logger import logger

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

def start_background_tasks():
    """Initialize and start background scheduler"""
    try:
        # Disabled for now - background scheduler causing shutdown issues
        # To re-enable: uncomment the code below
        logger.log_error("Background tasks disabled (scheduler)", {})
        return
        
        # Remove any existing jobs
        # if scheduler.running:
        #     scheduler.shutdown(wait=False)
        # 
        # # Add token validation task - runs every 30 minutes
        # scheduler.add_job(
        #     validate_all_tokens,
        #     'interval',
        #     minutes=30,
        #     id='validate_tokens',
        #     name='Validate all broker tokens',
        #     replace_existing=True
        # )
        # 
        # scheduler.start()
        # logger.log_error("Background tasks started", {"jobs": len(scheduler.get_jobs())})
        
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
