import sqlite3
import os
from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey, Text, Numeric
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime

# Get absolute path to project data directory
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")

# Ensure data directory exists
os.makedirs(DATA_DIR, exist_ok=True)

# Absolute path to SQLite database
DB_PATH = os.path.join(DATA_DIR, "auction_house.db")
SQLALCHEMY_DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False, index=True)
    password = Column(String, nullable=False)
    role = Column(String, nullable=False)  # 'customer' or 'manager'
    
    created_auctions = relationship("Auction", back_populates="creator")
    bids = relationship("Bid", back_populates="bidder")
    current_bids = relationship("AuctionItem")
    registrations = relationship("AuctionRegistration", back_populates="user")
    
    def __repr__(self):
        return f"<User(id={self.id}, name='{self.name}', role='{self.role}')>"

class Auction(Base):
    __tablename__ = "auctions"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    ended_at = Column(DateTime, nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    status = Column(String, default="active")  # 'active', 'ended', 'cancelled'
    
    creator = relationship("User", back_populates="created_auctions")
    items = relationship("AuctionItem", back_populates="auction")
    registrations = relationship("AuctionRegistration", back_populates="auction")
    
    def __repr__(self):
        return f"<Auction(id={self.id}, name='{self.name}', status='{self.status}')>"

class AuctionItem(Base):
    __tablename__ = "auction_items"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    opening_price = Column(Numeric(10, 2), nullable=False)
    closing_price = Column(Numeric(10, 2), default=0)
    auction_id = Column(Integer, ForeignKey("auctions.id"), nullable=False)
    current_bid = Column(Numeric(10, 2), default=0)
    current_bidder_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    
    auction = relationship("Auction", back_populates="items")
    current_bidder = relationship("User", overlaps="current_bids")
    bids = relationship("Bid", back_populates="item")
    
    def __repr__(self):
        return f"<AuctionItem(id={self.id}, name='{self.name}', current_bid={self.current_bid})>"

class Bid(Base):
    __tablename__ = "bids"
    
    id = Column(Integer, primary_key=True, index=True)
    item_id = Column(Integer, ForeignKey("auction_items.id"), nullable=False)
    bidder_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    amount = Column(Numeric(10, 2), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    item = relationship("AuctionItem", back_populates="bids")
    bidder = relationship("User", back_populates="bids")
    
    def __repr__(self):
        return f"<Bid(id={self.id}, amount={self.amount}, item_id={self.item_id})>"

class AuctionRegistration(Base):
    __tablename__ = "auction_registrations"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    auction_id = Column(Integer, ForeignKey("auctions.id"), nullable=False)
    registered_at = Column(DateTime, default=datetime.utcnow)
    
    user = relationship("User", back_populates="registrations")
    auction = relationship("Auction", back_populates="registrations")
    
    def __repr__(self):
        return f"<AuctionRegistration(user_id={self.user_id}, auction_id={self.auction_id})>"

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def create_tables():
    Base.metadata.create_all(bind=engine)

if __name__ == "__main__":
    create_tables()
    print("Database tables created successfully!")