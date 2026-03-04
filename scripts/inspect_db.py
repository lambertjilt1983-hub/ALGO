import sys
# ensure backend package is on path
sys.path.append("backend")
from app.core.config import get_settings
from app.core import database

settings = get_settings()
print("DATABASE_URL from settings=", settings.DATABASE_URL)
print("engine URL=", database.engine.url)
