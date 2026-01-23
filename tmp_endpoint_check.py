import requests

BASE = 'http://localhost:8002'
user = {'username': 'test', 'password': 'test123'}

r = requests.post(f'{BASE}/auth/login', json=user, timeout=10)
print('login', r.status_code, r.text)
r.raise_for_status()
token = r.json().get('access_token')
headers = {'Authorization': f'Bearer {token}'}

rc = requests.get(f'{BASE}/brokers/credentials', headers=headers, timeout=10)
print('brokers', rc.status_code, rc.text)

arm = requests.post(f'{BASE}/autotrade/arm', headers=headers, json={'armed': True}, timeout=10)
print('arm', arm.status_code, arm.text)

mode = requests.post(f'{BASE}/autotrade/mode', headers=headers, json={'demo_mode': False}, timeout=10)
print('mode', mode.status_code, mode.text)

mode_get = requests.get(f'{BASE}/autotrade/mode', headers=headers, timeout=10)
print('mode_get', mode_get.status_code, mode_get.text)

status = requests.get(f'{BASE}/autotrade/status', headers=headers, timeout=10)
print('status', status.status_code, status.text)

analyze = requests.post(f'{BASE}/autotrade/analyze', headers=headers, timeout=15)
print('analyze', analyze.status_code, analyze.text)
