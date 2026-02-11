from app.main import app

import logging
logging.basicConfig(level=logging.INFO)
logging.info("Registered Routes:")
for route in app.routes:
    logging.info(f"  {route.path} - {route.methods if hasattr(route, 'methods') else 'N/A'}")
