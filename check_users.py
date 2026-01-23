import sqlite3
from passlib.context import CryptContext

# Initialize password context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Connect to database
conn = sqlite3.connect('F:/ALGO/algotrade.db')
c = conn.cursor()

# Get all users
c.execute('SELECT id, username, hashed_password FROM users')
users = c.fetchall()

print("Users in database:")
print("-" * 50)
for user in users:
    user_id, username, hashed_pw = user
    print(f"ID: {user_id}, Username: {username}")
    
    # Test password for 'test' user
    if username == 'test':
        is_valid = pwd_context.verify('test123', hashed_pw)
        print(f"  Password 'test123' valid: {is_valid}")

conn.close()
