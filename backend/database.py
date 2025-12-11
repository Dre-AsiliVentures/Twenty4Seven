# backend/database.py
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import datetime
import os

# For Render, you would eventually use a Postgres URL. 
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./bot_data.db")

# Fix for some postgres URL prefixes (Render uses postgres://, SQLAlchemy needs postgresql://)
if SQLALCHEMY_DATABASE_URL.startswith("postgres://"):
    SQLALCHEMY_DATABASE_URL = SQLALCHEMY_DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(SQLALCHEMY_DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class Trade(Base):
    __tablename__ = "trades"
    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String)
    side = Column(String) # BUY or SELL
    price = Column(Float)
    quantity = Column(Float)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    strategy_status = Column(String) # e.g., "OPEN", "CLOSED"

class LogEntry(Base):
    __tablename__ = "logs"
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    level = Column(String)
    message = Column(String)

Base.metadata.create_all(bind=engine)