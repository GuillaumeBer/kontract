import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from dotenv import load_dotenv

from data.models import Base, Collection, Skin, Price, UserAlert, Opportunity, TradeupBasket, BasketItem, PandL

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./kontract.db")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db() -> None:
    Base.metadata.create_all(bind=engine)


def get_session() -> Session:
    return SessionLocal()


# Redis client — optional, gracefully disabled if not available
try:
    import redis as redis_lib

    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    _redis_client = redis_lib.from_url(REDIS_URL, decode_responses=True)
    _redis_client.ping()
    redis_client = _redis_client
except Exception:
    redis_client = None  # Redis non disponible — fonctionne sans cache
