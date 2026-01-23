import requests
import json

# Test login
url = 'http://localhost:8000/auth/login'
data = {
    'username': 'test',
    'password': 'test123'
}

try:
    response = requests.post(url, json=data)
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.text}")
    if response.status_code == 200:
        print("\n✓ Login successful!")
        token = response.json().get('access_token')
        print(f"Token: {token[:50]}..." if token else "No token")
    else:
        print("\n✗ Login failed!")
except Exception as e:
    print(f"Error: {e}")
