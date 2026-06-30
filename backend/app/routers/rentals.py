from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from ..auth import get_current_user
from ..db import get_session
from ..models import (
    STATUS_AVAILABLE,
    STATUS_IN_USE,
    STATUS_REPAIR,
    Hardware,
    Rental,
)
from ..schemas import HardwareOut

router = APIRouter(prefix="/api", tags=["rentals"])


@router.post("/hardware/{hid}/rent", response_model=HardwareOut)
def rent(hid: int, session: Session = Depends(get_session), user=Depends(get_current_user)):
    hw = session.get(Hardware, hid)
    if hw is None or hw.quarantined:
        raise HTTPException(404, "Hardware not found")

    # --- Core guards: prevent impossible states ---------------------------- #
    if hw.status == STATUS_REPAIR:
        raise HTTPException(409, "Cannot rent hardware that is in repair")
    if hw.status != STATUS_AVAILABLE:
        raise HTTPException(409, f"Cannot rent hardware with status '{hw.status}'")

    hw.status = STATUS_IN_USE
    hw.assigned_to = user.email
    session.add(hw)
    session.add(Rental(hardware_id=hw.id, user_email=user.email))
    session.commit()
    session.refresh(hw)
    return hw


@router.post("/hardware/{hid}/return", response_model=HardwareOut)
def return_hardware(
    hid: int, session: Session = Depends(get_session), user=Depends(get_current_user)
):
    hw = session.get(Hardware, hid)
    if hw is None:
        raise HTTPException(404, "Hardware not found")
    if hw.status != STATUS_IN_USE:
        raise HTTPException(409, "Cannot return hardware that is not in use")

    rental = session.exec(
        select(Rental).where(Rental.hardware_id == hid, Rental.ended_at == None)  # noqa: E711
    ).first()
    if rental is None:
        raise HTTPException(409, "No active rental found for this hardware")
    if rental.user_email != user.email and not user.is_admin:
        raise HTTPException(403, "You can only return hardware you rented")

    rental.ended_at = datetime.utcnow()
    hw.status = STATUS_AVAILABLE
    hw.assigned_to = None
    session.add(rental)
    session.add(hw)
    session.commit()
    session.refresh(hw)
    return hw


@router.get("/rentals/mine", response_model=list[HardwareOut])
def my_rentals(session: Session = Depends(get_session), user=Depends(get_current_user)):
    rentals = session.exec(
        select(Rental).where(Rental.user_email == user.email, Rental.ended_at == None)  # noqa: E711
    ).all()
    ids = [r.hardware_id for r in rentals]
    if not ids:
        return []
    return session.exec(select(Hardware).where(Hardware.id.in_(ids))).all()
