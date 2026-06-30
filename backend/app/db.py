from sqlalchemy import event
from sqlmodel import Session, SQLModel, create_engine

from .config import settings

_is_sqlite = settings.database_url.startswith("sqlite")
_connect_args = {"check_same_thread": False} if _is_sqlite else {}
engine = create_engine(settings.database_url, echo=False, connect_args=_connect_args)

if _is_sqlite:
    # The SPA fires overlapping requests (audit + list + fix). With default
    # SQLite settings concurrent access raises "database is locked" (HTTP 500).
    # WAL allows readers alongside a writer; busy_timeout makes writers wait
    # for a lock instead of failing immediately.
    @event.listens_for(engine, "connect")
    def _sqlite_pragmas(dbapi_conn, _record):  # noqa: ANN001
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA busy_timeout=5000")
        cur.close()


def init_db() -> None:
    # Import models so they are registered on SQLModel.metadata before create_all.
    from . import models  # noqa: F401

    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session
