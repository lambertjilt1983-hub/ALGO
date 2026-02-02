#!/usr/bin/env python3
"""
Script to add a new user to the database
"""
import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env files
env_paths = [
    Path('f:/ALGO/backend/.env'),
    Path('f:/ALGO/.env')
]

for env_path in env_paths:
    if env_path.exists():
        load_dotenv(env_path)
        print(f"✅ Loaded environment from {env_path}")

sys.path.insert(0, 'f:/ALGO/backend')

from app.core.database import SessionLocal
from app.models.auth import User
from app.core.security import encryption_manager
from datetime import datetime

# User details
USERNAME = "lambert"
PASSWORD = "Bangalore@123"
EMAIL = "lambert@algo.com"
MOBILE = "9876543210"
OTP = "123456"

def add_user():
    """Add a new user to the database"""
    db = SessionLocal()
    
    try:
        # Check if user already exists
        existing_user = db.query(User).filter(User.username == USERNAME).first()
        if existing_user:
            print(f"❌ User '{USERNAME}' already exists!")
            return False
        
        # Hash the password
        hashed_password = encryption_manager.hash_password(PASSWORD)
        
        # Create new user
        new_user = User(
            username=USERNAME,
            email=EMAIL,
            mobile=MOBILE,
            hashed_password=hashed_password,
            otp_code=OTP,
            is_active=True,
            is_email_verified=True,
            is_mobile_verified=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        # Add to database
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        
        print(f"✅ User '{USERNAME}' created successfully!")
        print(f"   Username: {USERNAME}")
        print(f"   Email: {EMAIL}")
        print(f"   Mobile: {MOBILE}")
        print(f"   OTP: {OTP}")
        print(f"   User ID: {new_user.id}")
        print(f"\n✅ User can now login with:")
        print(f"   Username: {USERNAME}")
        print(f"   Password: {PASSWORD}")
        
        return True
        
    except Exception as e:
        db.rollback()
        print(f"❌ Error creating user: {str(e)}")
        return False
    
    finally:
        db.close()

if __name__ == "__main__":
    print("🔧 Adding new user to database...\n")
    success = add_user()
    sys.exit(0 if success else 1)
