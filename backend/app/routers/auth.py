from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from ..auth import create_token, email_domain_allowed, get_current_user, verify_password
from ..db import get_session
from ..models import User
from ..schemas import LoginIn, TokenOut

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=TokenOut)
def login(data: LoginIn, session: Session = Depends(get_session)):
    from ..config import settings as _settings
    if not email_domain_allowed(data.email):
        domain = _settings.allowed_email_domain
        raise HTTPException(400, f"Only @{domain} accounts are allowed")
    user = session.exec(select(User).where(User.email == data.email)).first()
    if not user or not verify_password(data.password, user.hashed_password):
        raise HTTPException(401, "Invalid email or password")
    token = create_token(user.email, user.is_admin)
    return TokenOut(access_token=token, is_admin=user.is_admin, email=user.email)


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return {"email": user.email, "name": user.name, "is_admin": user.is_admin}
