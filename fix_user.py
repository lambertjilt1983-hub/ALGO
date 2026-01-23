import sys
sys.path.insert(0, 'F:/ALGO/backend')

from app.core.database import SessionLocal
from app.models.auth import User
from app.core.security import encryption_manager

db = SessionLocal()

try:
    # Delete old user
    db.query(User).filter(User.username == 'test').delete()
    db.commit()
    print("Deleted old user")
    
    # Create new user with correct password
    hashed = encryption_manager.hash_password('test123')
    user = User(username='test', email='test@test.com', hashed_password=hashed)
    db.add(user)
    db.commit()
    db.refresh(user)
    
    # Verify password works
    valid = encryption_manager.verify_password('test123', user.hashed_password)
    print(f"Created user: {user.username} (ID: {user.id})")
    print(f"Password 'test123' valid: {valid}")
    
finally:
    db.close()
