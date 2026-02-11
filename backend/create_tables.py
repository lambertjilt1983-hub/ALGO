from app.core.database import Base, engine

# Import all models so Base.metadata.create_all works for all tables
from app.models import auth
import logging
logging.basicConfig(level=logging.INFO)

logging.info('Creating all tables...')
Base.metadata.create_all(bind=engine)
logging.info('All tables created!')
