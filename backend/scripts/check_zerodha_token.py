import os
from dotenv import load_dotenv
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '../.env.qa'))

import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app.models.auth import BrokerCredential
from app.core.token_manager import TokenManager
from app.core.database import SessionLocal

# Print latest Zerodha credential
if __name__ == "__main__":
    db = SessionLocal()
    cred = db.query(BrokerCredential).filter(
        BrokerCredential.broker_name == 'zerodha',
        BrokerCredential.is_active == True
    ).order_by(BrokerCredential.id.desc()).first()
    if not cred:
           import logging
           logging.basicConfig(level=logging.INFO)
           logging.warning("No Zerodha credential found.")
    else:
           import logging
           logging.basicConfig(level=logging.INFO)
           logging.info(f"API Key: {cred.api_key}")
           logging.info(f"Access Token: {cred.access_token}")
           logging.info(f"Token Expiry: {cred.token_expiry}")
           logging.info(f"Active: {cred.is_active}")
        # Validate token
        valid = TokenManager.validate_zerodha_token(cred)
           logging.info(f"Token Valid: {valid}")
    db.close()
