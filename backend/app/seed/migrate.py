"""Seed audit & migration.

The provided seed dataset contains *deliberate* data-quality problems
(duplicate ids, a future purchase date, a DD-MM-YYYY date, a brand typo,
a record whose status contradicts its safety notes, an invalid status, an
empty brand). We do NOT load it blindly:

  * objective issues are normalised (date formats),
  * subjective issues are flagged but NOT silently rewritten (brand typos),
  * unsafe records are status-corrected (Available -> Repair when notes
    mention damage),
  * structurally invalid records are quarantined (kept, but excluded from
    the active inventory).

`audit_and_clean` returns the cleaned rows plus a human-readable report
that we print on startup and paste into the README (Data Strategy).
"""

import json
from datetime import date, datetime
from pathlib import Path

from ..models import (
    STATUS_AVAILABLE,
    STATUS_REPAIR,
    VALID_STATUSES,
    Hardware,
    Rental,
    STATUS_IN_USE,
)

SEED_PATH = Path(__file__).parent / "seed.json"

# Words in notes/history that mean a device must not be issued.
_DANGER = ["swelling", "liquid damage", "do not issue", "sticky", "cracked", "water damage"]

# Brand typos we only *flag* (correcting a name is a judgement call).
_BRAND_TYPOS = {"Appel": "Apple", "Samsng": "Samsung", "Microsft": "Microsoft"}


def load_seed() -> list[dict]:
    return json.loads(SEED_PATH.read_text(encoding="utf-8"))


def _parse_date(raw):
    if not raw:
        return None, ["missing_purchase_date"]
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%m/%d/%Y"):
        try:
            d = datetime.strptime(raw, fmt).date()
            flags = [] if fmt == "%Y-%m-%d" else [f"date_format_normalized({raw})"]
            return d, flags
        except ValueError:
            continue
    return None, [f"unparseable_date({raw})"]


def audit_and_clean(raw_records: list[dict]):
    cleaned: list[Hardware] = []
    report = {"total": len(raw_records), "ok": 0, "fixed": 0, "quarantined": 0, "items": []}
    seen_ids: set[int] = set()
    max_id = max([int(r.get("id") or 0) for r in raw_records] + [0])

    for r in raw_records:
        flags: list[str] = []

        rid = r.get("id")
        if rid is None:
            max_id += 1
            rid = max_id
            flags.append("missing_id_assigned")
        elif rid in seen_ids:
            max_id += 1
            flags.append(f"duplicate_id_reassigned({rid}->{max_id})")
            rid = max_id
        seen_ids.add(rid)

        brand = (r.get("brand") or "").strip()
        if not brand:
            flags.append("missing_brand")
        if brand in _BRAND_TYPOS:
            flags.append(f"brand_typo_suspected({brand}->{_BRAND_TYPOS[brand]})")

        pdate, dflags = _parse_date(r.get("purchaseDate"))
        flags += dflags
        if pdate and pdate > date.today():
            flags.append("future_purchase_date")

        status = (r.get("status") or "").strip()
        quarantined = False
        if status not in VALID_STATUSES:
            quarantined = True
            flags.append(f"invalid_status_quarantined({status or 'empty'})")

        # Safety override: never expose a damaged device as Available.
        blob = f"{r.get('notes', '')} {r.get('history', '')}".lower()
        if status == STATUS_AVAILABLE and any(k in blob for k in _DANGER):
            flags.append("status_overridden_safety(Available->Repair)")
            status = STATUS_REPAIR

        cleaned.append(
            Hardware(
                id=rid,
                name=r.get("name") or "Unnamed device",
                brand=brand,
                purchase_date=pdate,
                status=status if status in VALID_STATUSES else (status or "Unknown"),
                notes=r.get("notes"),
                history=r.get("history"),
                assigned_to=r.get("assignedTo"),
                audit_flags=";".join(flags),
                quarantined=quarantined,
            )
        )

        if quarantined:
            report["quarantined"] += 1
        elif flags:
            report["fixed"] += 1
        else:
            report["ok"] += 1
        report["items"].append({"id": rid, "name": r.get("name"), "flags": flags})

    return cleaned, report


def seed_if_empty(session):
    """Populate the DB from the audited seed, but only if it's empty."""
    from sqlmodel import select

    if session.exec(select(Hardware)).first() is not None:
        return None

    cleaned, report = audit_and_clean(load_seed())
    for hw in cleaned:
        session.add(hw)
    session.commit()

    # Re-create the active rental implied by `assignedTo` in the seed.
    for hw in cleaned:
        if hw.assigned_to and hw.status == STATUS_IN_USE and not hw.quarantined:
            session.add(Rental(hardware_id=hw.id, user_email=hw.assigned_to))
    session.commit()
    return report
