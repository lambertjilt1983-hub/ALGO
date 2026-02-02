import sys
from pathlib import Path
from dotenv import load_dotenv
from datetime import datetime

load_dotenv(Path('f:/ALGO/backend/.env.qa'))
sys.path.insert(0, 'f:/ALGO/backend')

from app.core.database import SessionLocal
from app.models.auth import User

db = SessionLocal()
try:
    user = db.query(User).filter(User.username == 'lambert').first()
    if user:
        user.is_admin = True
        user.is_email_verified = True
        user.is_mobile_verified = True
        user.updated_at = datetime.utcnow()
        db.commit()
        print('Updated lambert to admin')
    else:
        print('User lambert not found')
finally:
    db.close()
