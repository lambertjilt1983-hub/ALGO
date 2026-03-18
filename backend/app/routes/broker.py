from fastapi import APIRouter, Body, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from typing import List
from app.auth.service import AuthService, BrokerAuthService
from app.models.schemas import BrokerCredentialCreate, BrokerCredentialResponse
from app.models.auth import BrokerCredential, User
from app.core.database import get_db
from app.core.token_manager import token_manager
from app.core.security import encryption_manager
from app.core.config import get_settings
import urllib.parse
import requests
from datetime import datetime, timedelta

router = APIRouter(prefix="/brokers", tags=["brokers"])


def _safe_decrypt(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return encryption_manager.decrypt_credentials(value)
    except Exception:
        return value


def _api_key_preview(value: str | None) -> str | None:
    if not value:
        return None
    return f"{value[:8]}..." if len(value) > 8 else value


def _build_broker_response(credential: BrokerCredential) -> dict:
    """
    Build broker credential response.
    
    IMPORTANT: If token exists in DB, we assume it's still usable unless:
    1. token_expiry is explicitly set and in the past
    2. Validation API call definitively proves it's expired
    
    This prevents spurious "requires_reauth" prompts when tokens are just stale
    but haven't hit their explicit expiry time yet. The trading system will
    attempt token refresh on first use if needed.
    """
    api_key = _safe_decrypt(getattr(credential, "api_key", None))
    has_access_token = bool(getattr(credential, "access_token", None))
    token_status = None
    requires_reauth = None
    
    # Check if token_expiry is explicitly set and in the past
    is_explicitly_expired = (
        credential.token_expiry 
        and credential.token_expiry < datetime.utcnow()
    )

    if credential.broker_name and "zerodha" in credential.broker_name.lower():
        if has_access_token and not is_explicitly_expired:
            # Token exists and hasn't hit explicit expiry time
            # Assume it's still usable for now (trading system will refresh if needed)
            token_status = "stored"
            requires_reauth = False
        elif has_access_token and is_explicitly_expired:
            # Token explicitly expired
            token_status = "expired"
            requires_reauth = True
        else:
            # No token
            token_status = "missing"
            requires_reauth = True
    else:
        token_status = "missing" if not has_access_token else "unknown"
        requires_reauth = not has_access_token

    return {
        "id": credential.id,
        "broker_name": credential.broker_name,
        "is_active": credential.is_active,
        "created_at": credential.created_at,
        "updated_at": credential.updated_at,
        "api_key_preview": _api_key_preview(api_key),
        "has_access_token": has_access_token,
        "token_expiry": credential.token_expiry,
        "token_status": token_status,
        "requires_reauth": requires_reauth,
        "last_used": credential.updated_at,
    }

@router.post("/credentials", response_model=BrokerCredentialResponse)
async def add_broker_credentials(
    credentials: BrokerCredentialCreate,
    db: Session = Depends(get_db),
    token: str = Depends(AuthService.verify_bearer_token)
):
    """Add broker credentials for current user"""
    payload = AuthService.verify_token(token)
    user_id = int(payload.get("sub"))
    
    # Check if broker already exists for this user
    existing = db.query(BrokerCredential).filter(
        (BrokerCredential.user_id == user_id) &
        (BrokerCredential.broker_name == credentials.broker_name)
    ).first()
    
    broker_cred = BrokerAuthService.store_credentials(
        user_id=user_id,
        broker_name=credentials.broker_name,
        api_key=credentials.api_key,
        api_secret=credentials.api_secret,
        db=db,
        access_token=credentials.access_token
    )
    if existing and broker_cred:
        broker_cred.is_active = True
        db.commit()
        db.refresh(broker_cred)
    return _build_broker_response(broker_cred)

@router.get("/credentials", response_model=List[BrokerCredentialResponse])
async def list_broker_credentials(
    db: Session = Depends(get_db),
    token: str = Depends(AuthService.verify_bearer_token)
):
    """List all broker credentials for current user"""
    payload = AuthService.verify_token(token)
    user_id = int(payload.get("sub"))
    
    credentials = db.query(BrokerCredential).filter(
        BrokerCredential.user_id == user_id
    ).all()
    
    return [_build_broker_response(cred) for cred in credentials]

@router.get("/credentials/{broker_name}", response_model=BrokerCredentialResponse)
async def get_broker_credentials(
    broker_name: str,
    db: Session = Depends(get_db),
    token: str = Depends(AuthService.verify_bearer_token)
):
    """Get specific broker credentials"""
    if token is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No authentication token provided")
    payload = AuthService.verify_token(token)
    user_id = int(payload.get("sub"))
    credential = BrokerAuthService.get_credentials(
        user_id=user_id,
        broker_name=broker_name,
        db=db
    )
    return _build_broker_response(credential)

@router.delete("/credentials/{broker_name}")
async def delete_broker_credentials(
    broker_name: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(AuthService.get_current_user)
):
    """Delete broker credentials"""
    credential = db.query(BrokerCredential).filter(
        (BrokerCredential.user_id == current_user.id) &
        (BrokerCredential.broker_name == broker_name)
    ).first()
    
    if not credential:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    
    db.delete(credential)
    db.commit()
    return {"message": "Credentials deleted successfully"}

@router.get("/balance/{broker_id}")
async def get_broker_balance(
    broker_id: int,
    db: Session = Depends(get_db),
    token: str = Depends(AuthService.verify_bearer_token)
):
    """Get account balance from broker with automatic token refresh"""
    payload = AuthService.verify_token(token)
    user_id = int(payload.get("sub"))
    
    # Debug: Check what's stored in database
    credential = db.query(BrokerCredential).filter(
        (BrokerCredential.id == broker_id) &
        (BrokerCredential.user_id == user_id)
    ).first()
    
    # Use automated token manager to handle token refresh and fallback
    result = await token_manager.get_balance_with_fallback(broker_id, db, user_id)
    
    # If token is expired, suggest re-authentication
    if result.get("status") == "token_expired":
        return result
    
    return result

@router.get("/zerodha/login/{broker_id}")
async def zerodha_oauth_login(
    broker_id: int,
    db: Session = Depends(get_db),
    token: str = Depends(AuthService.verify_bearer_token)
):
    """Initiate Zerodha OAuth flow to get access token"""
    payload = AuthService.verify_token(token)
    user_id = int(payload.get("sub"))
    
    credential = db.query(BrokerCredential).filter(
        (BrokerCredential.user_id == user_id) &
        (BrokerCredential.id == broker_id)
    ).first()
    
    if not credential:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Broker credential not found"
        )
    
    # Decrypt API key before using it, fallback to environment if not set in DB
    decrypted_api_key = None
    try:
        if credential.api_key:
            decrypted_api_key = encryption_manager.decrypt_credentials(credential.api_key)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Credentials encrypted with old key. Please delete and re-add this broker."
        )
    
    # Build Zerodha login URL; Zerodha must be configured with the redirect URL
    # Use the frontend URL from config
    settings = get_settings()
    redirect_uri = settings.FRONTEND_URL
    
    # Fallback to environment ZERODHA_API_KEY if not stored in credential
    if not decrypted_api_key:
        decrypted_api_key = settings.ZERODHA_API_KEY
    
    if not decrypted_api_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="API key not found. Please add Zerodha credentials with API key, or set ZERODHA_API_KEY environment variable."
        )
    
    # Store broker_id in state parameter to identify the callback
    state = f"{user_id}:{broker_id}"
    
    # Zerodha login URL (redirect URL is configured in the developer console)
    encoded_state = urllib.parse.quote(state)
    login_url = f"https://kite.zerodha.com/connect/login?api_key={decrypted_api_key}&v=3&state={encoded_state}"
    
    return {
        "login_url": login_url,
        "redirect_url": redirect_uri,
        "state": state,
        "message": "Redirect user to login_url, then handle callback"
    }


@router.get("/upstox/login/{broker_id}")
async def upstox_oauth_login(
    broker_id: int,
    db: Session = Depends(get_db),
    token: str = Depends(AuthService.verify_bearer_token)
):
    """Initiate Upstox OAuth flow to get access token"""
    payload = AuthService.verify_token(token)
    user_id = int(payload.get("sub"))

    credential = db.query(BrokerCredential).filter(
        (BrokerCredential.user_id == user_id) &
        (BrokerCredential.id == broker_id)
    ).first()

    if not credential:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Broker credential not found"
        )

    try:
        decrypted_api_key = encryption_manager.decrypt_credentials(credential.api_key)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Credentials encrypted with old key. Please delete and re-add this broker."
        )

    settings = get_settings()
    redirect_uri = settings.UPSTOX_REDIRECT_URL or settings.FRONTEND_URL
    state = f"upstox:{user_id}:{broker_id}"
    encoded_state = urllib.parse.quote(state)
    encoded_redirect = urllib.parse.quote(redirect_uri)

    login_url = (
        "https://api.upstox.com/v2/login/authorization/dialog"
        f"?response_type=code&client_id={decrypted_api_key}"
        f"&redirect_uri={encoded_redirect}&state={encoded_state}"
    )

    return {
        "login_url": login_url,
        "redirect_url": redirect_uri,
        "state": state,
        "message": "Redirect user to login_url, then exchange code for token"
    }


@router.post("/upstox/exchange/{broker_id}")
def upstox_token_exchange(
    broker_id: int,
    code: str = Body(..., embed=True),
    db: Session = Depends(get_db),
    token: str = Depends(AuthService.verify_bearer_token)
):
    """Exchange Upstox auth code for access token and persist it"""
    payload = AuthService.verify_token(token)
    user_id = int(payload.get("sub"))

    credential = db.query(BrokerCredential).filter(
        (BrokerCredential.user_id == user_id) &
        (BrokerCredential.id == broker_id)
    ).first()

    if not credential:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Broker credential not found"
        )

    settings = get_settings()
    try:
        api_key = encryption_manager.decrypt_credentials(credential.api_key)
        api_secret = encryption_manager.decrypt_credentials(credential.api_secret)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to decrypt credentials: {e}"
        )

    api_key = api_key or settings.UPSTOX_API_KEY
    api_secret = api_secret or settings.UPSTOX_API_SECRET
    redirect_uri = settings.UPSTOX_REDIRECT_URL or settings.FRONTEND_URL

    if not api_key or not api_secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Upstox API key/secret missing"
        )

    try:
        resp = requests.post(
            "https://api.upstox.com/v2/login/authorization/token",
            headers={"accept": "application/json", "Content-Type": "application/x-www-form-urlencoded"},
            data={
                "code": code,
                "client_id": api_key,
                "client_secret": api_secret,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code"
            },
            timeout=20
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Upstox token request failed: {e}")

    if resp.status_code >= 400:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)

    data = resp.json() if resp.content else {}
    access_token = data.get("access_token") or data.get("data", {}).get("access_token")
    refresh_token = data.get("refresh_token") or data.get("data", {}).get("refresh_token")

    if not access_token:
        raise HTTPException(status_code=400, detail="Upstox access token missing in response")

    credential.access_token = encryption_manager.encrypt_credentials(access_token)
    if refresh_token:
        credential.refresh_token = encryption_manager.encrypt_credentials(refresh_token)
    db.add(credential)
    db.commit()
    db.refresh(credential)

    return {"status": "success", "broker_id": credential.id}

@router.get("/debug/tokens")
async def debug_tokens(
    db: Session = Depends(get_db),
    token: str = Depends(AuthService.verify_bearer_token)
):
    """DEBUG: Show all tokens for current user"""
    payload = AuthService.verify_token(token)
    user_id = int(payload.get("sub"))
    
    credentials = db.query(BrokerCredential).filter(
        BrokerCredential.user_id == user_id
    ).all()
    
    result = []
    for cred in credentials:
        result.append({
            "id": cred.id,
            "broker": cred.broker_name,
            "has_api_key": bool(cred.api_key),
            "has_api_secret": bool(cred.api_secret),
            "has_access_token": bool(cred.access_token),
            "access_token_preview": cred.access_token[:50] + "..." if cred.access_token else "NONE",
            "created_at": str(cred.created_at),
            "updated_at": str(cred.updated_at)
        })
    
    return {"user_id": user_id, "credentials": result}

@router.get("/zerodha/callback")
async def zerodha_oauth_callback(
    request_token: str,
    status: str = "success",
    db: Session = Depends(get_db),
    token: str = Depends(AuthService.verify_bearer_token)
):
    """Handle Zerodha OAuth callback and exchange request token for access token"""
    print(f"\n{'='*60}")
    print(f"ZERODHA CALLBACK RECEIVED")
    print(f"Request Token: {request_token}")
    print(f"Status: {status}")
    print(f"{'='*60}\n")
    
    if status != "success":
        print("Status not success, sending JSON failure")
        return {"status": "failed", "message": "Zerodha auth did not return success"}
    
    try:
        from kiteconnect import KiteConnect
        from app.core.security import encryption_manager
        
        # Get authenticated user from token
        payload = AuthService.verify_token(token)
        user_id = int(payload.get("sub"))
        print(f"Authenticated user ID: {user_id}")
        
        # Get the most recent Zerodha credential for THIS user
        credential = db.query(BrokerCredential).filter(
            (BrokerCredential.user_id == user_id) &
            (BrokerCredential.broker_name.ilike("%zerodha%"))
        ).order_by(BrokerCredential.created_at.desc()).first()
        
        if not credential:
            print(f"ERROR: No Zerodha broker found for user {user_id}!")
            return {"status": "error", "message": "No Zerodha broker found for user"}
        
        print(f"Found broker: ID={credential.id}, Name={credential.broker_name}, User={user_id}")
        
        if not credential.api_key or not credential.api_secret:
            print("WARNING: Missing API credentials in DB, attempting to use environment variables...")
            settings = get_settings()
            if not settings.ZERODHA_API_KEY or not settings.ZERODHA_API_SECRET:
                print("ERROR: Missing API credentials!")
                return {"status": "error", "message": "API credentials not found. Please configure Zerodha credentials in your account or set environment variables."}
        else:
            settings = get_settings()
        
        # Decrypt credentials (fallback to environment if not set in DB)
        try:
            decrypted_api_key = encryption_manager.decrypt_credentials(credential.api_key) if credential.api_key else None
            decrypted_api_secret = encryption_manager.decrypt_credentials(credential.api_secret) if credential.api_secret else None
        except Exception as e:
            print(f"ERROR decrypting credentials: {str(e)}")
            settings = get_settings()
            decrypted_api_key = None
            decrypted_api_secret = None
        
        # Use environment fallback if DB values are empty
        decrypted_api_key = decrypted_api_key or settings.ZERODHA_API_KEY
        decrypted_api_secret = decrypted_api_secret or settings.ZERODHA_API_SECRET
        
        if not decrypted_api_key or not decrypted_api_secret:
            print("ERROR: Unable to resolve API key/secret from DB or environment!")
            return {"status": "error", "message": "API credentials not available"}
        
        print(f"Using API key: {decrypted_api_key[:10]}...")
        
        # Decrypt credentials
        kite = KiteConnect(api_key=decrypted_api_key)
        
        # Exchange request token for access token
        print("Generating session with Zerodha...")
        try:
            data = kite.generate_session(request_token, api_secret=decrypted_api_secret)
            access_token = data["access_token"]
            refresh_token = data.get("refresh_token")
            login_time = data.get("login_time")
            print(f"Access token received: {access_token[:20]}...")
        except Exception as kite_error:
            print(f"Kite session generation failed: {str(kite_error)}")
            raise
        
        # Update credential with access token - CRITICAL: Save to DB immediately
        print(f"Saving access token to broker ID: {credential.id}")
        safe_access_token = access_token.strip() if isinstance(access_token, str) else access_token
        credential.access_token = encryption_manager.encrypt_credentials(safe_access_token)
        if refresh_token:
            safe_refresh_token = refresh_token.strip() if isinstance(refresh_token, str) else refresh_token
            credential.refresh_token = encryption_manager.encrypt_credentials(safe_refresh_token)

        if isinstance(login_time, datetime):
            credential.token_expiry = login_time + timedelta(hours=23, minutes=50)
        else:
            credential.token_expiry = datetime.utcnow() + timedelta(hours=23, minutes=50)

        db.add(credential)  # Explicitly add to session
        db.commit()
        
        # Verify it was saved
        db.refresh(credential)
        saved_token = credential.access_token
        print(f"Token saved! Verify: {saved_token[:20] if saved_token else 'NONE'}...")
        
        if not saved_token:
            print("ERROR: Token was not persisted to database!")
            return {"status": "error", "message": "Token failed to save to database"}
        
        # Return JSON for frontend fetch handler
        print("✅ Returning JSON success to frontend")
        return {
            "status": "success",
            "broker_id": credential.id,
            "has_refresh_token": bool(refresh_token),
            "token_expiry": credential.token_expiry.isoformat() if credential.token_expiry else None,
        }
        
    except Exception as e:
        print(f"ERROR in callback: {str(e)}")
        import traceback
        traceback.print_exc()
        error_msg = str(e)
        return {"status": "error", "message": error_msg}
