from datetime import date, datetime
from typing import Optional

from sqlmodel import Field, SQLModel

# Canonical status values (match the seed dataset). The UI may relabel
# "In Use" as "Rented" for display, but the source of truth is here.
STATUS_AVAILABLE = "Available"
STATUS_IN_USE = "In Use"
STATUS_REPAIR = "Repair"
VALID_STATUSES = {STATUS_AVAILABLE, STATUS_IN_USE, STATUS_REPAIR}


class Hardware(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    brand: str = ""
    category: Optional[str] = None          # added per wireframe (not in seed)
    serial_number: Optional[str] = None     # added per wireframe (not in seed)
    purchase_date: Optional[date] = None
    status: str = STATUS_AVAILABLE
    notes: Optional[str] = None
    history: Optional[str] = None
    assigned_to: Optional[str] = None
    # Migration audit trail: ";"-joined flags raised during seed cleaning.
    audit_flags: str = ""
    # Invalid/unsafe records kept out of the active inventory but not deleted.
    quarantined: bool = False


class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(index=True, unique=True)
    name: str = ""
    hashed_password: str
    is_admin: bool = False


class Rental(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    hardware_id: int = Field(foreign_key="hardware.id")
    user_email: str
    started_at: datetime = Field(default_factory=datetime.utcnow)
    ended_at: Optional[datetime] = None


class AuditNote(SQLModel, table=True):
    """Admin's free-text comment on a flagged audit issue (one per hardware)."""

    id: Optional[int] = Field(default=None, primary_key=True)
    hardware_id: int = Field(foreign_key="hardware.id", unique=True)
    note: str = ""
    reviewed_at: datetime = Field(default_factory=datetime.utcnow)


class AuditAction(SQLModel, table=True):
    """History log of an AI-assisted fix: the admin's prompt + what happened."""

    id: Optional[int] = Field(default=None, primary_key=True)
    hardware_id: int = Field(foreign_key="hardware.id")
    prompt: str = ""
    summary: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)
