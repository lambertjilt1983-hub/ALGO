"""
Token Refresh Routes
Endpoints for checking token status and triggering refresh operations
"""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.auth.service import AuthService
from app.models.auth import BrokerCredential, User
from app.core.token_manager import token_manager
from app.core.logger import logger

router = APIRouter(prefix="/api/tokens", tags=["tokens"])


class RefreshRequest(BaseModel):
    request_token: str | None = None

@router.get("/status/{broker_id}")
async def get_token_status(
    broker_id: int,
    db: Session = Depends(get_db),
    token: str = Depends(AuthService.verify_bearer_token)
):
    """
    Check if broker token is still valid
    Returns token status and whether re-auth is needed
    """
    try:
        payload = AuthService.verify_token(token)
        user_id = int(payload.get("sub"))
        
        credential = db.query(BrokerCredential).filter(
            (BrokerCredential.id == broker_id) &
            (BrokerCredential.user_id == user_id)
        ).first()
        
        if not credential:
            raise HTTPException(status_code=404, detail="Broker credential not found")
        
        is_valid = token_manager.validate_zerodha_token(credential)
        
        logger.log_info("Token status check", {
            "broker_id": broker_id,
            "user_id": user_id,
            "is_valid": is_valid
        })
        
        return {
            "broker_id": broker_id,
            "broker_name": credential.broker_name,
            "is_valid": is_valid,
            "has_token": bool(credential.access_token),
            "requires_reauth": not is_valid,
            "last_refreshed": credential.updated_at.isoformat() if credential.updated_at else None
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.log_error("Failed to check token status", {"error": str(e)})
        raise HTTPException(status_code=500, detail="Failed to check token status")

@router.post("/refresh/{broker_id}")
async def attempt_token_refresh(
    broker_id: int,
    body: RefreshRequest | None = None,
    db: Session = Depends(get_db),
    token: str = Depends(AuthService.verify_bearer_token)
):
    """
    Attempt to refresh broker token
    For Zerodha, this requires re-authentication via OAuth
    Returns auth URL if needed
    """
    try:
        payload = AuthService.verify_token(token)
        user_id = int(payload.get("sub"))
        
        credential = db.query(BrokerCredential).filter(
            (BrokerCredential.id == broker_id) &
            (BrokerCredential.user_id == user_id)
        ).first()
        
        if not credential:
            raise HTTPException(status_code=404, detail="Broker credential not found")
        
        # Attempt refresh - for Zerodha, this will indicate re-auth is needed
        refresh_result = token_manager.refresh_zerodha_token(broker_id, db, request_token=body.request_token if body else None)
        
        logger.log_info("Token refresh attempted", {
            "broker_id": broker_id,
            "user_id": user_id,
            "result_status": refresh_result.get("status")
        })
        
        return {
            "broker_id": broker_id,
            "broker_name": credential.broker_name,
            **refresh_result
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.log_error("Failed to refresh token", {"error": str(e)})
        raise HTTPException(status_code=500, detail="Failed to refresh token")

@router.get("/validate-all")
async def validate_all_tokens(
    db: Session = Depends(get_db),
    token: str = Depends(AuthService.verify_bearer_token)
):
    """
    Validate all tokens for the authenticated user
    Returns status of all broker connections
    """
    try:
        payload = AuthService.verify_token(token)
        user_id = int(payload.get("sub"))
        
        credentials = db.query(BrokerCredential).filter(
            BrokerCredential.user_id == user_id
        ).all()
        
        results = []
        for credential in credentials:
            try:
                is_valid = token_manager.validate_zerodha_token(credential)
                results.append({
                    "broker_id": credential.id,
                    "broker_name": credential.broker_name,
                    "is_valid": is_valid,
                    "status": "active" if is_valid else "requires_reauth"
                })
            except Exception as e:
                results.append({
                    "broker_id": credential.id,
                    "broker_name": credential.broker_name,
                    "is_valid": False,
                    "status": "error",
                    "error": str(e)
                })
        
        logger.log_info("All tokens validated", {
            "user_id": user_id,
            "total_brokers": len(credentials),
            "valid_count": sum(1 for r in results if r.get("is_valid"))
        })
        
        return {
            "user_id": user_id,
            "total_brokers": len(credentials),
            "brokers": results,
            "all_valid": all(r.get("is_valid") for r in results)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.log_error("Failed to validate all tokens", {"error": str(e)})
        raise HTTPException(status_code=500, detail="Failed to validate all tokens")
