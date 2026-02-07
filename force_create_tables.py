"""
Force-create all tables in algotrade.db using SQLAlchemy models.
"""

import sys
import os
os.environ['DATABASE_URL'] = 'sqlite:///./algotrade.db'  # Force SQLite usage
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'backend')))
from app.core.database import Base, engine

if __name__ == "__main__":
    print("[INFO] Creating all tables in algotrade.db ...")
    Base.metadata.create_all(bind=engine)
    print("[SUCCESS] All tables created (if not already present).")
