"""Auction service: lazy-close and shared logic."""
import csv
import io
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import List, Tuple

from sqlalchemy.orm import Session

from database import Auction


def _parse_ended_at(value: str) -> datetime | None:
    value = (value or "").strip()
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        pass
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(value[:19].replace("T", " "), fmt)
        except ValueError:
            continue
    return None


def parse_auctions_csv(content: str) -> List[Tuple[str, datetime | None, List[Tuple[str, Decimal]]]]:
    """
    Parse CSV: one row per auction. Columns name, ended_at, item_1_name, item_1_price, item_2_name, item_2_price, ...
    Returns list of (name, ended_at, [(item_name, opening_price), ...]).
    Empty item name or invalid price skips that item. Invalid ended_at yields None (caller may reject).
    """
    reader = csv.DictReader(io.StringIO(content))
    rows_out = []
    for row in reader:
        name = (row.get("name") or "").strip()
        ended_at_val = _parse_ended_at(row.get("ended_at") or "")
        items = []
        i = 1
        while True:
            iname = (row.get(f"item_{i}_name") or "").strip()
            iprice_str = (row.get(f"item_{i}_price") or "").strip()
            if not iname and not iprice_str:
                i += 1
                if i > 100:
                    break
                continue
            if not iname:
                i += 1
                continue
            try:
                price = Decimal(iprice_str) if iprice_str else Decimal("0")
                if price < 0:
                    continue
                items.append((iname, price))
            except (InvalidOperation, ValueError):
                pass
            i += 1
            if i > 100:
                break
        rows_out.append((name, ended_at_val, items))
    return rows_out


def ensure_auction_closed_if_ended(db: Session, auction: Auction) -> None:
    """
    If the auction has ended (now >= ended_at) and is still active,
    mark it ended and set each item's closing_price = current_bid.
    Idempotent: safe to call multiple times.
    """
    if auction.status != "active":
        return
    if auction.ended_at is None:
        return
    if datetime.utcnow() < auction.ended_at:
        return
    _close_auction(db, auction)


def end_auction_manually(db: Session, auction: Auction) -> None:
    """
    Manually end an auction regardless of scheduled end time.
    Sets each item's closing_price = current_bid.
    """
    if auction.status != "active":
        return
    _close_auction(db, auction)


def _close_auction(db: Session, auction: Auction) -> None:
    """Internal: close auction and save closing prices."""
    auction.status = "ended"
    for item in auction.items:
        item.closing_price = item.current_bid
    db.commit()
    db.refresh(auction)
