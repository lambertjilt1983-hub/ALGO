import sqlite3
import sys
sys.path.insert(0, 'F:/ALGO/backend')

from app.core.security import encryption_manager

# Check if test user exists (for demo purposes)
conn = sqlite3.connect('F:/ALGO/algotrade.db')
c = conn.cursor()
c.execute('SELECT id FROM users WHERE username = ?', ('test',))
user = c.fetchone()

if not user:
    print('   Creating demo user (test)...')
    hashed_pw = encryption_manager.hash_password('test123')
    c.execute('''INSERT INTO users (username, email, hashed_password, is_active, created_at) 
                 VALUES (?, ?, ?, ?, datetime("now"))''',
              ('test', 'test@test.com', hashed_pw, 1))
    user_id = c.lastrowid
    conn.commit()
    print(f'   [OK] Demo user created (ID: {user_id})')
    print('   [INFO] Login with: username=test, password=test123')
else:
    user_id = user[0]
    print(f'   [OK] Demo user exists (ID: {user_id})')

print('   [INFO] Database initialized successfully!')
print('   [INFO] Users can register via the UI or use demo account')

conn.close()
