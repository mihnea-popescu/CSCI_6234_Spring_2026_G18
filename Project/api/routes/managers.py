import csv
import io
from decimal import Decimal

from fastapi import APIRouter, Body, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func
from typing import List, Optional

from database import get_db, User, Auction, AuctionItem, Bid
from schemas import AuctionResponse, AuctionCreate, AuctionUpdate, AuctionItemCreate, AuctionItemResponse, AuctionImportResult
from services.auction import ensure_auction_closed_if_ended, end_auction_manually, parse_auctions_csv
from services import auction as auction_service
import auth

router = APIRouter()

@router.get("/auctions", response_model=List[AuctionResponse])
async def get_auctions(
    current_user: User = Depends(auth.get_current_manager),
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
    return auctions

@router.get("/auctions/export")
async def export_auctions_csv(
    current_user: User = Depends(auth.get_current_manager),
    db: Session = Depends(get_db),
):
    query = (
        db.query(Auction)
        .options(joinedload(Auction.items))
        .order_by(Auction.id)
    )
    auctions = query.all()
    for a in auctions:
        ensure_auction_closed_if_ended(db, a)

    def row_gen():
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(["auction_id", "name", "status", "ended_at", "item_count", "total_bids", "revenue"])
        yield buffer.getvalue()
        for a in auctions:
            buffer = io.StringIO()
            writer = csv.writer(buffer)
            item_count = len(a.items)
            total_bids = db.query(func.count(Bid.id)).join(AuctionItem).filter(AuctionItem.auction_id == a.id).scalar() or 0
            revenue = sum(
                (item.closing_price if a.status == "ended" else item.current_bid) for item in a.items
            ) if a.items else Decimal("0")
            writer.writerow([
                a.id,
                a.name,
                a.status,
                a.ended_at.isoformat() if a.ended_at else "",
                item_count,
                total_bids,
                str(revenue),
            ])
            yield buffer.getvalue()

    return StreamingResponse(
        row_gen(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=auction_stats.csv"},
    )

@router.post("/auctions/import", response_model=AuctionImportResult)
async def import_auctions_csv(
    current_user: User = Depends(auth.get_current_manager),
    db: Session = Depends(get_db),
    file: UploadFile = File(...),
):
    content = (await file.read()).decode("utf-8", errors="replace")
    rows = parse_auctions_csv(content)
    created = 0
    errors = []
    for idx, (name, ended_at, items) in enumerate(rows):
        if not name:
            errors.append(f"Row {idx + 2}: missing name")
            continue
        if ended_at is None:
            errors.append(f"Row {idx + 2}: invalid or missing ended_at")
            continue
        if not items:
            errors.append(f"Row {idx + 2}: at least one item required")
            continue
        try:
            auction = Auction(
                name=name,
                ended_at=ended_at,
                created_by=current_user.id,
                status="active",
            )
            db.add(auction)
            db.flush()
            for item_name, opening_price in items:
                db.add(
                    AuctionItem(
                        name=item_name,
                        opening_price=opening_price,
                        closing_price=Decimal("0"),
                        auction_id=auction.id,
                    )
                )
            db.commit()
            created += 1
        except Exception as e:
            db.rollback()
            errors.append(f"Row {idx + 2}: {e!s}")
    return AuctionImportResult(created=created, errors=errors)

@router.post("/auctions", response_model=AuctionResponse)
async def create_auction(auction: AuctionCreate, current_user: User = Depends(auth.get_current_manager), db: Session = Depends(get_db)):
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

VALID_AUCTION_STATUSES = ("active", "ended", "cancelled")

@router.put("/auctions/{auction_id}", response_model=AuctionResponse)
async def update_auction(
    auction_id: int,
    body: AuctionUpdate = Body(...),
    current_user: User = Depends(auth.get_current_manager),
    db: Session = Depends(get_db),
):
    db_auction = (
        db.query(Auction)
        .options(joinedload(Auction.creator))
        .filter(Auction.id == auction_id)
        .first()
    )
    if not db_auction:
        raise HTTPException(status_code=404, detail="Auction not found")
    if body.name is not None:
        db_auction.name = body.name
    if body.ended_at is not None:
        db_auction.ended_at = body.ended_at
    if body.status is not None:
        if body.status not in VALID_AUCTION_STATUSES:
            raise HTTPException(
                status_code=400,
                detail=f"status must be one of: {', '.join(VALID_AUCTION_STATUSES)}",
            )
        db_auction.status = body.status
    db.commit()
    db.refresh(db_auction)
    return db_auction

@router.post("/auctions/{auction_id}/items", response_model=AuctionItemResponse)
async def add_item_to_auction(auction_id: int, item: AuctionItemCreate, current_user: User = Depends(auth.get_current_manager), db: Session = Depends(get_db)):
    auction = db.query(Auction).filter(Auction.id == auction_id).first()
    if not auction:
        raise HTTPException(status_code=404, detail="Auction not found")
    closing = item.closing_price if item.closing_price is not None else Decimal("0")
    db_item = AuctionItem(
        name=item.name,
        opening_price=item.opening_price,
        closing_price=closing,
        auction_id=auction_id,
        current_bid=Decimal("0"),
        current_bidder_id=None,
    )
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    db_item = (
        db.query(AuctionItem)
        .options(joinedload(AuctionItem.auction).joinedload(Auction.creator))
        .filter(AuctionItem.id == db_item.id)
        .one()
    )
    return db_item

@router.post("/auctions/{auction_id}/end", response_model=AuctionResponse)
async def end_auction(auction_id: int, current_user: User = Depends(auth.get_current_manager), db: Session = Depends(get_db)):
    auction = db.query(Auction).filter(Auction.id == auction_id).first()
    if not auction:
        raise HTTPException(status_code=404, detail="Auction not found")
    if auction.status == "ended":
        raise HTTPException(status_code=400, detail="Auction already ended")
    if auction.status == "cancelled":
        raise HTTPException(status_code=400, detail="Cannot end a cancelled auction")
    
    auction_service.end_auction_manually(db, auction)
    return auction