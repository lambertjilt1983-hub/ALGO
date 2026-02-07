#!/usr/bin/env python3
"""
Create all database tables
"""
import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
env_paths = [
    Path('f:/ALGO/backend/.env'),
    Path('f:/ALGO/.env')
]

for env_path in env_paths:
    if env_path.exists():
        load_dotenv(env_path)

sys.path.insert(0, 'f:/ALGO/backend')

from app.core.database import engine, Base
from app.models.auth import User, BrokerCredential, RefreshToken
from app.models.trading import PaperTrade

def create_tables():
    """Create all tables in the database"""
    try:
        print("🔧 Creating database tables...")
        Base.metadata.create_all(bind=engine)
        print("✅ All tables created successfully!")
        return True
    except Exception as e:
        print(f"❌ Error creating tables: {str(e)}")
        return False

if __name__ == "__main__":
    success = create_tables()
    sys.exit(0 if success else 1)
