import sys
sys.path.insert(0, 'F:/ALGO/backend')

from app.core.database import get_db
from app.models.auth import BrokerCredential
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Setup database session
DATABASE_URL = "sqlite:///F:/ALGO/algotrade.db"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
db = SessionLocal()

# Query broker 4
broker = db.query(BrokerCredential).filter(BrokerCredential.id == 4).first()

print(f"Broker ID: {broker.id}")
print(f"User ID: {broker.user_id}")
print(f"Broker Name: {broker.broker_name}")
print(f"API Key (encrypted): {broker.api_key[:30]}...")
print(f"API Secret (encrypted): {broker.api_secret[:30]}...")
print(f"Access Token: {broker.access_token}")
print(f"Token is None: {broker.access_token is None}")
print(f"Token == None: {broker.access_token == None}")
print(f"not Token: {not broker.access_token}")

db.close()
