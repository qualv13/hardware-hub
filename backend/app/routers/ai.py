from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from ..ai.gemini import audit_inventory, semantic_search
from ..auth import get_current_user
from ..db import get_session
from ..models import AuditAction, Hardware
from ..schemas import HardwareOut, SearchIn

router = APIRouter(prefix="/api/ai", tags=["ai"])


def _items(session: Session) -> list[dict]:
    rows = session.exec(select(Hardware)).all()
    return [HardwareOut.model_validate(r).model_dump() for r in rows]


@router.post("/search", response_model=list[HardwareOut])
def search(data: SearchIn, session: Session = Depends(get_session), _user=Depends(get_current_user)):
    items = [i for i in _items(session) if not i["quarantined"]]
    ids = semantic_search(data.query, items)
    by_id = {i["id"]: i for i in items}
    return [by_id[i] for i in ids if i in by_id]


@router.get("/audit")
def audit(session: Session = Depends(get_session), _user=Depends(get_current_user)):
    issues = audit_inventory(_items(session))
    history: dict[int, list] = {}
    for a in session.exec(
        select(AuditAction).order_by(AuditAction.created_at.desc())
    ).all():
        history.setdefault(a.hardware_id, []).append(
            {"prompt": a.prompt, "summary": a.summary, "at": a.created_at.isoformat()}
        )
    for iss in issues:
        iss["history"] = history.get(iss["id"], [])
    return {"issues": issues}
