"""
Seed encrypted broker API credentials into the database.

Usage:
  # Run from repo root (ensures imports resolve)
  python -m backend.scripts.seed_broker_credentials --broker zerodha --user-id 1 \
      --api-key "$ZERODHA_API_KEY" --api-secret "$ZERODHA_API_SECRET"

Requirements:
  - ENCRYPTION_KEY and DATABASE_URL configured in environment (or defaults to local SQLite).
  - The target user must exist.
"""
import argparse
import os
import sys
from typing import Optional

# Allow module imports when executed as a script
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from backend.app.core.database import SessionLocal  # type: ignore
from backend.app.core.security import encryption_manager  # type: ignore
from backend.app.models.auth import User, BrokerCredential  # type: ignore


def upsert_credentials(user_id: int, broker_name: str, api_key: str, api_secret: str) -> None:
    session = SessionLocal()
    try:
        user = session.query(User).filter(User.id == user_id).first()
        if not user:
            raise SystemExit(f"User {user_id} not found. Create the user before seeding credentials.")

        encrypted_key = encryption_manager.encrypt_credentials(api_key)
        encrypted_secret = encryption_manager.encrypt_credentials(api_secret)

        credential = (
            session.query(BrokerCredential)
            .filter(BrokerCredential.user_id == user_id, BrokerCredential.broker_name == broker_name)
            .first()
        )

        if credential:
            credential.api_key = encrypted_key
            credential.api_secret = encrypted_secret
            session.add(credential)
            action = "updated"
        else:
            credential = BrokerCredential(
                user_id=user_id,
                broker_name=broker_name,
                api_key=encrypted_key,
                api_secret=encrypted_secret,
            )
            session.add(credential)
            action = "created"

        session.commit()
        session.refresh(credential)
        print(f"✅ {action.capitalize()} credentials for broker '{broker_name}' (id={credential.id}) for user {user_id}.")
    finally:
        session.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed encrypted broker credentials into the database")
    parser.add_argument("--user-id", type=int, required=True, help="Target user id that owns the credentials")
    parser.add_argument("--broker", type=str, required=True, help="Broker name (e.g., zerodha, upstox)")
    parser.add_argument("--api-key", type=str, default=os.getenv("ZERODHA_API_KEY"), help="Broker API key")
    parser.add_argument("--api-secret", type=str, default=os.getenv("ZERODHA_API_SECRET"), help="Broker API secret")
    args = parser.parse_args()

    missing = []
    if not args.api_key:
        missing.append("--api-key or ZERODHA_API_KEY")
    if not args.api_secret:
        missing.append("--api-secret or ZERODHA_API_SECRET")
    if missing:
        raise SystemExit(f"Missing required values: {', '.join(missing)}")

    return args


def main() -> None:
    args = parse_args()
    upsert_credentials(
        user_id=args.user_id,
        broker_name=args.broker,
        api_key=args.api_key,
        api_secret=args.api_secret,
    )


if __name__ == "__main__":
    main()
