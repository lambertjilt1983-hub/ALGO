from datetime import datetime, timedelta
import secrets
from typing import Optional
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import encryption_manager
from app.core.database import get_db, SessionLocal
from app.models.auth import User, BrokerCredential
from app.models.schemas import UserCreate, UserLogin, TokenResponse, OtpVerify

settings = get_settings()
security = HTTPBearer()

class AuthService:
    """Authentication and JWT token management"""

    @staticmethod
    def _generate_otp() -> str:
        return f"{secrets.randbelow(900000) + 100000}"

    @staticmethod
    def _send_otp(user: User, otp: str) -> None:
        # Placeholder for SMS/Email integrations; logged for now.
        print(f"[OTP] Send to email {user.email} and mobile {user.mobile}: {otp}")
    
    @staticmethod
    def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
        """Create JWT access token"""
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
        return encoded_jwt
    
    @staticmethod
    def create_refresh_token(user_id: int) -> str:
        """Create refresh token"""
        data = {"sub": str(user_id), "type": "refresh"}
        return AuthService.create_access_token(data, expires_delta=timedelta(days=7))
    
    @staticmethod
    def verify_token(token: str) -> dict:
        """Verify and decode JWT token"""
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
            user_id = payload.get("sub")
            if user_id is None:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
            return payload
        except JWTError:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    
    @staticmethod
    def register_user(user_data: UserCreate, db: Session) -> User:
        """Register new user"""
        # Check if user exists
        existing_user = db.query(User).filter(
            (User.email == user_data.email) | (User.username == user_data.username) | (User.mobile == user_data.mobile)
        ).first()
        
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User already exists"
            )
        
        # Hash password and create user
        hashed_password = encryption_manager.hash_password(user_data.password)
        otp = AuthService._generate_otp()
        expires_at = datetime.utcnow() + timedelta(minutes=10)

        db_user = User(
            username=user_data.username,
            email=user_data.email,
            mobile=user_data.mobile,
            hashed_password=hashed_password,
            is_email_verified=False,
            is_mobile_verified=False,
            is_admin=False,
            otp_code=otp,
            otp_expires_at=expires_at,
            last_otp_sent_at=datetime.utcnow(),
        )
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        AuthService._send_otp(db_user, otp)
        return db_user
    
    @staticmethod
    def login_user(user_data: UserLogin, db: Session) -> dict:
        """Authenticate user and return tokens"""
        user = db.query(User).filter(User.username == user_data.username).first()
        
        if not user or not encryption_manager.verify_password(user_data.password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials"
            )

        # Admin is allowed to sign in without OTP friction
        if user.is_admin and (not user.is_email_verified or not user.is_mobile_verified):
            user.is_email_verified = True
            user.is_mobile_verified = True
            db.commit()
            db.refresh(user)

        if not (user.is_email_verified and user.is_mobile_verified):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="OTP verification required")

        access_token = AuthService.create_access_token({"sub": str(user.id)})
        refresh_token = AuthService.create_refresh_token(user.id)
        
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer"
        }

    @staticmethod
    def verify_otp(payload: OtpVerify, db: Session) -> dict:
        user = db.query(User).filter((User.username == payload.username) | (User.email == payload.username)).first()
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        if not user.otp_code or not user.otp_expires_at:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No OTP pending")

        if datetime.utcnow() > user.otp_expires_at:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="OTP expired")

        if str(payload.otp).strip() != str(user.otp_code).strip():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid OTP")

        user.is_email_verified = True
        user.is_mobile_verified = True
        user.otp_code = None
        user.otp_expires_at = None
        db.commit()
        db.refresh(user)

        access_token = AuthService.create_access_token({"sub": str(user.id)})
        refresh_token = AuthService.create_refresh_token(user.id)

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer"
        }
    
    @staticmethod
    def verify_bearer_token(credentials = Depends(security)) -> str:
        """Extract and return bearer token from credentials"""
        return credentials.credentials
    
    @staticmethod
    def get_current_user(
        token: str = Depends(security),
        db: Session = Depends(get_db)
    ) -> User:
        """Get current authenticated user"""
        # Extract bearer token from credentials
        if hasattr(token, 'credentials'):
            raw_token = token.credentials
        else:
            raw_token = token

        payload = AuthService.verify_token(raw_token)
        user_id = payload.get("sub")
        
        user = db.query(User).filter(User.id == int(user_id)).first()
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
        
        return user

    @staticmethod
    def ensure_default_admin(db: Optional[Session] = None) -> Optional[User]:
        """Ensure a default admin account exists with OTP bypass."""
        local_db = db or SessionLocal()
        try:
            admin = local_db.query(User).filter(User.username == "admin").first()

            if not admin:
                admin_password = encryption_manager.hash_password("admin123")
                admin = User(
                    username="admin",
                    email="admin@system.local",
                    mobile=None,
                    hashed_password=admin_password,
                    is_active=True,
                    is_admin=True,
                    is_email_verified=True,
                    is_mobile_verified=True,
                )
                local_db.add(admin)
                local_db.commit()
                local_db.refresh(admin)
                return admin

            # Keep existing admin aligned with required flags
            updated = False
            if not admin.is_admin:
                admin.is_admin = True
                updated = True
            if not admin.is_active:
                admin.is_active = True
                updated = True
            if not (admin.is_email_verified and admin.is_mobile_verified):
                admin.is_email_verified = True
                admin.is_mobile_verified = True
                updated = True
            if not encryption_manager.verify_password("admin123", admin.hashed_password):
                admin.hashed_password = encryption_manager.hash_password("admin123")
                updated = True

            if updated:
                local_db.commit()
                local_db.refresh(admin)

            return admin
        finally:
            if db is None:
                local_db.close()

class BrokerAuthService:
    """Manage broker-specific authentication and credentials"""
    
    @staticmethod
    def store_credentials(
        user_id: int,
        broker_name: str,
        api_key: str,
        api_secret: str,
        db: Session
    ) -> BrokerCredential:
        """Store encrypted broker credentials"""
        encrypted_key = encryption_manager.encrypt_credentials(api_key)
        encrypted_secret = encryption_manager.encrypt_credentials(api_secret)
        
        # Check if credentials exist
        existing = db.query(BrokerCredential).filter(
            (BrokerCredential.user_id == user_id) &
            (BrokerCredential.broker_name == broker_name)
        ).first()
        
        if existing:
            existing.api_key = encrypted_key
            existing.api_secret = encrypted_secret
            existing.updated_at = datetime.utcnow()
            db.commit()
            db.refresh(existing)
            return existing
        
        credential = BrokerCredential(
            user_id=user_id,
            broker_name=broker_name,
            api_key=encrypted_key,
            api_secret=encrypted_secret
        )
        db.add(credential)
        db.commit()
        db.refresh(credential)
        return credential
    
    @staticmethod
    def get_credentials(
        user_id: int,
        broker_name: str,
        db: Session
    ) -> BrokerCredential:
        """Retrieve and decrypt broker credentials"""
        credential = db.query(BrokerCredential).filter(
            (BrokerCredential.user_id == user_id) &
            (BrokerCredential.broker_name == broker_name)
        ).first()
        
        if not credential:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No credentials found for {broker_name}"
            )
        
        return credential
    
    @staticmethod
    def update_oauth_token(
        user_id: int,
        broker_name: str,
        access_token: str,
        refresh_token: Optional[str] = None,
        token_expiry: Optional[datetime] = None,
        db: Session = None
    ) -> BrokerCredential:
        """Update OAuth tokens for broker"""
        credential = db.query(BrokerCredential).filter(
            (BrokerCredential.user_id == user_id) &
            (BrokerCredential.broker_name == broker_name)
        ).first()
        
        if credential:
            credential.access_token = access_token
            if refresh_token:
                credential.refresh_token = encryption_manager.encrypt_credentials(refresh_token)
            credential.token_expiry = token_expiry
            credential.updated_at = datetime.utcnow()
            db.commit()
            db.refresh(credential)
        
        return credential
