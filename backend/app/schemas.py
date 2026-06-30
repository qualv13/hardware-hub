from datetime import date
from typing import Optional

from pydantic import BaseModel


class LoginIn(BaseModel):
    email: str
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    is_admin: bool
    email: str


class HardwareOut(BaseModel):
    id: int
    name: str
    brand: str
    category: Optional[str] = None
    serial_number: Optional[str] = None
    purchase_date: Optional[date] = None
    status: str
    notes: Optional[str] = None
    history: Optional[str] = None
    assigned_to: Optional[str] = None
    audit_flags: str = ""
    quarantined: bool = False

    model_config = {"from_attributes": True}


class HardwareCreate(BaseModel):
    name: str
    brand: str = ""
    category: Optional[str] = None
    serial_number: Optional[str] = None
    purchase_date: Optional[date] = None


class UserCreate(BaseModel):
    email: str
    name: str = ""
    password: str
    is_admin: bool = False


class SearchIn(BaseModel):
    query: str


class AuditApplyIn(BaseModel):
    note: Optional[str] = None


class AuditFixIn(BaseModel):
    prompt: Optional[str] = None
