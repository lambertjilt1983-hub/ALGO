import requests
import json

# Login
login_resp = requests.post('http://localhost:8000/auth/login', 
                          json={'username':'trader','password':'trader123'})
token = login_resp.json()['access_token']
print(f'✓ Logged in')

# Get brokers
brokers_resp = requests.get('http://localhost:8000/brokers/credentials',
                           headers={'Authorization': f'Bearer {token}'})
brokers = brokers_resp.json()

print(f'\n📊 Total brokers: {len(brokers)}')
for broker in brokers:
    print(f'\n  Broker ID: {broker["id"]}')
    print(f'  Name: {broker["broker_name"]}')
    print(f'  Has Access Token: {"✓ YES" if broker.get("access_token") else "✗ NO"}')
    
    # Get balance for this broker
    balance_resp = requests.get(f'http://localhost:8000/brokers/balance/{broker["id"]}',
                               headers={'Authorization': f'Bearer {token}'})
    balance = balance_resp.json()
    
    print(f'\n  Balance Info:')
    print(f'    Available: ₹{balance.get("available_balance", 0):,.2f}')
    print(f'    Total: ₹{balance.get("total_balance", 0):,.2f}')
    print(f'    Data Source: {balance.get("data_source", "unknown")}')
    if balance.get("error"):
        print(f'    Error: {balance.get("error")}')

print('\n' + '='*60)
if any(b.get('data_source') == 'real_zerodha_api' for b in [requests.get(f'http://localhost:8000/brokers/balance/{b["id"]}', headers={'Authorization': f'Bearer {token}'}).json() for b in brokers]):
    print('✅ REAL DATA - Zerodha API connected!')
else:
    print('⚠️  DEMO DATA - No real Zerodha connection yet')
print('='*60)
