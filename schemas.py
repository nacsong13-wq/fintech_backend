from pydantic import BaseModel, EmailStr
from typing import Optional

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    nfc_card_id: Optional[str] = None

class UserResponse(BaseModel):
    id: int
    email: EmailStr
    nfc_card_id: Optional[str] = None
    balance: float
    is_active: bool

    class Config:
        from_attributes = True