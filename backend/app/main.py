import json
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlmodel import Session, select

from .auth import hash_password
from .config import settings
from .db import engine, init_db
from .models import User
from .routers import admin, ai, auth, hardware, rentals
from .seed.migrate import seed_if_empty


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    with Session(engine) as session:
        # Bootstrap the first admin. Afterwards, accounts are created ONLY
        # through the Admin Panel (no public self-registration).
        if not session.exec(select(User).where(User.email == settings.admin_email)).first():
            session.add(
                User(
                    email=settings.admin_email,
                    name="Admin",
                    hashed_password=hash_password(settings.admin_password),
                    is_admin=True,
                )
            )
            session.commit()

        report = seed_if_empty(session)
        if report:
            print("=== SEED AUDIT REPORT ===")
            print(json.dumps(report, indent=2, default=str))
            print("=========================")
    yield


app = FastAPI(title="Hardware Hub", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(hardware.router)
app.include_router(rentals.router)
app.include_router(admin.router)
app.include_router(ai.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}


# Serve the built Vue SPA if it exists (single-container production deploy).
_dist = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
if _dist.exists():
    app.mount("/", StaticFiles(directory=str(_dist), html=True), name="frontend")
