from app.core.database import SessionLocal
from app.models.auth import BrokerCredential
from app.core.security import encryption_manager
import json

db = SessionLocal()
creds = db.query(BrokerCredential).filter(BrokerCredential.broker_name == 'zerodha').all()
print('found', len(creds))
for c in creds:
    try:
        api_key = encryption_manager.decrypt_credentials(c.api_key) if c.api_key else None
        api_secret = encryption_manager.decrypt_credentials(c.api_secret) if c.api_secret else None
        access = encryption_manager.decrypt_credentials(c.access_token) if c.access_token else None
        refresh = encryption_manager.decrypt_credentials(c.refresh_token) if c.refresh_token else None
    except Exception as e:
        print('decrypt error', c.id, type(e).__name__, e)
        print('raw', {'api_key': c.api_key, 'api_secret': c.api_secret, 'access_token': c.access_token, 'refresh_token': c.refresh_token})
        continue
    print(json.dumps({
        'id': c.id,
        'user_id': c.user_id,
        'api_key': api_key,
        'api_secret': api_secret,
        'access_token': access,
        'refresh_token': refresh,
    }, indent=2))
