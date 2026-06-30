from datetime import datetime, timedelta, timezone

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlmodel import Session, select

from .config import settings
from .db import get_session
from .models import User

_oauth2 = OAuth2PasswordBearer(tokenUrl="api/auth/login")


def email_domain_allowed(email: str) -> bool:
    """Return True if the email matches the configured allowed domain.

    If ``allowed_email_domain`` is empty, all emails are allowed.
    The check is case-insensitive.
    """
    domain = settings.allowed_email_domain.strip()
    if not domain:
        return True
    return email.lower().endswith(f"@{domain.lower()}")


def hash_password(p: str) -> str:
    # bcrypt only considers the first 72 bytes; truncate explicitly so long
    # inputs don't raise on bcrypt >= 4.1.
    return bcrypt.hashpw(p.encode("utf-8")[:72], bcrypt.gensalt()).decode("utf-8")


def verify_password(p: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(p.encode("utf-8")[:72], hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def create_token(email: str, is_admin: bool) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.access_token_expire_minutes
    )
    payload = {"sub": email, "is_admin": is_admin, "exp": expire}
    return jwt.encode(payload, settings.secret_key, algorithm="HS256")


def get_current_user(
    token: str = Depends(_oauth2),
    session: Session = Depends(get_session),
) -> User:
    cred_exc = HTTPException(
        status.HTTP_401_UNAUTHORIZED,
        "Invalid authentication credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
        email = payload.get("sub")
    except JWTError:
        raise cred_exc
    user = session.exec(select(User).where(User.email == email)).first()
    if user is None:
        raise cred_exc
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if not user.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin privileges required")
    return user
