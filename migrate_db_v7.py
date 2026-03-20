
from data.database import engine
from data.models import Base
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def migrate():
    logger.info("Migrating database v7 (Adding Basket tables)...")
    # This will only create missing tables
    Base.metadata.create_all(engine)
    logger.info("Migration v7 terminée.")

if __name__ == "__main__":
    migrate()
