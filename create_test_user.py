import requests
import json

# Create test user via API
url = 'http://localhost:8000/auth/register'
data = {
    'username': 'test',
    'email': 'test@test.com',
    'password': 'test123'
}

print("Creating test user...")
try:
    response = requests.post(url, json=data)
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.text}")
    
    if response.status_code == 200:
        print("\n✓ User created successfully!")
        result = response.json()
        print(f"User ID: {result.get('id')}")
        print(f"Username: {result.get('username')}")
    else:
        print("\n✗ User creation failed!")
except Exception as e:
    print(f"Error: {e}")
