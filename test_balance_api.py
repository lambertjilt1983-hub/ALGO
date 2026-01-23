import requests

# Login as test user
login_url = 'http://localhost:8000/auth/login'
login_data = {'username': 'test', 'password': 'test123'}

response = requests.post(login_url, json=login_data)
if response.status_code != 200:
    print(f"Login failed: {response.text}")
    exit(1)

token = response.json()['access_token']
print(f"Logged in as test user")

# Get broker balance
headers = {'Authorization': f'Bearer {token}'}
balance_url = 'http://localhost:8000/brokers/balance/4'

response = requests.get(balance_url, headers=headers)
print(f"\nBalance API Response:")
print(f"Status: {response.status_code}")

if response.status_code == 200:
    data = response.json()
    print(f"\nBroker ID: {data.get('broker_id')}")
    print(f"Broker Name: {data.get('broker_name')}")
    print(f"Available Balance: {data.get('available_balance')}")
    print(f"Data Source: {data.get('data_source')}")
    print(f"Error: {data.get('error', 'None')}")
    
    if data.get('data_source') == 'real_zerodha_api':
        print("\n✓ REAL DATA from Zerodha")
    else:
        print(f"\n⚠️ NOT REAL DATA - Source: {data.get('data_source')}")
else:
    print(f"Error: {response.text}")
