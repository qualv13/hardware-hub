"""Thin Gemini wrapper powering Semantic Search and the Inventory Auditor.

Uses the current `google-genai` SDK (the old `google-generativeai` package is
deprecated). Both functions degrade gracefully: with no API key (or on any
SDK/network error) they fall back to deterministic logic so the app never
breaks because of the AI layer.
"""

import json
import re

from ..config import settings

_DANGER = ["swelling", "liquid damage", "do not issue", "sticky", "cracked", "water"]

# --------------------------------------------------------------------------- #
# Device-type inference and use-case mapping (used by _keyword_fallback)      #
# --------------------------------------------------------------------------- #

# Ordered list of (pattern_fragments, device_type).  First match wins.
_TYPE_RULES: list[tuple[list[str], str]] = [
    (["iphone", "galaxy s", "galaxy a", "pixel", " phone", "smartphone"], "phone"),
    (["ipad", " tab ", "tablet", "tab "], "tablet"),
    (["macbook", "xps", "thinkpad", "ideapad", "zenbook", "vivobook",
      "laptop", "notebook", "surface pro", "surface book", "surface laptop",
      "chromebook"], "laptop"),
    (["magic keyboard", "keyboard", "mechanical key"], "keyboard"),
    (["basilisk", "mx master", "mx anywhere", "deathadder", "superlight",
      " mouse"], "mouse"),
    (["wh-", "wf-", "headphone", "earbud", "airpod", "buds ", "bose qc",
      "bose nc", "quietcomfort", "soundlink"], "headphones"),
    (["monitor", " display", "ultrasharp", "27\"", "24\"", "32\"",
      "curved"], "monitor"),
    (["surface", "ipad"], "tablet"),   # catch-all Surface/iPad after laptop
    (["mac mini", "mac pro", "imac", "desktop", "tower"], "desktop"),
    (["switch", "playstation", "xbox", "controller", "gamepad"], "gaming"),
    (["camera", "webcam", "mirrorless", "dslr"], "camera"),
    (["projector"], "projector"),
    (["printer", "scanner"], "printer"),
]

# Use-case keywords -> sets of device types that satisfy that use case.
# More specific / longer phrases come first so they're tried before fragments.
_USE_CASE_RULES: list[tuple[list[str], set[str]]] = [
    # Mobile / app testing
    (["mobile app", "ios app", "android app", "test app", "test on mobile",
      "test mobile", "testing app", "app testing", "test my app",
      "something to test"], {"phone", "tablet"}),
    # Audio / communication
    (["noise cancel", "listen to music", "music", "podcast", "audio",
      "noise cancell", "call", "meeting", "conference call",
      "work from home audio", "headset"], {"headphones"}),
    # Presentation / screen
    (["present", "presentation", "big screen", "external screen",
      "external display", "second screen", "dual monitor"], {"monitor", "laptop"}),
    # Coding / office work
    (["develop", "coding", "code", "programming", "type", "typing",
      "spreadsheet", "document", "word", "excel", "email",
      "work from home", "remote work", "office work"], {"laptop"}),
    # Design / creative
    (["design", "photo edit", "video edit", "creative", "illustrat",
      "photoshop"], {"laptop", "tablet"}),
    # Mobile / phone (generic) — use word-boundary style: avoid "phone" inside "headphones"
    (["mobile", " phone", "android", "ios", "iphone", "smartphone",
      "cellular", "sim card"], {"phone"}),
    # Tablet
    (["tablet", "ipad", "drawing", "sketch", "stylus"], {"tablet"}),
    # Mouse / pointing
    (["click", "point", "mouse", "scroll", "gaming mouse"], {"mouse"}),
    # Keyboard
    (["keyboard", "type on", "mechanical", "wireless keyboard"], {"keyboard"}),
    # Monitor
    (["monitor", "display", "screen"], {"monitor"}),
    # Gaming
    (["game", "gaming", "play games", "fps", "controller"], {"gaming"}),
    # Camera
    (["photo", "video", "record", "camera", "webcam", "stream"], {"camera"}),
]

_STOPWORDS = {
    "i", "a", "an", "the", "to", "in", "on", "at", "of", "or", "and", "for",
    "my", "me", "we", "us", "it", "is", "be", "do", "by", "as", "up", "so",
    "if", "no", "go", "but", "not", "can", "are", "was", "has", "had", "its",
    "will", "need", "want", "like", "that", "with", "some", "what", "this",
    "from", "have", "get", "use", "used", "using", "would", "could", "should",
    "just", "only", "also", "something", "anything", "everything",
}


def _infer_type(item: dict) -> str | None:
    """Infer a device type from item name and category using heuristics."""
    text = f"{item['name']} {item.get('category') or ''}".lower()
    for patterns, device_type in _TYPE_RULES:
        if any(p in text for p in patterns):
            return device_type
    return None


def _desired_types(query: str) -> set[str]:
    """Map a natural-language query to a set of desired device types."""
    q = query.lower()
    desired: set[str] = set()
    for phrases, types in _USE_CASE_RULES:
        if any(phrase in q for phrase in phrases):
            desired |= types
    return desired


def _meaningful_tokens(text: str) -> list[str]:
    """Split text into lowercase tokens, dropping stopwords and short tokens."""
    raw = re.split(r"[\s\-/,;.()\[\]]+", text.lower())
    return [t for t in raw if len(t) >= 3 and t not in _STOPWORDS]


_CLIENT = None


def _client():
    """Return a cached google-genai Client, or None when unavailable."""
    global _CLIENT
    if not settings.gemini_api_key:
        return None
    if _CLIENT is None:
        try:
            from google import genai

            _CLIENT = genai.Client(api_key=settings.gemini_api_key)
        except Exception:
            return None
    return _CLIENT


def _generate(prompt: str):
    """Return the model's text for a plain prompt, or None on any failure."""
    client = _client()
    if client is None:
        return None
    try:
        resp = client.models.generate_content(
            model=settings.gemini_model, contents=prompt
        )
        return resp.text
    except Exception:
        return None


def _extract_json(text: str):
    text = text.strip().strip("`").strip()
    if text.lower().startswith("json"):
        text = text[4:].strip()
    return json.loads(text)


# --------------------------------------------------------------------------- #
# Semantic search                                                             #
# --------------------------------------------------------------------------- #
def semantic_search(query: str, items: list[dict]) -> list[int]:
    """Return hardware ids matching a natural-language query, best first."""
    if _client() is None:
        return _keyword_fallback(query, items)

    catalog = json.dumps(
        [
            {"id": i["id"], "name": i["name"], "brand": i["brand"], "category": i.get("category")}
            for i in items
        ],
        default=str,
    )
    prompt = (
        "You are a hardware search assistant for an internal equipment hub.\n"
        "Your job: given a USER QUERY and a JSON CATALOG, infer the device TYPE "
        "and use-case the user needs, then return ONLY a JSON array of matching "
        "item ids (integers), best matches first.\n\n"
        "RULES:\n"
        "1. Reason about device type first. Examples:\n"
        "   - 'test my mobile app' or 'test on phone/tablet' -> phones and tablets ONLY\n"
        "   - 'listen to music' / 'noise cancelling' -> headphones ONLY\n"
        "   - 'code' / 'develop' / 'type' / 'spreadsheet' -> laptops ONLY\n"
        "   - 'present' / 'external screen' -> monitor or laptop\n"
        "   - 'click' / 'point device' -> mouse ONLY\n"
        "2. Do NOT pad results with unrelated device types.\n"
        "3. 'app' in the query does NOT imply 'Apple'. Match by use-case.\n"
        "4. Return [] if nothing in the catalog fits the use-case.\n"
        "5. Output a raw JSON array only — no markdown, no explanation.\n\n"
        f"USER QUERY: {query}\n\nCATALOG: {catalog}"
    )
    text = _generate(prompt)
    if text is None:
        return _keyword_fallback(query, items)
    try:
        ids = _extract_json(text)
        return [int(i) for i in ids]
    except Exception:
        return _keyword_fallback(query, items)


def _keyword_fallback(query: str, items: list[dict]) -> list[int]:
    """Deterministic fallback: type-aware use-case matching + token scoring."""
    desired = _desired_types(query)
    query_tokens = _meaningful_tokens(query)

    # Classify every item
    typed: list[tuple[int, str | None]] = [(it["id"], _infer_type(it)) for it in items]

    if desired:
        # Return ONLY items whose type is in the desired set, ordered by
        # how many meaningful query tokens appear in their name/brand.
        type_hits = [
            it for it in items if _infer_type(it) in desired
        ]
        if type_hits:
            def _score(item: dict) -> int:
                blob = f"{item['name']} {item['brand']}".lower()
                return sum(1 for tok in query_tokens if tok in blob)

            type_hits.sort(key=_score, reverse=True)
            return [it["id"] for it in type_hits]
        # Desired types found in rules but no catalog items have those types —
        # fall through to token matching below.

    # No use-case type mapping: rank by meaningful token overlap only.
    # Never match single-char tokens or stopwords (already filtered).
    if not query_tokens:
        return []

    scored: list[tuple[int, int]] = []
    for it in items:
        blob = f"{it['name']} {it['brand']} {it.get('category') or ''}".lower()
        score = sum(1 for tok in query_tokens if tok in blob)
        if score > 0:
            scored.append((it["id"], score))

    scored.sort(key=lambda x: x[1], reverse=True)
    return [item_id for item_id, _ in scored]


# --------------------------------------------------------------------------- #
# Inventory auditor                                                           #
# --------------------------------------------------------------------------- #
def audit_inventory(items: list[dict]) -> list[dict]:
    """Return [{id, name, issues:[...]}] for anomalous records."""
    if _client() is None:
        return _rule_fallback(items)

    catalog = json.dumps(items, default=str)
    prompt = (
        "You are an inventory auditor. Inspect the hardware JSON and return ONLY "
        "a JSON array of issues. Each element: "
        '{"id": int, "name": str, "issues": [str]}. Flag, among others: a status '
        "that contradicts notes/history (e.g. Available but battery swelling or "
        "liquid damage), future purchase dates, missing/empty required fields, "
        "suspicious brand typos, invalid status values, and duplicates.\n\n"
        f"CATALOG: {catalog}"
    )
    text = _generate(prompt)
    if text is None:
        return _rule_fallback(items)
    try:
        return _extract_json(text)
    except Exception:
        return _rule_fallback(items)


def _rule_fallback(items: list[dict]) -> list[dict]:
    out = []
    for it in items:
        issues = []
        if it.get("audit_flags"):
            issues += [f for f in it["audit_flags"].split(";") if f]
        blob = f"{it.get('notes') or ''} {it.get('history') or ''}".lower()
        if it["status"] == "Available" and any(k in blob for k in _DANGER):
            issues.append("safety: marked Available but notes indicate damage")
        if issues:
            out.append({"id": it["id"], "name": it["name"], "issues": issues})
    return out
