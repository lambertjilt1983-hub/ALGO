"""
Test token exchange flow
Simulates what happens when user completes Zerodha OAuth
"""
import requests
import json

# Login to get JWT token
login_response = requests.post('http://localhost:8001/auth/login', json={
    'username': 'test',
    'password': 'test123'
})

if login_response.status_code == 200:
    jwt_token = login_response.json()['access_token']
    print(f"✅ Login successful! JWT Token: {jwt_token[:30]}...")
    
    # Test the callback endpoint with a dummy request_token
    # In real scenario, this comes from Zerodha redirect
    test_request_token = "YOUR_REQUEST_TOKEN_HERE"
    
    callback_response = requests.get(
        f'http://localhost:8001/brokers/zerodha/callback?request_token={test_request_token}&status=success',
        headers={
            'Authorization': f'Bearer {jwt_token}',
            'Content-Type': 'application/json'
        }
    )
    
    print(f"\n📥 Callback Response Status: {callback_response.status_code}")
    print(f"📄 Response Data:")
    try:
        data = callback_response.json()
        print(json.dumps(data, indent=2))
        
        if data.get('status') == 'success':
            print("\n✅ TOKEN EXCHANGE SUCCESSFUL!")
            print(f"🎯 Broker ID: {data.get('broker_id')}")
            
            # Verify token was saved by checking balance
            broker_id = data.get('broker_id')
            balance_response = requests.get(
                f'http://localhost:8001/brokers/balance/{broker_id}',
                headers={'Authorization': f'Bearer {jwt_token}'}
            )
            
            print(f"\n📊 Balance Check:")
            print(json.dumps(balance_response.json(), indent=2))
        else:
            print("\n❌ Token exchange failed!")
            print(f"Error: {data.get('message')}")
    except:
        print(callback_response.text)
else:
    print(f"❌ Login failed: {login_response.status_code}")
    print(login_response.text)
