from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime
from decimal import Decimal

class UserBase(BaseModel):
    name: str
    email: EmailStr
    role: str  # 'customer' or 'manager'

class UserCreate(UserBase):
    password: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserResponse(UserBase):
    id: int
    
    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: Optional[str] = None

class AuctionBase(BaseModel):
    name: str
    ended_at: Optional[datetime] = None

class AuctionCreate(AuctionBase):
    pass

class AuctionUpdate(BaseModel):
    name: Optional[str] = None
    ended_at: Optional[datetime] = None
    status: Optional[str] = None

class AuctionResponse(AuctionBase):
    id: int
    created_at: datetime
    created_by: int
    status: str
    creator: UserResponse
    is_registered: bool = False
    
    class Config:
        from_attributes = True

class AuctionRegistrationResponse(BaseModel):
    id: int
    user_id: int
    auction_id: int
    registered_at: datetime
    
    class Config:
        from_attributes = True

class AuctionItemBase(BaseModel):
    name: str
    opening_price: Decimal
    closing_price: Optional[Decimal] = Decimal('0')
    auction_id: int

class AuctionItemCreate(AuctionItemBase):
    pass

class AuctionItemUpdate(BaseModel):
    name: Optional[str] = None
    opening_price: Optional[Decimal] = None
    closing_price: Optional[Decimal] = None
    current_bid: Optional[Decimal] = None
    current_bidder_id: Optional[int] = None

class AuctionItemResponse(AuctionItemBase):
    id: int
    current_bid: Decimal
    current_bidder_id: Optional[int]
    auction: AuctionResponse
    
    class Config:
        from_attributes = True

class BidBase(BaseModel):
    item_id: int
    amount: Decimal

class BidCreate(BidBase):
    pass

class BidResponse(BidBase):
    id: int
    bidder_id: int
    created_at: datetime
    item: AuctionItemResponse
    bidder: UserResponse
    
    class Config:
        from_attributes = True

class AuctionDetailResponse(AuctionResponse):
    items: List[AuctionItemResponse]


class AuctionImportResult(BaseModel):
    created: int
    errors: List[str]