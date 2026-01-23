"""Reset users and fix login issues"""
import sys
sys.path.insert(0, 'F:/ALGO/backend')

from app.core.database import SessionLocal
from app.models.auth import User
from app.core.security import encryption_manager

# Create fresh session
db = SessionLocal()

try:
    # Delete existing test user
    db.query(User).filter(User.username == 'test').delete()
    db.commit()
    print("✓ Deleted old test user")
    
    # Create new user with properly hashed password
    hashed_pw = encryption_manager.hash_password('test123')
    new_user = User(
        username='test',
        email='test@test.com',
        hashed_password=hashed_pw
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    print(f"✓ Created new user: {new_user.username} (ID: {new_user.id})")
    print(f"  Email: {new_user.email}")
    print(f"  Password: test123")
    
    # Verify password works
    is_valid = encryption_manager.verify_password('test123', new_user.hashed_password)
    print(f"  Password verification: {'✓ PASS' if is_valid else '✗ FAIL'}")
    
finally:
    db.close()
