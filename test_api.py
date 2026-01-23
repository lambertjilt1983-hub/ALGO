import requests
import json

# Login first
login_url = "http://localhost:8001/auth/login"
login_data = {"username": "test", "password": "test123"}

print("Logging in...")
response = requests.post(login_url, json=login_data)
if response.status_code != 200:
    print(f"Login failed: {response.text}")
    exit(1)

token_data = response.json()
token = token_data["access_token"]
print(f"✓ Login successful, token: {token[:20]}...")

# Get broker credentials
print("\nFetching broker credentials...")
headers = {"Authorization": f"Bearer {token}"}
brokers_url = "http://localhost:8001/brokers/credentials"
response = requests.get(brokers_url, headers=headers)
print(f"Status: {response.status_code}")
brokers_list = response.json()
print(f"Brokers: {json.dumps(brokers_list, indent=2)}")

# Get balance for each broker
print(f"\n✓ Found {len(brokers_list)} broker(s)")
for broker in brokers_list:
    print(f"\n  Broker ID: {broker['id']}, Name: {broker['broker_name']}")
    balance_url = f"http://localhost:8001/brokers/balance/{broker['id']}"
    balance_resp = requests.get(balance_url, headers=headers)
    print(f"  Balance response: {json.dumps(balance_resp.json(), indent=4)}")
