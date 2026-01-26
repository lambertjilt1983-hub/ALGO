import os
from app.core.database import SessionLocal
from app.models.auth import User
from app.core.security import encryption_manager
from datetime import datetime, timedelta

# Ensure FERNET_KEY is set
fernet_key = os.environ.get('FERNET_KEY')
if not fernet_key:
    raise RuntimeError('FERNET_KEY is missing in environment variables')

username = "lambertjilt"
email = "lambertjilt1983@gmail.com"
mobile = "+919880609360"
password = "Password@123"
hashed_password = encryption_manager.hash_password(password)

db = SessionLocal()
user = db.query(User).filter(User.username == username).first()
if not user:
    user = User(
        username=username,
        email=email,
        mobile=mobile,
        hashed_password=hashed_password,
        is_active=True,
        is_admin=True,
        is_email_verified=True,
        is_mobile_verified=True,
        otp_code="988060",
        otp_expires_at=datetime.utcnow() + timedelta(minutes=10),
        last_otp_sent_at=datetime.utcnow(),
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    db.add(user)
    db.commit()
    print("User created.")
else:
    print("User already exists.")
db.close()
