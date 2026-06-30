# Prompt Trail

The prompt history that shaped the architecture and design of Hardware Hub, in
order. Prompts are quoted verbatim (mostly Polish, as they were written) with a
short note on what each one produced.

**Tooling:** built with **Claude Code** (planning, scaffolding, multi-agent
parallel work, debugging, verification via a headless browser preview).
In-app AI uses **Google Gemini** (`google-genai` SDK, `gemini-2.5-flash`) for
Semantic Search, the Inventory Auditor, and tool-calling fixes — with
deterministic fallbacks when no API key is set.

---

## 1. Understand the task
> *(attached: the assessment PDF + the Figma wireframes link)*
> „Przeglądnij materiały i wytłumacz co i jak muszę zrobić, jakie są ważne elementy itd"

→ Reviewed the PDF + wireframes; summarised the 3 pillars (management / rental /
AI-native) and flagged the **deliberately broken seed data** as the key,
gradeable detail (duplicate ids, future date, DD-MM-YYYY date, brand typo,
invalid status, damaged-but-"Available" devices).

## 2. Plan & gather preferences
> „Tak, pomóż rozplanować i podejrzeć wireframy z figmy. Pytaj jeśli nie będziesz pewien lub będziesz chciał poznać preferencje"

→ Produced the architecture plan + a ~4–5h schedule. Collected the key decisions:
- **Stack:** Python (FastAPI) + Vue.js
- **AI features:** Semantic Search + Inventory Auditor
- **LLM:** Gemini (free AI Studio key) + a free deploy target
- Wireframes inspected via the browser.

## 3. Scaffold the project
> *(attached: 5 wireframe screenshots — login, hardware list, my rentals, admin panel, add-device modal)*
> „projekt daj w tej ścieżce: H:\Projects\rental_app i możesz tam wygenerować szkielet"

→ Generated the full scaffold (FastAPI + SQLModel + SQLite + JWT, Vue 3 + Vite +
Pinia, the ⭐ seed audit/migration, Semantic Search + Inventory Auditor with
fallbacks, 3 critical tests, Dockerfile, README). UI matched the wireframes
("In Use" relabelled "Rented", added Serial Number/Category, Add User + AI Audit
actions).

## 4. First round of fixes (parallel agents)
> „Po użyciu AI audit powinna być możliwość zastosowania zmian które są proponowane. Przycisk repair powinien działać jak toggle dla stanu repair. Usuwanie nie działa. 'I need something to test my mobile app' zwraca np. laptop czy dziwne inne elementy jak myszka. maile z góry muszą mieć narzuconą końcówkę @booksy.com. Uruchom agentów, aby zająć się wszystkim równolegle"

→ Ran **3 parallel sub-agents** on disjoint files:
- enforce `@booksy.com` (login + user creation) + apply-audit endpoint + cascade delete
- rewrite semantic-search relevance (device-type + use-case mapping; "test a mobile app" → phones/tablets only)
- frontend: fixed repair-toggle path bug, delete, apply-audit button, `@booksy.com` suffix UI

## 5. Per-item audit review
> „apply suggestion musi być do każdego z osobna. Każdy z tych wierszy musi mieć też pole tekstowe, gdzie można odnieść się do zmian które są proponowane"

→ Replaced the single global "Apply" with a **per-row Apply button + per-row text
field**, persisted, surviving re-audit (initially as a saved note).

## 6. AI tool-calling (reframing the comment box as an LLM prompt)
> „dla każdej opcji która może się zepsuć powinien istnieć tool, który może wywołać LLM z api i naprawić dany problem. Dodanie komentarza nie miało być dodaniem komentarza, tylko wysłaniem prompta do LLMa w celu zaproponowania fixa z użyciem możliwych tooli. Admin od swojej strony powinien widzieć też notatki/historię"

→ Built `ai/tools.py` with one **tool per fixable flag** (`set_brand`,
`set_purchase_date`, `set_status`, `set_quarantine`, `set_name`, …). The row's
field is now a **natural-language prompt** sent to Gemini (function calling);
Gemini picks and runs the tool(s). Each fix is logged to an `AuditAction`
**history** visible per-row and in a History panel. Deterministic fallback when
no key is set.

## 7. Visual polish
> „Wzbogać możliwości wizualne frontendu poprzez użycie fragmentów ze strony react bits"

→ Added Vue ports of [React Bits](https://reactbits.dev) (MIT) effects:
ClickSpark, Aurora login backdrop, ShinyText headings, CountUp + SpotlightCard
inventory stats, staggered table-row entrances. (Credited in the README.)

## 8. SDK & model choice
> *(pasted the `google.generativeai` deprecation FutureWarning)*
> „…i chciałbym używać modelu Gemma 4 26B"
>
> „to używajmy gemini, zweryfikuj które obsługują toole z planu free"

→ Migrated from the deprecated `google-generativeai` to the current
`google-genai` SDK. Verified free-tier Gemini models that support custom
function calling and set the default to **`gemini-2.5-flash`** (Gemma models
don't support native tools, so we stayed on Gemini).

## 9. Debugging "it doesn't work" (local dev networking)
> „it still doesn't work" *(+ Vite proxy `ECONNREFUSED` / later `ETIMEDOUT` logs)*
>
> *(screenshot)* „fix date format and typo" → "Could not apply fix"
>
> „lokalnie może mają problem. Czy docker-compose może to postawić razem jakoś, żeby nie było konfliktów w komunikacji?"
>
> *(screenshot)* „set date to 29.06.2026" → no change

→ Diagnosed that the backend was healthy (always 200) and the failures were the
**Vite dev-proxy ↔ uvicorn connection** on Windows localhost (stale keep-alive,
ECONNREFUSED, ETIMEDOUT). Fixes: `keepAlive:false` proxy agent, SQLite WAL +
busy_timeout, robust `fixItem`, an auto-retry interceptor, and — the clean
answer — a **`docker-compose.yml`** that serves SPA + API from one origin (no
proxy). Also broadened the fallback date parser to accept `.` `/` `-` and
European order (`29.06.2026`).

## 10. This file
> „zapisz moje prompty zgodnie z tym co było w zadaniu"

---

## The "Correction" (required by the brief)
A few moments where AI output was wrong and had to be corrected (kept honest):
- **`passlib` + modern `bcrypt`** raised *"password cannot be longer than 72
  bytes"* during backend detection → replaced with direct `bcrypt` + explicit
  72-byte truncation.
- **Frontend called the wrong repair path** (`/api/hardware/{id}/repair` instead
  of `/api/admin/hardware/{id}/repair`) → 404; corrected the path.
- **Naive semantic-search fallback** matched short tokens ("app" ⊂ "Apple") and
  returned laptops/mice for a phone query → rewrote with device-type inference,
  use-case mapping and stopword filtering.
- **Deprecated `google-generativeai`** SDK → migrated to `google-genai`.
- **Vite dev-proxy** intermittent 500/ECONNREFUSED/ETIMEDOUT misattributed at
  first to reload-on-db then to IPv6; the real cause was stale keep-alive
  sockets → fixed at the proxy and sidestepped with Docker (single origin).
