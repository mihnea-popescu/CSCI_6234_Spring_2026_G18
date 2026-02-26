from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional
from database import get_db, Auction, AuctionItem, Bid, User, AuctionRegistration
from schemas import AuctionResponse, AuctionDetailResponse, AuctionCreate, BidCreate, BidResponse, AuctionRegistrationResponse
from services.auction import ensure_auction_closed_if_ended
import auth

router = APIRouter()

@router.get("/get_auctions", response_model=List[AuctionResponse])
async def get_auctions(
    current_user: User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
    status_filter: Optional[str] = Query(None, alias="status"),
):
    query = (
        db.query(Auction)
        .options(joinedload(Auction.creator))
        .order_by(Auction.created_at.desc())
    )
    if status_filter and status_filter in ("active", "ended", "cancelled"):
        query = query.filter(Auction.status == status_filter)
    auctions = query.all()
    for a in auctions:
        ensure_auction_closed_if_ended(db, a)
    
    registered_ids = set(
        r.auction_id for r in db.query(AuctionRegistration).filter(
            AuctionRegistration.user_id == current_user.id
        ).all()
    )
    
    for a in auctions:
        a.is_registered = a.id in registered_ids
    
    return auctions

@router.post("/{auction_id}/register", response_model=AuctionRegistrationResponse)
async def register_for_auction(
    auction_id: int,
    current_user: User = Depends(auth.get_current_customer),
    db: Session = Depends(get_db),
):
    auction = db.query(Auction).filter(Auction.id == auction_id).first()
    if not auction:
        raise HTTPException(status_code=404, detail="Auction not found")
    
    existing = db.query(AuctionRegistration).filter(
        AuctionRegistration.user_id == current_user.id,
        AuctionRegistration.auction_id == auction_id,
    ).first()
    
    if existing:
        raise HTTPException(status_code=400, detail="Already registered for this auction")
    
    registration = AuctionRegistration(
        user_id=current_user.id,
        auction_id=auction_id,
    )
    db.add(registration)
    db.commit()
    db.refresh(registration)
    return registration

@router.get("/{auction_id}", response_model=AuctionDetailResponse)
async def get_auction(
    auction_id: int,
    current_user: User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    auction = (
        db.query(Auction)
        .options(
            joinedload(Auction.creator),
            joinedload(Auction.items),
        )
        .filter(Auction.id == auction_id)
        .first()
    )
    if not auction:
        raise HTTPException(status_code=404, detail="Auction not found")
    ensure_auction_closed_if_ended(db, auction)
    return auction

@router.post("/{auction_id}/bids", response_model=BidResponse)
async def place_bid(
    auction_id: int,
    body: BidCreate,
    current_user: User = Depends(auth.get_current_customer),
    db: Session = Depends(get_db),
):
    auction = (
        db.query(Auction)
        .options(joinedload(Auction.items))
        .filter(Auction.id == auction_id)
        .first()
    )
    if not auction:
        raise HTTPException(status_code=404, detail="Auction not found")
    ensure_auction_closed_if_ended(db, auction)
    if auction.status != "active":
        raise HTTPException(status_code=400, detail="Auction is not active")
    
    registration = db.query(AuctionRegistration).filter(
        AuctionRegistration.user_id == current_user.id,
        AuctionRegistration.auction_id == auction_id,
    ).first()
    if not registration:
        raise HTTPException(status_code=403, detail="You must register for this auction before bidding")
    
    item = db.query(AuctionItem).filter(
        AuctionItem.id == body.item_id,
        AuctionItem.auction_id == auction_id,
    ).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found in this auction")
    if body.amount <= item.current_bid:
        raise HTTPException(
            status_code=400,
            detail=f"Bid must be greater than current bid ({item.current_bid})",
        )
    if body.amount < item.opening_price:
        raise HTTPException(
            status_code=400,
            detail=f"Bid must be at least opening price ({item.opening_price})",
        )
    item.current_bid = body.amount
    item.current_bidder_id = current_user.id
    db_bid = Bid(
        item_id=body.item_id,
        bidder_id=current_user.id,
        amount=body.amount,
    )
    db.add(db_bid)
    db.commit()
    db.refresh(db_bid)
    db.refresh(item)
    bid = (
        db.query(Bid)
        .options(
            joinedload(Bid.item).joinedload(AuctionItem.auction).joinedload(Auction.creator),
            joinedload(Bid.bidder),
        )
        .filter(Bid.id == db_bid.id)
        .first()
    )
    return bid

@router.post("/", response_model=AuctionResponse)
async def create_auction(
    auction: AuctionCreate,
    current_user: User = Depends(auth.get_current_manager),
    db: Session = Depends(get_db),
):
    db_auction = Auction(
        name=auction.name,
        ended_at=auction.ended_at,
        created_by=current_user.id,
        status="active",
    )
    db.add(db_auction)
    db.commit()
    db.refresh(db_auction)
    db_auction.creator = current_user
    return db_auction

@router.put("/{auction_id}", response_model=AuctionResponse)
async def update_auction(
    auction_id: int,
    current_user: User = Depends(auth.get_current_manager),
    db: Session = Depends(get_db),
):
    # Placeholder: Update auction details
    return {"id": auction_id, "name": "Updated Auction", "status": "active"}

@router.post("/{auction_id}/end", response_model=AuctionResponse)
async def end_auction(
    auction_id: int,
    current_user: User = Depends(auth.get_current_manager),
    db: Session = Depends(get_db),
):
    # Placeholder: End auction and finalize sales
    return {"id": auction_id, "name": "Ended Auction", "status": "ended"}