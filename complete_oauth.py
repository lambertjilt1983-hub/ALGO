import requests

# Complete OAuth with request token
request_token = "[REMOVED_REQUEST_TOKEN]"

response = requests.get(
    f'http://localhost:8000/brokers/zerodha/callback',
    params={
        'request_token': request_token,
        'status': 'success'
    }
)

print(f"Status Code: {response.status_code}")
print(f"Response: {response.text}")

if 'success' in response.url:
    print("\n✅ Zerodha authentication successful!")
    print("Your account is now connected with real market data.")
    print("\nRefresh your dashboard at: http://localhost:3000")
else:
    print(f"\n❌ Error: {response.text}")
