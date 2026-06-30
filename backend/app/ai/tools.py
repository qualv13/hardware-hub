"""LLM-callable tools for fixing flagged inventory issues.

Each flag the seed audit can raise has a corresponding tool that mutates the
Hardware row and clears the matching flag. `run_fix` sends the admin's natural
-language prompt to Gemini together with these tools (function calling); Gemini
chooses and invokes the right tool(s). With no API key, a deterministic
fallback parser interprets common instructions so the feature still works.
"""

import json
import logging
import re
from datetime import datetime

logger = logging.getLogger(__name__)

from ..models import VALID_STATUSES

# --------------------------------------------------------------------------- #
# Executors (the actual mutations). Each returns a human-readable change line. #
# --------------------------------------------------------------------------- #


def _strip_flags(hw, *prefixes: str) -> None:
    hw.audit_flags = ";".join(
        f
        for f in hw.audit_flags.split(";")
        if f and not any(f.startswith(p) for p in prefixes)
    )


def set_brand(hw, brand: str) -> str:
    old = hw.brand or "(empty)"
    hw.brand = brand
    _strip_flags(hw, "brand_typo_suspected", "missing_brand")
    return f"brand: {old} -> {brand}"


def set_purchase_date(hw, value: str) -> str:
    d = datetime.strptime(value, "%Y-%m-%d").date()
    old = hw.purchase_date.isoformat() if hw.purchase_date else "(none)"
    hw.purchase_date = d
    _strip_flags(
        hw,
        "future_purchase_date",
        "date_format_normalized",
        "missing_purchase_date",
        "unparseable_date",
    )
    return f"purchase_date: {old} -> {d.isoformat()}"


def set_status(hw, status: str) -> str:
    if status not in VALID_STATUSES:
        raise ValueError(f"invalid status '{status}'")
    old = hw.status
    hw.status = status
    _strip_flags(hw, "status_overridden_safety", "invalid_status_quarantined")
    hw.quarantined = False
    return f"status: {old} -> {status}"


def set_quarantine(hw, quarantined: bool) -> str:
    hw.quarantined = bool(quarantined)
    if not quarantined:
        _strip_flags(hw, "invalid_status_quarantined")
    return f"quarantined -> {bool(quarantined)}"


def set_name(hw, name: str) -> str:
    old = hw.name
    hw.name = name
    return f"name: {old} -> {name}"


def set_category(hw, category: str) -> str:
    hw.category = category
    return f"category -> {category}"


def set_serial_number(hw, serial_number: str) -> str:
    hw.serial_number = serial_number
    return f"serial_number -> {serial_number}"


def set_assigned_to(hw, assigned_to: str) -> str:
    old = hw.assigned_to or "(none)"
    hw.assigned_to = assigned_to or None
    return f"assigned_to: {old} -> {assigned_to or '(none)'}"


EXECUTORS = {
    "set_brand": set_brand,
    "set_purchase_date": set_purchase_date,
    "set_status": set_status,
    "set_quarantine": set_quarantine,
    "set_name": set_name,
    "set_category": set_category,
    "set_serial_number": set_serial_number,
    "set_assigned_to": set_assigned_to,
}

# Tool specs surfaced to the LLM (and usable for docs/UI).
TOOL_SPECS = [
    {
        "name": "set_brand",
        "description": "Correct or set the device brand/manufacturer (fixes brand typos and missing brand).",
        "parameters": {
            "type": "object",
            "properties": {"brand": {"type": "string"}},
            "required": ["brand"],
        },
    },
    {
        "name": "set_purchase_date",
        "description": "Set the purchase date in ISO format YYYY-MM-DD (fixes future, wrong-format or missing dates).",
        "parameters": {
            "type": "object",
            "properties": {"value": {"type": "string", "description": "ISO date YYYY-MM-DD"}},
            "required": ["value"],
        },
    },
    {
        "name": "set_status",
        "description": "Set a valid status: 'Available', 'In Use', or 'Repair' (fixes invalid/contradictory status; releases quarantine).",
        "parameters": {
            "type": "object",
            "properties": {"status": {"type": "string", "enum": list(VALID_STATUSES)}},
            "required": ["status"],
        },
    },
    {
        "name": "set_quarantine",
        "description": "Quarantine (true) or release from quarantine (false).",
        "parameters": {
            "type": "object",
            "properties": {"quarantined": {"type": "boolean"}},
            "required": ["quarantined"],
        },
    },
    {
        "name": "set_name",
        "description": "Set the device name (fixes unknown/placeholder names).",
        "parameters": {
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
        },
    },
    {
        "name": "set_category",
        "description": "Set the device category.",
        "parameters": {
            "type": "object",
            "properties": {"category": {"type": "string"}},
            "required": ["category"],
        },
    },
    {
        "name": "set_serial_number",
        "description": "Set the device serial number.",
        "parameters": {
            "type": "object",
            "properties": {"serial_number": {"type": "string"}},
            "required": ["serial_number"],
        },
    },
    {
        "name": "set_assigned_to",
        "description": (
            "Set who the device is assigned to (an email). Resolves a "
            "contradictory 'In Use but unassigned' state by recording the "
            "holder; pass an empty string to clear the assignment."
        ),
        "parameters": {
            "type": "object",
            "properties": {"assigned_to": {"type": "string"}},
            "required": ["assigned_to"],
        },
    },
]


# --------------------------------------------------------------------------- #
# Orchestration                                                               #
# --------------------------------------------------------------------------- #


def run_fix(hw, prompt: str):
    """Resolve an issue from a natural-language prompt. Mutates ``hw`` in place.
    Returns (changes: list[str], explanation: str)."""
    try:
        result = _gemini_fix(hw, prompt)
        if result is not None:
            return result
    except Exception:
        # Don't let an LLM/SDK failure break the fix flow — but log it, so a
        # regression (e.g. a missing import) can't silently masquerade as the
        # deterministic fallback the way it once did.
        logger.exception("Gemini fix failed; using deterministic fallback")
    return _fallback_fix(hw, prompt)


def _hw_context(hw) -> dict:
    return {
        "id": hw.id,
        "name": hw.name,
        "brand": hw.brand,
        "category": hw.category,
        "serial_number": hw.serial_number,
        "purchase_date": hw.purchase_date.isoformat() if hw.purchase_date else None,
        "status": hw.status,
        "quarantined": hw.quarantined,
        "audit_flags": hw.audit_flags,
        "notes": hw.notes,
        "history": hw.history,
    }


def _gemini_fix(hw, prompt: str):
    """Native Gemini function calling via the google-genai SDK. Gemini chooses
    and the SDK auto-invokes the tool closures below, which mutate ``hw``."""
    from ..config import settings
    from .gemini import _client

    client = _client()
    if client is None:
        return None
    from google.genai import types

    changes: list[str] = []

    # Closures the SDK auto-calls; they apply the fix and record the change.
    def set_brand_tool(brand: str) -> dict:
        "Correct or set the device brand/manufacturer name."
        changes.append(set_brand(hw, brand))
        return {"ok": True}

    def set_purchase_date_tool(value: str) -> dict:
        "Set the purchase date. 'value' must be ISO format YYYY-MM-DD."
        changes.append(set_purchase_date(hw, value))
        return {"ok": True}

    def set_status_tool(status: str) -> dict:
        "Set a valid status: 'Available', 'In Use' or 'Repair'."
        changes.append(set_status(hw, status))
        return {"ok": True}

    def set_quarantine_tool(quarantined: bool) -> dict:
        "Quarantine (true) or release from quarantine (false)."
        changes.append(set_quarantine(hw, quarantined))
        return {"ok": True}

    def set_name_tool(name: str) -> dict:
        "Set the device name."
        changes.append(set_name(hw, name))
        return {"ok": True}

    def set_category_tool(category: str) -> dict:
        "Set the device category (e.g. Laptop, Phone, Monitor, Headphones)."
        changes.append(set_category(hw, category))
        return {"ok": True}

    def set_serial_number_tool(serial_number: str) -> dict:
        "Set the device serial number."
        changes.append(set_serial_number(hw, serial_number))
        return {"ok": True}

    def set_assigned_to_tool(assigned_to: str) -> dict:
        "Set who the device is assigned to (an email); pass '' to clear it."
        changes.append(set_assigned_to(hw, assigned_to))
        return {"ok": True}

    config = types.GenerateContentConfig(
        system_instruction=(
            "You are a hardware inventory fixer. Given a device record (with audit "
            "flags) and the admin's request, call the appropriate tool(s) to fix the "
            "flagged problems. Only make changes the admin asked for or that clearly "
            "resolve a flag. Never invent data you cannot infer. To resolve a "
            "contradictory 'In Use but unassigned' state, either record a holder with "
            "set_assigned_to or move the device to 'Available' with set_status."
        ),
        tools=[
            set_brand_tool,
            set_purchase_date_tool,
            set_status_tool,
            set_quarantine_tool,
            set_name_tool,
            set_category_tool,
            set_serial_number_tool,
            set_assigned_to_tool,
        ],
    )
    resp = client.models.generate_content(
        model=settings.gemini_model,
        contents=(
            f"DEVICE: {json.dumps(_hw_context(hw), default=str)}\n\n"
            f"ADMIN REQUEST: {prompt or '(resolve the flags appropriately)'}"
        ),
        config=config,
    )
    explanation = ""
    try:
        explanation = (resp.text or "").strip()
    except Exception:
        explanation = ""
    if not explanation:
        explanation = "Applied: " + "; ".join(changes) if changes else "No change."
    return changes, explanation


def _extract_date(raw: str):
    """Find a date in the prompt with any common separator (-, ., /) and either
    order (ISO YYYY-MM-DD or day/month-first), and return it as ISO YYYY-MM-DD."""
    m = re.search(r"\b(\d{1,4})[-./](\d{1,2})[-./](\d{1,4})\b", raw)
    if not m:
        return None
    norm = f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%m-%d-%Y"):
        try:
            return datetime.strptime(norm, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _fallback_fix(hw, prompt: str):
    """Deterministic interpreter used when no GEMINI_API_KEY is configured."""
    raw = prompt or ""
    p = raw.lower()
    changes: list[str] = []

    date_iso = _extract_date(raw)
    if date_iso:
        changes.append(set_purchase_date(hw, date_iso))

    if "unquarantine" in p or "release" in p or "restore" in p:
        changes.append(set_quarantine(hw, False))
    elif "quarantine" in p:
        changes.append(set_quarantine(hw, True))

    if "repair" in p:
        changes.append(set_status(hw, "Repair"))
    elif "available" in p:
        changes.append(set_status(hw, "Available"))
    elif "in use" in p or "rented" in p:
        changes.append(set_status(hw, "In Use"))

    mb = re.search(r"brand\s+(?:to\s+|=\s*|->\s*)?([A-Za-z][\w .&-]+)", raw, re.I)
    if mb:
        changes.append(set_brand(hw, mb.group(1).strip()))

    # --- Flag-aware intent: act on THIS item's own audit flags when the admin
    # gives a high-level instruction ("fix the typo", "fix date format",
    # "resolve") instead of an explicit value. ---
    flags = hw.audit_flags or ""
    wants_all = (not p.strip()) or any(
        w in p for w in ("fix all", "fix everything", "fix the flag", "resolve", "clean")
    )

    # "typo" / "brand" / fix-all → apply the known brand-typo correction.
    if not mb and ("typo" in p or "brand" in p or wants_all):
        from ..seed.migrate import _BRAND_TYPOS

        if hw.brand in _BRAND_TYPOS:
            changes.append(set_brand(hw, _BRAND_TYPOS[hw.brand]))

    # "date format" / "format" / fix-all with no explicit date: the value was
    # already normalised to ISO at import, so just clear the informational flag.
    if not date_iso and ("format" in p or "date" in p or wants_all):
        if "date_format_normalized" in flags:
            _strip_flags(hw, "date_format_normalized")
            changes.append("cleared date_format_normalized flag (value already ISO)")

    if changes:
        explanation = "Applied locally (no GEMINI_API_KEY set): " + "; ".join(changes)
    else:
        explanation = (
            "Couldn't act on that without a model. Set GEMINI_API_KEY for full "
            "natural-language fixes, or be specific — e.g. 'set brand to Apple', "
            "'set date to 2024-01-15', 'move to repair'."
        )
    return changes, explanation
