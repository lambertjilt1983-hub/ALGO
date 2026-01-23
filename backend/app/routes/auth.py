from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.auth.service import AuthService, BrokerAuthService
from app.models.schemas import UserCreate, UserLogin, TokenResponse, UserResponse, OtpVerify
from app.models.auth import User
from app.core.database import get_db

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/register", response_model=UserResponse)
async def register(user_data: UserCreate, db: Session = Depends(get_db)):
    """Register new user"""
    user = AuthService.register_user(user_data, db)
    return user

@router.post("/login", response_model=TokenResponse)
async def login(user_data: UserLogin, db: Session = Depends(get_db)):
    """Login user and get tokens"""
    tokens = AuthService.login_user(user_data, db)
    return tokens


@router.post("/verify-otp", response_model=TokenResponse)
async def verify_otp(payload: OtpVerify, db: Session = Depends(get_db)):
    """Verify OTP for MFA and return tokens"""
    tokens = AuthService.verify_otp(payload, db)
    return tokens

@router.post("/refresh")
async def refresh_token(refresh_token: str, db: Session = Depends(get_db)):
    """Refresh access token"""
    try:
        payload = AuthService.verify_token(refresh_token)
        user_id = payload.get("sub")
        
        if not user_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
        
        new_access_token = AuthService.create_access_token({"sub": str(user_id)})
        return {
            "access_token": new_access_token,
            "token_type": "bearer"
        }
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)

@router.get("/me", response_model=UserResponse)
async def get_current_user(db: Session = Depends(get_db), token = Depends(AuthService.verify_bearer_token)):
    """Get current user profile"""
    try:
        payload = AuthService.verify_token(token)
        user_id = payload.get("sub")
        
        user = db.query(User).filter(User.id == int(user_id)).first()
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
        
        return user
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))


def _require_admin(current_user: User) -> User:
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return current_user


@router.get("/admin/users", response_model=list[UserResponse])
async def list_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(AuthService.get_current_user),
):
    _require_admin(current_user)
    return db.query(User).all()
