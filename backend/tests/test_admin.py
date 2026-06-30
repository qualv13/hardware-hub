"""Admin & auth domain-enforcement tests."""


def test_login_non_booksy_email_rejected(client):
    """Login with a non-@booksy.com email must be rejected with HTTP 400."""
    r = client.post(
        "/api/auth/login", json={"email": "x@gmail.com", "password": "anything"}
    )
    assert r.status_code == 400
    assert "booksy.com" in r.json()["detail"].lower()


def test_create_user_non_booksy_email_rejected(client, auth):
    """Admin creating a user with a non-@booksy.com email must be rejected with HTTP 400."""
    r = client.post(
        "/api/admin/users",
        json={"email": "hacker@evil.com", "name": "Evil", "password": "pw123"},
        headers=auth,
    )
    assert r.status_code == 400
    assert "booksy.com" in r.json()["detail"].lower()


def test_create_user_booksy_email_accepted(client, auth):
    """Admin creating a user with a @booksy.com email must succeed (200)."""
    r = client.post(
        "/api/admin/users",
        json={
            "email": "newuser@booksy.com",
            "name": "New User",
            "password": "secure123",
        },
        headers=auth,
    )
    assert r.status_code == 200
    data = r.json()
    assert data["email"] == "newuser@booksy.com"


def test_audit_apply_corrects_brand_typo(client, auth):
    """POST /api/admin/audit/apply must correct the 'Appel' → 'Apple' brand typo."""
    r = client.post("/api/admin/audit/apply", headers=auth)
    assert r.status_code == 200
    data = r.json()
    # At least one correction must have been applied (the iPad row seeded with 'Appel').
    assert data["count"] >= 1
    # Find the iPad row in the applied list.
    corrected = [
        item for item in data["applied"]
        if any("Appel" in change and "Apple" in change for change in item["changes"])
    ]
    assert len(corrected) >= 1, f"Expected Appel->Apple fix, got: {data['applied']}"
    # The change description must follow the required format.
    assert corrected[0]["changes"] == ["brand: Appel -> Apple"]


def test_audit_apply_is_idempotent(client, auth):
    """Second call to POST /api/admin/audit/apply must return count=0 (nothing left to fix)."""
    # First call was already made in the previous test (session-scoped DB), so
    # call once more and expect nothing to fix.
    r = client.post("/api/admin/audit/apply", headers=auth)
    assert r.status_code == 200
    data = r.json()
    assert data["count"] == 0
    assert data["applied"] == []


def test_audit_fix_applies_via_prompt_and_logs_history(client, auth):
    """The per-item prompt drives a tool that fixes the flag, and the action is
    recorded in history (uses the deterministic fallback — no API key in tests)."""
    # #6 (Logitech) is seeded with a future purchase date.
    before = client.get("/api/ai/audit", headers=auth).json()["issues"]
    six = next(i for i in before if i["id"] == 6)
    assert any("future_purchase_date" in f for f in six["issues"])

    r = client.post(
        "/api/admin/audit/fix/6",
        json={"prompt": "change the purchase date to 2024-01-15"},
        headers=auth,
    )
    assert r.status_code == 200
    data = r.json()
    assert any("purchase_date" in c for c in data["changes"])
    assert data["history"] and data["history"][0]["summary"].startswith("purchase_date")

    # The future-date flag is gone on re-audit (row may drop out entirely).
    after = client.get("/api/ai/audit", headers=auth).json()["issues"]
    six_after = next((i for i in after if i["id"] == 6), None)
    if six_after is not None:
        assert not any("future_purchase_date" in f for f in six_after["issues"])

    # The action shows up in the global history.
    hist = client.get("/api/admin/history", headers=auth).json()["history"]
    assert any(h["hardware_id"] == 6 for h in hist)


def test_audit_fix_invalid_status_quarantine_release(client, auth):
    """A prompt can release a quarantined record by setting a valid status."""
    r = client.post(
        "/api/admin/audit/fix/10",
        json={"prompt": "set status to Repair"},
        headers=auth,
    )
    assert r.status_code == 200
    assert any("status:" in c for c in r.json()["changes"])
    # #10 (Unknown Device) was quarantined; setting a valid status releases it.
    visible = client.get("/api/hardware", headers=auth).json()
    assert any(i["id"] == 10 for i in visible)

    # Restore quarantine so later tests still see the seeded migration state
    # (the DB is shared session-wide across test files).
    client.post(
        "/api/admin/audit/fix/10", json={"prompt": "quarantine"}, headers=auth
    )
    visible = client.get("/api/hardware", headers=auth).json()
    assert not any(i["id"] == 10 for i in visible)
