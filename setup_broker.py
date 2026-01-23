import requests
import json

# Login first
login_url = 'http://localhost:8000/auth/login'
login_data = {
    'username': 'test',
    'password': 'test123'
}

print("1. Logging in...")
response = requests.post(login_url, json=login_data)
token = response.json()['access_token']
print(f"✓ Got token: {token[:30]}...")

# Add Zerodha broker
broker_url = 'http://localhost:8000/brokers/credentials'
headers = {
    'Authorization': f'Bearer {token}',
    'Content-Type': 'application/json'
}
broker_data = {
    'broker_name': 'zerodha',
    'api_key': '[REMOVED_ZERODHA_API_KEY]',
    'api_secret': '[REMOVED_ZERODHA_API_SECRET]'
}

print("\n2. Adding Zerodha broker...")
response = requests.post(broker_url, json=broker_data, headers=headers)
print(f"Status: {response.status_code}")
print(f"Response: {response.text}")

if response.status_code == 200:
    result = response.json()
    broker_id = result.get('id')
    print(f"\n✓ Broker created with ID: {broker_id}")
    
    # Get login URL
    print("\n3. Getting Zerodha login URL...")
    login_url = f'http://localhost:8000/brokers/{broker_id}/zerodha/login'
    response = requests.get(login_url, headers=headers)
    if response.status_code == 200:
        auth_url = response.json().get('login_url')
        print(f"✓ Login URL: {auth_url[:100]}...")
        print("\n📋 Next step: Open this URL in browser to authorize Zerodha")
else:
    print(f"\n✗ Failed: {response.text}")
