"""Critical business-logic & data-integrity tests (AI-guided)."""


def test_cannot_rent_hardware_in_repair(client, auth):
    """A device in 'Repair' must never be rentable."""
    items = client.get(
        "/api/hardware", params={"include_quarantined": True}, headers=auth
    ).json()
    in_repair = next(i for i in items if i["status"] == "Repair")

    r = client.post(f"/api/hardware/{in_repair['id']}/rent", headers=auth)
    assert r.status_code == 409
    assert "repair" in r.json()["detail"].lower()


def test_cannot_rent_already_in_use(client, auth):
    """Renting twice must be rejected (no double-booking)."""
    available = next(
        i for i in client.get("/api/hardware", headers=auth).json()
        if i["status"] == "Available"
    )
    hid = available["id"]

    assert client.post(f"/api/hardware/{hid}/rent", headers=auth).status_code == 200
    assert client.post(f"/api/hardware/{hid}/rent", headers=auth).status_code == 409

    # cleanup so the device is free for other tests
    client.post(f"/api/hardware/{hid}/return", headers=auth)


def test_seed_migration_quarantines_and_dedupes(client, auth):
    """The deliberately broken seed must be cleaned: invalid record
    quarantined, duplicate id reassigned, damaged 'Available' forced to Repair."""
    visible = client.get("/api/hardware", headers=auth).json()
    all_rows = client.get(
        "/api/hardware", params={"include_quarantined": True}, headers=auth
    ).json()

    # 'Unknown Device' (invalid status) is quarantined -> hidden from inventory.
    assert "Unknown Device" not in [i["name"] for i in visible]

    # Duplicate id=4 was reassigned -> all ids are unique, both rows survive.
    ids = [i["id"] for i in all_rows]
    assert len(ids) == len(set(ids))
    names = [i["name"] for i in all_rows]
    assert "SAMSUNG Galaxy S21" in names
    assert "Duplicate ID Test Laptop" in names

    # Dell XPS (swelling battery) was Available in the seed -> forced to Repair.
    dell = next(i for i in all_rows if i["name"].startswith("Dell XPS"))
    assert dell["status"] == "Repair"
