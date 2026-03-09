#!/usr/bin/env python3
"""Check for existing Zerodha BrokerCredential records."""
import sys
sys.path.insert(0, r'f:\ALGO\backend')
from app.core.database import SessionLocal
from app.models.auth import BrokerCredential

def main():
    s = SessionLocal()
    try:
        creds = s.query(BrokerCredential).filter(BrokerCredential.broker_name.ilike('%zerodha%')).all()
        if not creds:
            print('NO_ZERODHA_CREDENTIALS_FOUND')
            return
        for c in creds:
            print(f"ID: {c.id} USER_ID: {c.user_id} BROKER: {c.broker_name} ACTIVE: {c.is_active}")
    finally:
        s.close()

if __name__ == '__main__':
    main()
