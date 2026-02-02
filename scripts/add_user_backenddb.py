import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from datetime import datetime

# Force DB to backend/local.db
os.environ['DATABASE_URL'] = 'sqlite:///f:/ALGO/backend/local.db'
load_dotenv(Path('f:/ALGO/backend/.env.qa'))

sys.path.insert(0, 'f:/ALGO/backend')

from app.core.database import SessionLocal, Base, engine
from app.models.auth import User
from app.core.security import encryption_manager

Base.metadata.create_all(bind=engine)

def upsert_user():
    db = SessionLocal()
    try:
        username = 'lambert'
        password = 'Bangalore@123'
        user = db.query(User).filter(User.username == username).first()
        if user:
            user.hashed_password = encryption_manager.hash_password(password)
            user.is_email_verified = True
            user.is_mobile_verified = True
            user.is_active = True
            user.otp_code = '123456'
            user.updated_at = datetime.utcnow()
            db.commit()
            print('Updated existing user in backend/local.db')
        else:
            user = User(
                username=username,
                email='lambert@algo.com',
                mobile='9876543210',
                hashed_password=encryption_manager.hash_password(password),
                is_active=True,
                is_email_verified=True,
                is_mobile_verified=True,
                otp_code='123456',
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            print(f'Created user in backend/local.db id={user.id}')
    finally:
        db.close()

if __name__ == '__main__':
    upsert_user()
