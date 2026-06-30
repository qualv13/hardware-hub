from typing import Optional

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from ..auth import get_current_user
from ..db import get_session
from ..models import Hardware
from ..schemas import HardwareOut

router = APIRouter(prefix="/api/hardware", tags=["hardware"])

_SORTABLE = {"name", "brand", "purchase_date", "status", "category"}


@router.get("", response_model=list[HardwareOut])
def list_hardware(
    status: Optional[str] = None,
    brand: Optional[str] = None,
    sort: str = "name",
    order: str = "asc",
    include_quarantined: bool = False,
    session: Session = Depends(get_session),
    _user=Depends(get_current_user),
):
    query = select(Hardware)
    if not include_quarantined:
        query = query.where(Hardware.quarantined == False)  # noqa: E712
    if status:
        query = query.where(Hardware.status == status)
    if brand:
        query = query.where(Hardware.brand == brand)

    items = session.exec(query).all()

    key = sort if sort in _SORTABLE else "name"
    # None values sort last regardless of direction.
    items.sort(
        key=lambda h: (getattr(h, key) is None, getattr(h, key) or ""),
        reverse=(order == "desc"),
    )
    return items
