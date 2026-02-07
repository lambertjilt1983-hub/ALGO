from app.core.database import Base, engine

# Import all models so Base.metadata.create_all works for all tables
from app.models import auth

print('Creating all tables...')
Base.metadata.create_all(bind=engine)
print('All tables created!')
