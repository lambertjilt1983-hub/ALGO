#!/usr/bin/env python3
"""Add Zerodha broker credentials into the database (encrypted).

Usage:
  - Ensure `FERNET_KEY` is set in the environment (same key used by the app).
  - Run: `python backend/scripts/add_zerodha_credential.py`
"""
import sys
import getpass
import os

# Ensure backend package is importable when running from workspace root
sys.path.insert(0, r'f:\ALGO\backend')

from app.core.database import SessionLocal
from app.models.auth import BrokerCredential
from app.core.security import encryption_manager


def prompt(prompt_text, default=None):
    v = input(f"{prompt_text}{' [' + str(default) + ']' if default else ''}: ")
    if not v and default is not None:
        return default
    return v


def main():
    try:
        # Touch encryption manager to ensure FERNET_KEY is present
        _ = encryption_manager
    except Exception as e:
        print("FERNET_KEY is missing or invalid. Set FERNET_KEY in the environment before running this script.")
        print(str(e))
        return

    print("Add Zerodha Broker Credential")
    user_id = prompt("User ID (owner of credentials)", default="1")
    broker_name = prompt("Broker name", default="zerodha")
    api_key = prompt("Zerodha API Key (api_key)")
    api_secret = prompt("Zerodha API Secret (api_secret) - optional", default="")
    access_token = getpass.getpass("Zerodha Access Token (access_token, hidden): ")
    confirm = prompt("Store credential now? (yes/no)", default="yes")
    if confirm.lower() not in ("y", "yes"):
        print("Aborted by user.")
        return

    enc_api_key = encryption_manager.encrypt_credentials(api_key) if api_key else None
    enc_api_secret = encryption_manager.encrypt_credentials(api_secret) if api_secret else None
    enc_access_token = encryption_manager.encrypt_credentials(access_token) if access_token else None

    db = SessionLocal()
    try:
        cred = BrokerCredential(
            user_id=int(user_id),
            broker_name=broker_name,
            api_key=enc_api_key,
            api_secret=enc_api_secret,
            access_token=enc_access_token,
            is_active=True,
        )
        db.add(cred)
        db.commit()
        db.refresh(cred)
        print(f"Saved BrokerCredential id={cred.id} for user_id={cred.user_id} broker={cred.broker_name}")
    except Exception as e:
        db.rollback()
        print("Failed to save credential:", e)
    finally:
        db.close()


if __name__ == '__main__':
    main()
