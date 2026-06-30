# Hardware Hub 📦

An AI-native internal tool for managing, renting and maintaining company
hardware. Built for the Booksy *AI-Native Hardware Hub* assessment.

- **Backend:** Python · FastAPI · SQLModel · SQLite
- **Frontend:** Vue 3 · Vite · Pinia · Vue Router (with custom animated UI components — Vue ports of [React Bits](https://reactbits.dev) effects)
- **AI:** Google Gemini via the `google-genai` SDK (Semantic Search, Inventory Auditor, and tool-calling fixes), with deterministic fallbacks. Default model `gemini-2.5-flash` — a free-tier model that supports custom function calling (alternatives: `gemini-2.5-flash-lite`, `gemini-3-flash-preview`). Run `python list_models.py` to list models your key can use.
- **Auth:** JWT; accounts are created **only** by an admin (no self-registration)

---

## Quick start

### Run with Docker (recommended — single origin, no proxy)
The most reliable way to run everything together. One container builds the Vue
SPA and serves it together with the API on a single port, so there is **no dev
proxy and no localhost communication conflicts**.
```bash
cp .env.example .env          # optional: add your GEMINI_API_KEY
docker compose up --build     # http://localhost:8000  (login admin / admin123)
```
The SQLite DB is persisted in a named volume (`hub_data`). Stop with
`docker compose down` (add `-v` to also wipe the DB).

> Local dev with two servers (Vite + uvicorn) works too (below), but on some
> Windows setups the Vite dev-proxy intermittently fails to reach uvicorn on
> localhost. Docker (or the single-server build) sidesteps that entirely.

### Backend (local dev)
```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate   |   macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # optional; sensible defaults otherwise
uvicorn app.main:app --reload # http://localhost:8000  (docs at /docs)
```
On first start the DB is created, an admin is bootstrapped
(`admin@booksy.com` / `admin123`), and the seed is audited & loaded — the
**audit report is printed to the console**.

### Frontend
```bash
cd frontend
npm install
npm run dev                   # http://localhost:5173 (proxies /api -> :8000)
```

### Tests
```bash
cd backend
pytest                        # 10 tests (incl. the 3 required critical ones)
```

### Default login
`admin@booksy.com` / `admin123` (change via `.env`). A non-admin user
`j.doe@booksy.com` exists in the seed as a rental holder but has no password —
create real users from the Admin Panel.

---

## ⭐ Data Strategy — auditing the (deliberately broken) seed

The provided seed contains intentional data-quality problems. We do **not**
ingest it blindly; [`backend/app/seed/migrate.py`](backend/app/seed/migrate.py)
audits every record and emits a report. Philosophy: **normalise objective
issues, flag subjective ones, never fabricate, and never expose unsafe gear.**

Result on the provided seed: **5 clean · 5 repaired · 1 quarantined**

| # | Issue detected | Action taken |
|---|----------------|--------------|
| 5 | `Available` but notes say *"battery swelling, do not issue"* | **Forced to `Repair`** (safety override) |
| 6 | `purchaseDate` 2027-10-10 (future) | Loaded, **flagged** `future_purchase_date` |
| 4 (dup) | Duplicate `id: 4` (Lenovo) | **ID reassigned → 12** (both rows kept) |
| 9 | Brand `"Appel"`; date `"22-05-2023"` | Date **normalised → ISO**; typo **flagged** (not auto-rewritten) |
| 10 | Empty brand, null date, status `"Unknown"` | **Quarantined** (kept, excluded from active inventory) |
| 11 | `Available` but history says *"liquid damage"* | **Forced to `Repair`** (safety override) |
| 8 | Missing id in sequence | Ignored (ids need not be contiguous) |

Decisions worth noting:
- **Safety > declared status.** A device described as damaged is never rentable.
- **Flag, don't fabricate.** `Appel → Apple` is *suspected* and surfaced, but
  the original value is preserved — silently rewriting data hides problems.
- **Quarantine, don't delete.** Invalid records stay visible to admins
  (`?include_quarantined=true`) so a human can fix them.
- The same logic powers the **Inventory Auditor** fallback when no AI key is set.

---

## Architecture

```
backend/app
├─ main.py            # app factory, lifespan: init DB, bootstrap admin, seed
├─ models.py          # Hardware / User / Rental (SQLModel)
├─ auth.py            # bcrypt + JWT, get_current_user / require_admin
├─ routers/           # auth, hardware, rentals, admin, ai
├─ ai/gemini.py       # Gemini wrapper (search + audit) + fallbacks
└─ seed/migrate.py    # ⭐ audit & clean the seed
frontend/src
├─ views/             # Login, HardwareList, MyRentals, AdminPanel
├─ components/        # Sidebar, StatusBadge
└─ stores/auth.js     # Pinia auth state
```

**State machine (rental guards):** `Available → In Use` (rent),
`In Use → Available` (return), `* ↔ Repair` (admin). Illegal transitions
return `409`: renting non-available or in-repair gear, returning gear that
isn't in use, or returning someone else's rental.

---

## AI layer

- **Semantic Search** (`POST /api/ai/search`) — the *"Ask AI…"* bar. Sends the
  catalogue + query to Gemini, gets back ranked ids. Fallback: keyword match.
- **Inventory Auditor** (`GET /api/ai/audit`) — *AI Audit* button in the Admin
  Panel. Gemini flags contradictions/anomalies. Fallback: deterministic rules
  from the migration flags.
- **AI Fix Tools (function calling)** (`POST /api/admin/audit/fix/{id}`) — each
  flagged row has a prompt box: the admin types a natural-language instruction
  (e.g. *"set the date to 2024-01-15"*, *"correct the brand"*, *"move to
  repair"*) and Gemini decides which **tool** to call to fix it. Tools live in
  [`ai/tools.py`](backend/app/ai/tools.py) and cover every fixable flag:
  `set_brand`, `set_purchase_date`, `set_status`, `set_quarantine`, `set_name`,
  `set_category`, `set_serial_number`, `set_assigned_to` — each clears the
  matching audit flag. A contradictory *"In Use but unassigned"* state can be
  resolved either by recording a holder (`set_assigned_to`) or releasing the
  device (`set_status` → Available).
  Every fix is logged to an `AuditAction` history the admin can review (per-row
  and via the *History* panel). Fallback: a deterministic prompt parser routes
  to the same tools so it works with no API key.

All **degrade gracefully**: with no `GEMINI_API_KEY` (or on any error) the
fallbacks run, so the product never breaks because of the AI layer.

---

## Design decisions vs. the wireframes

The Figma wireframes were used as inspiration; deviations and their reasons:
- **Added `Serial Number` and `Category`** — present in the wireframe forms but
  absent from the seed schema; added as optional fields.
- **`Rented` label = canonical `In Use`** — the source of truth stays `In Use`
  (matching the seed); the UI relabels it.
- **Added an "Add User" action** in the Admin Panel — the wireframe omits it,
  but the spec requires admins to be the only way accounts are created.
- **Added an "AI Audit" action** to surface the Inventory Auditor.

### Visual polish

The UI uses a small set of animated components under
`frontend/src/components/visual/`, re-implemented in Vue from the open-source
[React Bits](https://reactbits.dev) collection (MIT) since this app is Vue, not
React:
- **ClickSpark** — spark burst on every click (global canvas overlay).
- **Aurora** — soft animated gradient backdrop on the login screen.
- **ShinyText** — shimmer sweep over page headings.
- **CountUp + SpotlightCard** — animated inventory stats with a cursor-following spotlight.
- Plus staggered table-row entrances and subtle button/row hover states.

All respect `prefers-reduced-motion`. Credit: effect designs from React Bits (MIT).

---

## Implementation Status & Trade-offs

### ✅ Fully implemented
- Login + JWT auth; admin-only account creation
- Hardware CRUD (admin), sorting & filtering, toggle Repair
- Rent / Return with state-machine guards
- Seed audit/migration with report + quarantine
- Semantic Search + Inventory Auditor + tool-calling fixes (Gemini + fallbacks)
- 10 backend tests (incl. the 3 required critical: cannot rent broken / in-use
  gear, seed audit quarantines & dedupes)

### ⚡ Shortcuts & "hacks"
- **JWT stored in `localStorage`.** *Why:* fastest path for an internal MVP.
  *Future:* httpOnly, SameSite cookies + refresh-token rotation.
- **SQLite, seeded on boot.** *Why:* zero-config, portable, easy to review.
  *Future:* Postgres + a real migration tool (Alembic) and a persistent volume.
- **Semantic search sends the whole catalogue per query.** *Why:* fine for
  ~dozens of items. *Future:* pre-computed embeddings + vector search.
- **`allow_origins=["*"]` CORS.** *Why:* dev convenience. *Future:* lock to the
  deployed origin.

### ⚠ Partial / missing
- No edit-device modal yet (the pencil action is stubbed in the wireframe).
- No pagination; rentals have no due dates / history view.

### 🔮 Next steps (24h roadmap)
1. Edit-device flow + device detail/history drawer.
2. Embedding-based semantic search + result explanations.
3. Harden auth (cookie sessions, password reset) and lock down CORS.

---

## AI Development Log

- **Tooling:** **Claude Code** for planning, scaffolding, multi-agent parallel
  work, debugging and runtime verification; **Google Gemini** (`google-genai`)
  for the in-app AI features.
- **Data strategy:** see *Data Strategy* above — the seed audit/migration report
  is the artifact. AI helped enumerate the seed's edge cases (duplicate ids,
  future date, DD-MM-YYYY date, brand typo, invalid status, damaged-but-
  "Available" devices); each got an explicit, reviewable rule rather than a
  silent rewrite.
- **Prompt trail:** the full, verbatim history is in [`PROMPTS.md`](PROMPTS.md).
- **The "Correction":** moments where AI output was wrong and I corrected it
  (more in [`PROMPTS.md`](PROMPTS.md)):
  - **Silent LLM fallback — the subtle one.** The tool-calling fixer *looked*
    healthy (HTTP 200), but every fix was quietly handled by the deterministic
    fallback, never the LLM. Root cause: `ai/tools.py` called `json.dumps(...)`
    without importing `json`; the resulting `NameError` was swallowed by a broad
    `except Exception` in `run_fix`, which fell back — even reporting *"no
    GEMINI_API_KEY set"* while a key was present. Caught by **verifying the path
    at runtime** (injecting a fake client) instead of trusting the 200; fixed the
    missing import, wired up two tools that were defined but never exposed to the
    model (`set_category`, `set_serial_number`), added `set_assigned_to`, and made
    the broad `except` **log** so the regression can't hide again.
  - **`passlib` + modern `bcrypt`** raised *"password cannot be longer than 72
    bytes"* → replaced with direct `bcrypt` + explicit 72-byte truncation.
  - **Naive semantic-search fallback** matched short tokens ("app" ⊂ "Apple")
    and returned laptops/mice for a phone query → rewritten with device-type
    inference, use-case mapping and stopword filtering.
  - **Deprecated `google-generativeai`** SDK → migrated to `google-genai`.

---

## Deployment

Single-container: build the Vue app, let FastAPI serve it (see `Dockerfile`).
Set `GEMINI_API_KEY` and `SECRET_KEY` as secrets. Suitable for Render / Fly.io /
Railway free tiers. ⚠️ SQLite is **ephemeral** on those hosts (re-seeds on each
cold start) — fine for a demo; use a volume or Postgres for anything real.
