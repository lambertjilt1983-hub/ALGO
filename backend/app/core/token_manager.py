"""
Automated Token Management Service
Handles token refresh, validation, and automatic regeneration
"""
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.models.auth import BrokerCredential
from app.core.security import encryption_manager
from app.core.logger import logger
from app.core.config import get_settings
from kiteconnect import KiteConnect
import requests

class TokenManager:
    """Manages broker tokens with automatic refresh"""
    
    @staticmethod
    def validate_zerodha_token(credential: BrokerCredential) -> bool:
        """
        Validate if Zerodha token is still active
        Returns True if token is valid, False if expired/invalid
        """
        if not credential.access_token or not credential.api_key:
            return False
        
        try:
            api_key = TokenManager._maybe_decrypt(credential.api_key)
            access_token = TokenManager._maybe_decrypt(credential.access_token)
            settings = get_settings()
            api_key = api_key or settings.ZERODHA_API_KEY
            if not api_key or not access_token:
                return False

            kite = KiteConnect(api_key=api_key)
            kite.set_access_token(access_token)
            
            # Test token by making a simple API call
            kite.margins()
            logger.log_info("Token validation", {"broker_id": credential.id, "status": "valid"})
            return True
            
        except Exception as e:
            logger.log_error("Token validation failed", {
                "broker_id": credential.id,
                "error": str(e)
            })
            return False
    
    @staticmethod
    def refresh_zerodha_token(broker_id: int, db: Session, request_token: str | None = None) -> dict:
        """
        Exchange Zerodha request_token for a new access_token and persist it.
        If request_token not provided, uses stored refresh_token column as the request token.
        """
        try:
            credential = db.query(BrokerCredential).filter(
                BrokerCredential.id == broker_id
            ).first()
            
            if not credential:
                return {"status": "error", "message": "Broker credential not found"}
            
            if not credential.api_key or not credential.api_secret:
                return {"status": "error", "message": "API credentials missing"}

            settings = get_settings()
            # Decrypt credentials or fall back to settings/raw
            decrypted_api_key = TokenManager._maybe_decrypt(credential.api_key) or settings.ZERODHA_API_KEY
            decrypted_api_secret = TokenManager._maybe_decrypt(credential.api_secret) or settings.ZERODHA_API_SECRET
            if not decrypted_api_key or not decrypted_api_secret:
                return {"status": "error", "message": "Unable to resolve API key/secret"}

            # Determine request token source
            stored_rt = credential.refresh_token
            if stored_rt:
                stored_rt = TokenManager._maybe_decrypt(stored_rt)

            effective_request_token = request_token or stored_rt
            if not effective_request_token:
                return {
                    "status": "requires_reauth",
                    "message": "Request token missing. Please complete Zerodha login.",
                    "broker_id": broker_id,
                    "action": "redirect_to_zerodha_login"
                }

            logger.log_info("Token refresh attempt", {
                "broker_id": broker_id,
                "broker_name": credential.broker_name
            })

            kite = KiteConnect(api_key=decrypted_api_key)
            session = kite.generate_session(effective_request_token, api_secret=decrypted_api_secret)
            new_access = session.get("access_token")
            login_time = session.get("login_time")

            if not new_access:
                return {"status": "error", "message": "No access token returned from Zerodha"}

            # Persist encrypted tokens
            credential.access_token = encryption_manager.encrypt_credentials(new_access)
            if request_token:
                credential.refresh_token = encryption_manager.encrypt_credentials(request_token)
            credential.token_expiry = None  # Zerodha tokens are day-scoped; expiry managed by validation
            db.add(credential)
            db.commit()
            db.refresh(credential)

            return {
                "status": "success",
                "message": "Access token refreshed",
                "broker_id": broker_id,
                "access_token_last4": new_access[-4:],
                "login_time": login_time.isoformat() if login_time else None,
            }

        except Exception as e:
            logger.log_error("Token refresh failed", {
                "broker_id": broker_id,
                "error": str(e)
            })
            return {"status": "error", "message": str(e)}

    @staticmethod
    def _maybe_decrypt(value: str | None) -> str | None:
        if not value:
            return None
        try:
            return encryption_manager.decrypt_credentials(value)
        except Exception:
            return value
    
    @staticmethod
    def get_balance_with_fallback(broker_id: int, db: Session, user_id: int) -> dict:
        """
        Get balance with automatic token refresh on failure
        Falls back to demo data if token is invalid
        """
        credential = db.query(BrokerCredential).filter(
            (BrokerCredential.id == broker_id) &
            (BrokerCredential.user_id == user_id)
        ).first()
        
        if not credential:
            return {
                "broker_id": broker_id,
                "status": "error",
                "message": "Broker credential not found"
            }
        
        # Check if access token exists - if not, require re-authentication
        if not credential.access_token:
            logger.log_error("No access token stored", {
                "broker_id": broker_id,
                "broker_name": credential.broker_name
            })
            return {
                "broker_id": broker_id,
                "broker_name": credential.broker_name,
                "available_balance": 0,
                "used_margin": 0,
                "total_balance": 0,
                "data_source": "no_token",
                "status": "token_expired",
                "requires_reauth": True,
                "message": "No access token found. Please authenticate with Zerodha.",
                "action": "redirect_to_zerodha_login"
            }
        
        # First, try with current token
        try:
            decrypted_api_key = encryption_manager.decrypt_credentials(credential.api_key)
            decrypted_access_token = TokenManager._maybe_decrypt(credential.access_token)
            if not decrypted_access_token:
                raise Exception("Missing access token; re-auth required")

            kite = KiteConnect(api_key=decrypted_api_key)
            kite.set_access_token(decrypted_access_token)
            
            margins = kite.margins()
            equity_margin = margins.get("equity", {})
            
            return {
                "broker_id": broker_id,
                "broker_name": credential.broker_name,
                "available_balance": float(equity_margin.get("available", {}).get("live_balance", 0)),
                "used_margin": float(equity_margin.get("utilised", {}).get("debits", 0)),
                "total_balance": float(equity_margin.get("net", 0)),
                "data_source": "real_zerodha_api",
                "status": "success"
            }
        
        except Exception as e:
            error_msg = str(e)
            logger.log_error("Token invalid, attempting refresh", {
                "broker_id": broker_id,
                "error": error_msg
            })
            
            # Token is invalid - log this and return status for re-auth
            if "Incorrect" in error_msg or "Token" in error_msg or "401" in error_msg:
                return {
                    "broker_id": broker_id,
                    "broker_name": credential.broker_name,
                    "available_balance": 0,
                    "used_margin": 0,
                    "total_balance": 0,
                    "data_source": "token_expired",
                    "status": "token_expired",
                    "requires_reauth": True,
                    "message": "Access token expired. Please re-authenticate with Zerodha to continue.",
                    "action": "redirect_to_zerodha_login"
                }
            
            # Other API errors - return demo data
            return {
                "broker_id": broker_id,
                "broker_name": credential.broker_name,
                "available_balance": 0,
                "used_margin": 0,
                "total_balance": 0,
                "data_source": "api_error",
                "status": "error",
                "message": f"Zerodha API error: {error_msg}"
            }

token_manager = TokenManager()
