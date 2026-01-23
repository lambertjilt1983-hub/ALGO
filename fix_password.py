import sqlite3
import sys
sys.path.insert(0, 'F:/ALGO/backend')

from app.core.security import encryption_manager

# Connect to database
conn = sqlite3.connect('F:/ALGO/algotrade.db')
c = conn.cursor()

# Get test user
c.execute('SELECT id, username, hashed_password FROM users WHERE username = ?', ('test',))
user = c.fetchone()

if user:
    user_id, username, hashed_pw = user
    print(f"User found: ID={user_id}, Username={username}")
    print(f"Hashed password: {hashed_pw[:50]}...")
    
    # Test password verification
    test_password = 'test123'
    is_valid = encryption_manager.verify_password(test_password, hashed_pw)
    print(f"\nPassword '{test_password}' is valid: {is_valid}")
    
    if not is_valid:
        print("\n⚠️ Password verification failed!")
        print("This might be because the password was hashed with a different method.")
        print("\nRehashing password with current encryption manager...")
        
        # Rehash the password
        new_hash = encryption_manager.hash_password(test_password)
        print(f"New hash: {new_hash[:50]}...")
        
        # Update database
        c.execute('UPDATE users SET hashed_password = ? WHERE id = ?', (new_hash, user_id))
        conn.commit()
        print("✓ Password updated in database")
        
        # Verify again
        is_valid_now = encryption_manager.verify_password(test_password, new_hash)
        print(f"Verification after rehash: {is_valid_now}")
else:
    print("❌ Test user not found!")

conn.close()
