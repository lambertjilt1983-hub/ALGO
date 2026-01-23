import requests

request_token = "[REMOVED_REQUEST_TOKEN]"

print(f"Exchanging request token: {request_token}")

# Call the backend callback endpoint
url = f"http://localhost:8000/brokers/zerodha/callback?request_token={request_token}&status=success"

try:
    response = requests.get(url, allow_redirects=False)
    print(f"Status Code: {response.status_code}")
    print(f"Headers: {dict(response.headers)}")
    
    if response.status_code in [301, 302, 303, 307, 308]:
        print(f"Redirect to: {response.headers.get('Location')}")
        print("\nChecking if token was saved...")
        
        # Check database
        import sqlite3
        conn = sqlite3.connect('F:/ALGO/algotrade.db')
        c = conn.cursor()
        c.execute('SELECT id, access_token FROM broker_credentials WHERE id = 4')
        broker = c.fetchone()
        
        if broker[1]:
            print(f"\n✓ SUCCESS! Access token saved: {broker[1][:30]}...")
        else:
            print("\n✗ FAILED: No access token in database")
        
        conn.close()
    else:
        print(f"Response: {response.text}")
        
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
