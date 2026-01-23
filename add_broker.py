import requests
import webbrowser

# Register/Login
try:
    r = requests.post('http://localhost:8000/auth/register', 
                     json={'username':'trader','email':'trader@algo.com','password':'trader123'})
    print('User created')
except:
    print('User already exists')

# Login
login_resp = requests.post('http://localhost:8000/auth/login', 
                          json={'username':'trader','password':'trader123'})
token = login_resp.json()['access_token']
print(f'Logged in successfully')

# Add broker
broker_resp = requests.post('http://localhost:8000/brokers/credentials',
                           headers={'Authorization': f'Bearer {token}'},
                           json={
                               'broker_name': 'zerodha',
                               'api_key': '[REMOVED_ZERODHA_API_KEY]',
                               'api_secret': '[REMOVED_ZERODHA_API_SECRET]'
                           })

if broker_resp.status_code == 200:
    broker = broker_resp.json()
    print(f'Broker added successfully! ID: {broker["id"]}')
    
    # Get Zerodha login URL
    login_url_resp = requests.get(f'http://localhost:8000/brokers/zerodha/login/{broker["id"]}',
                                 headers={'Authorization': f'Bearer {token}'})
    
    if login_url_resp.status_code == 200:
        login_data = login_url_resp.json()
        print(f'\nZerodha Login URL: {login_data["login_url"]}')
        print('\nOpening Zerodha login in browser...')
        print('After logging in, you will be redirected back to the app.')
        webbrowser.open(login_data['login_url'])
    else:
        print(f'Error getting login URL: {login_url_resp.text}')
else:
    print(f'Error adding broker: {broker_resp.text}')

print('\nLogin with: username=trader, password=trader123')
print('Dashboard: http://localhost:3000')
