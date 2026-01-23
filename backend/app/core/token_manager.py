"""
Automated Token Management Service
Handles token refresh, validation, and automatic regeneration
"""
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.models.auth import BrokerCredential
from app.core.security import encryption_manager
from app.core.logger import logger
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
            decrypted_api_key = encryption_manager.decrypt_credentials(credential.api_key)
            kite = KiteConnect(api_key=decrypted_api_key)
            kite.set_access_token(credential.access_token)
            
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
    def refresh_zerodha_token(broker_id: int, db: Session) -> dict:
        """
        Attempt to refresh Zerodha access token
        Uses stored API key and secret to get new token
        """
        try:
            credential = db.query(BrokerCredential).filter(
                BrokerCredential.id == broker_id
            ).first()
            
            if not credential:
                return {"status": "error", "message": "Broker credential not found"}
            
            if not credential.api_key or not credential.api_secret:
                return {"status": "error", "message": "API credentials missing"}
            
            # Decrypt credentials
            decrypted_api_key = encryption_manager.decrypt_credentials(credential.api_key)
            decrypted_api_secret = encryption_manager.decrypt_credentials(credential.api_secret)
            
            logger.log_info("Token refresh attempt", {
                "broker_id": broker_id,
                "broker_name": credential.broker_name
            })
            
            # For Zerodha, we need a request token to exchange for access token
            # If we don't have one, we trigger a re-auth flow
            # This is a limitation of OAuth - we can't refresh without user interaction
            
            return {
                "status": "requires_reauth",
                "message": "Token expired. Please re-authenticate with Zerodha.",
                "broker_id": broker_id,
                "action": "redirect_to_zerodha_login"
            }
            
        except Exception as e:
            logger.log_error("Token refresh failed", {
                "broker_id": broker_id,
                "error": str(e)
            })
            return {"status": "error", "message": str(e)}
    
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
            kite = KiteConnect(api_key=decrypted_api_key)
            kite.set_access_token(credential.access_token)
            
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
