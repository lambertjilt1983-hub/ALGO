from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import encryption_manager
from app.core.database import get_db
from app.models.auth import User, BrokerCredential
from app.models.schemas import UserCreate, UserLogin, TokenResponse

settings = get_settings()
security = HTTPBearer()

class AuthService:
    """Authentication and JWT token management"""
    
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
            (User.email == user_data.email) | (User.username == user_data.username)
        ).first()
        
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User already exists"
            )
        
        # Hash password and create user
        hashed_password = encryption_manager.hash_password(user_data.password)
        db_user = User(
            username=user_data.username,
            email=user_data.email,
            hashed_password=hashed_password
        )
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
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
