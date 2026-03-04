import json, urllib.request

login_url = 'http://localhost:8000/auth/login'
active_url = 'http://localhost:8000/autotrade/trades/active'

login_payload = json.dumps({'username':'admin','password':'admin123'}).encode('utf-8')
req = urllib.request.Request(login_url, data=login_payload, headers={'Content-Type':'application/json'})
with urllib.request.urlopen(req) as resp:
    data = json.load(resp)
    token = data.get('access_token')
    print('Got token:', bool(token))

req2 = urllib.request.Request(active_url, headers={'Authorization': f'Bearer {token}'})
with urllib.request.urlopen(req2) as resp:
    data2 = json.load(resp)
    print(json.dumps(data2, indent=2))
