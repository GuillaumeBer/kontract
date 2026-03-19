from datetime import datetime
from sqlalchemy import (
    Column, String, Boolean, Float, Integer, DateTime,
    ForeignKey, Text, UniqueConstraint
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class Collection(Base):
    __tablename__ = "collections"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    release_date = Column(String, nullable=True)
    active = Column(Boolean, default=True)

    skins = relationship("Skin", back_populates="collection")


class Skin(Base):
    __tablename__ = "skins"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    weapon = Column(String, nullable=True)
    collection_id = Column(String, ForeignKey("collections.id"), nullable=True)
    rarity_id = Column(String, nullable=False)
    rarity_name = Column(String, nullable=True)
    float_min = Column(Float, nullable=True)
    float_max = Column(Float, nullable=True)
    stattrak = Column(Boolean, default=False)
    market_hash_name = Column(String, nullable=True)

    collection = relationship("Collection", back_populates="skins")
    prices = relationship("Price", back_populates="skin")


class TradeupPool(Base):
    __tablename__ = "tradeup_pool"

    id = Column(Integer, primary_key=True, autoincrement=True)
    input_skin_id = Column(String, ForeignKey("skins.id"), nullable=False)
    output_skin_id = Column(String, ForeignKey("skins.id"), nullable=False)
    collection_id = Column(String, ForeignKey("collections.id"), nullable=False)

    __table_args__ = (
        UniqueConstraint("input_skin_id", "output_skin_id", "collection_id"),
    )


class Price(Base):
    __tablename__ = "prices"

    id = Column(Integer, primary_key=True, autoincrement=True)
    skin_id = Column(String, ForeignKey("skins.id"), nullable=False)
    platform = Column(String, nullable=False)  # "skinport" | "steam"
    buy_price = Column(Float, nullable=True)
    sell_price = Column(Float, nullable=True)
    volume_24h = Column(Float, nullable=True)
    volume_7d  = Column(Float, nullable=True)
    volume_30d = Column(Float, nullable=True)
    quantity   = Column(Integer, nullable=True)  # unités disponibles sur Skinport
    median_24h = Column(Float, nullable=True)
    median_7d  = Column(Float, nullable=True)
    median_30d = Column(Float, nullable=True)
    median_90d = Column(Float, nullable=True)
    avg_24h    = Column(Float, nullable=True)
    avg_7d     = Column(Float, nullable=True)
    avg_30d    = Column(Float, nullable=True)
    avg_90d    = Column(Float, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    skin = relationship("Skin", back_populates="prices")

    __table_args__ = (
        UniqueConstraint("skin_id", "platform"),
    )


class UserAlert(Base):
    __tablename__ = "user_alerts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, nullable=False, unique=True)  # Telegram chat_id
    min_roi = Column(Float, default=10.0)
    max_budget = Column(Float, default=100.0)
    max_pool_size = Column(Integer, default=5)
    min_liquidity = Column(Float, default=3.0)
    source_buy = Column(String, default="skinport")   # "skinport" | "steam"
    source_sell = Column(String, default="skinport")
    active = Column(Boolean, default=True)


class Opportunity(Base):
    __tablename__ = "opportunities"

    id = Column(Integer, primary_key=True, autoincrement=True)
    combo_hash = Column(String, nullable=False, index=True)
    inputs_json = Column(Text, nullable=False)   # JSON list of input skin ids
    ev_nette = Column(Float, nullable=False)
    roi = Column(Float, nullable=False)
    pool_size = Column(Integer, nullable=False)
    liquidity_score = Column(Float, nullable=True)
    price_reliability = Column(String, nullable=True)   # "high" | "medium" | "low"
    cv_pond = Column(Float, nullable=True)
    win_prob = Column(Float, nullable=True)
    kontract_score = Column(Float, nullable=True)
    floor_ratio = Column(Float, nullable=True)
    input_liquidity_status = Column(String, nullable=True)  # "liquid" | "partial" | "scarce"
    created_at = Column(DateTime, default=datetime.utcnow)
