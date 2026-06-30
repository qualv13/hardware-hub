"""Development server runner.

Use this instead of a bare `uvicorn app.main:app --reload`. The SQLite database
lives inside the backend/ directory, so the plain `--reload` watcher restarts
the server on every DB write (and drops in-flight requests — the Vite proxy
then reports ECONNREFUSED). Here we keep auto-reload for code, but exclude the
database files from the watcher.

    python dev.py
"""

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
        reload_includes=["*.py"],
        reload_excludes=["*.db", "*.db-journal", "*.db-wal", "*.db-shm"],
    )
