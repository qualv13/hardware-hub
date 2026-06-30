from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from ..ai.tools import run_fix
from ..auth import email_domain_allowed, hash_password, require_admin
from ..db import get_session
from ..models import (
    STATUS_AVAILABLE,
    STATUS_REPAIR,
    AuditAction,
    AuditNote,
    Hardware,
    Rental,
    User,
)
from ..schemas import AuditApplyIn, AuditFixIn, HardwareCreate, HardwareOut, UserCreate

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.post("/hardware", response_model=HardwareOut)
def add_hardware(
    data: HardwareCreate, session: Session = Depends(get_session), _admin=Depends(require_admin)
):
    hw = Hardware(
        **data.model_dump(),
        status=STATUS_AVAILABLE,
    )
    if hw.purchase_date is None:
        hw.purchase_date = date.today()
    session.add(hw)
    session.commit()
    session.refresh(hw)
    return hw


@router.delete("/hardware/{hid}")
def delete_hardware(
    hid: int, session: Session = Depends(get_session), _admin=Depends(require_admin)
):
    hw = session.get(Hardware, hid)
    if hw is None:
        raise HTTPException(404, "Hardware not found")
    # Delete related rentals first to avoid orphaned rows.
    rentals = session.exec(select(Rental).where(Rental.hardware_id == hid)).all()
    for rental in rentals:
        session.delete(rental)
    session.delete(hw)
    session.commit()
    return {"deleted": hid}


@router.patch("/hardware/{hid}/repair", response_model=HardwareOut)
def toggle_repair(
    hid: int, session: Session = Depends(get_session), _admin=Depends(require_admin)
):
    hw = session.get(Hardware, hid)
    if hw is None:
        raise HTTPException(404, "Hardware not found")
    hw.status = STATUS_AVAILABLE if hw.status == STATUS_REPAIR else STATUS_REPAIR
    session.add(hw)
    session.commit()
    session.refresh(hw)
    return hw


@router.post("/users")
def create_user(
    data: UserCreate, session: Session = Depends(get_session), _admin=Depends(require_admin)
):
    from ..config import settings as _settings
    email = data.email.lower()
    if not email_domain_allowed(email):
        domain = _settings.allowed_email_domain
        raise HTTPException(400, f"Only @{domain} accounts are allowed")
    if session.exec(select(User).where(User.email == email)).first():
        raise HTTPException(409, "A user with this email already exists")
    user = User(
        email=email,
        name=data.name,
        hashed_password=hash_password(data.password),
        is_admin=data.is_admin,
    )
    session.add(user)
    session.commit()
    return {"email": user.email, "is_admin": user.is_admin}


def _apply_safe_fixes(hw: Hardware) -> list[str]:
    """Apply the deterministic, safe fixes that the seed audit only *flagged*
    (currently: brand-typo correction). Mutates ``hw`` in place and returns a
    human-readable list of the changes made (empty if nothing was fixable)."""
    from ..seed.migrate import _BRAND_TYPOS

    changes: list[str] = []
    if hw.brand in _BRAND_TYPOS:
        corrected = _BRAND_TYPOS[hw.brand]
        flag = f"brand_typo_suspected({hw.brand}->{corrected})"
        hw.audit_flags = ";".join(
            f for f in hw.audit_flags.split(";") if f and f != flag
        )
        changes.append(f"brand: {hw.brand} -> {corrected}")
        hw.brand = corrected
    return changes


def _upsert_note(session: Session, hardware_id: int, note: str) -> None:
    note = (note or "").strip()
    if not note:
        return
    existing = session.exec(
        select(AuditNote).where(AuditNote.hardware_id == hardware_id)
    ).first()
    if existing:
        existing.note = note
        existing.reviewed_at = datetime.utcnow()
        session.add(existing)
    else:
        session.add(AuditNote(hardware_id=hardware_id, note=note))


@router.post("/audit/apply")
def apply_audit_fixes(
    session: Session = Depends(get_session), _admin=Depends(require_admin)
):
    """Bulk: apply every available safe fix across the inventory."""
    applied = []
    for hw in session.exec(select(Hardware)).all():
        changes = _apply_safe_fixes(hw)
        if changes:
            session.add(hw)
            applied.append({"id": hw.id, "name": hw.name, "changes": changes})
    session.commit()
    return {"count": len(applied), "applied": applied}


@router.post("/audit/apply/{hid}")
def apply_audit_fix_item(
    hid: int,
    data: AuditApplyIn,
    session: Session = Depends(get_session),
    _admin=Depends(require_admin),
):
    """Per-item: apply the available safe fix for ONE hardware row and persist
    the admin's free-text note about the proposed change."""
    hw = session.get(Hardware, hid)
    if hw is None:
        raise HTTPException(404, "Hardware not found")
    changes = _apply_safe_fixes(hw)
    session.add(hw)
    _upsert_note(session, hid, data.note or "")
    session.commit()
    session.refresh(hw)
    return {"id": hw.id, "name": hw.name, "changes": changes, "note": (data.note or "").strip()}


def _history_for(session: Session, hid: int) -> list[dict]:
    actions = session.exec(
        select(AuditAction)
        .where(AuditAction.hardware_id == hid)
        .order_by(AuditAction.created_at.desc())
    ).all()
    return [
        {"prompt": a.prompt, "summary": a.summary, "at": a.created_at.isoformat()}
        for a in actions
    ]


@router.post("/audit/fix/{hid}")
def fix_audit_item(
    hid: int,
    data: AuditFixIn,
    session: Session = Depends(get_session),
    _admin=Depends(require_admin),
):
    """Send the admin's natural-language prompt to the LLM, which calls the
    available tools to fix the flagged problem(s). The action is logged."""
    hw = session.get(Hardware, hid)
    if hw is None:
        raise HTTPException(404, "Hardware not found")
    changes, explanation = run_fix(hw, data.prompt or "")
    session.add(hw)
    summary = "; ".join(changes) if changes else "no change"
    session.add(
        AuditAction(hardware_id=hid, prompt=(data.prompt or "").strip(), summary=summary)
    )
    session.commit()
    session.refresh(hw)
    return {
        "id": hw.id,
        "name": hw.name,
        "changes": changes,
        "explanation": explanation,
        "history": _history_for(session, hid),
    }


@router.get("/history")
def audit_history(session: Session = Depends(get_session), _admin=Depends(require_admin)):
    """Full AI-fix history across the inventory (most recent first)."""
    actions = session.exec(
        select(AuditAction).order_by(AuditAction.created_at.desc())
    ).all()
    names = {h.id: h.name for h in session.exec(select(Hardware)).all()}
    return {
        "history": [
            {
                "hardware_id": a.hardware_id,
                "name": names.get(a.hardware_id, f"#{a.hardware_id}"),
                "prompt": a.prompt,
                "summary": a.summary,
                "at": a.created_at.isoformat(),
            }
            for a in actions
        ]
    }
