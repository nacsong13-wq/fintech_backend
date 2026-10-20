from sqlalchemy import Column, Integer, String, Float, Boolean
from database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    nfc_card_id = Column(String, unique=True, index=True, nullable=True)
    balance = Column(Float, default=0.0)
    is_active = Column(Boolean, default=True)