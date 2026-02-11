import requests

def arm_live_trading(api_url, token):
    url = f"{api_url}/autotrade/arm"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    response = requests.post(url, json=True, headers=headers)
        import logging
        logging.basicConfig(level=logging.INFO)
        logging.info("Status: %s", response.status_code)
        logging.info("Response: %s", response.json())

if __name__ == "__main__":
    # Update these values as needed
    API_URL = "http://localhost:8000"
    ACCESS_TOKEN = input("Enter your JWT access token: ")
    arm_live_trading(API_URL, ACCESS_TOKEN)
