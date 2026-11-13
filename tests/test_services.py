NEW_SERVICE = {"title": "Бритьё", "duration_minutes": 30, "price": 900}


async def test_only_admin_can_create_service(client, user_headers, admin_headers):
    assert (await client.post("/services", json=NEW_SERVICE)).status_code == 401
    assert (
        await client.post("/services", json=NEW_SERVICE, headers=user_headers)
    ).status_code == 403

    resp = await client.post("/services", json=NEW_SERVICE, headers=admin_headers)
    assert resp.status_code == 201
    assert resp.json()["is_active"] is True


async def test_invalid_service_is_rejected(client, admin_headers):
    bad = {**NEW_SERVICE, "duration_minutes": 0}
    assert (await client.post("/services", json=bad, headers=admin_headers)).status_code == 422


async def test_deactivated_service_disappears_from_list(client, admin_headers, haircut):
    assert [s["id"] for s in (await client.get("/services")).json()] == [haircut.id]

    resp = await client.patch(
        f"/services/{haircut.id}", json={"is_active": False}, headers=admin_headers
    )
    assert resp.status_code == 200
    assert (await client.get("/services")).json() == []
    assert (await client.get(f"/services/{haircut.id}/slots?day=2030-01-08")).status_code == 404


async def test_slots_endpoint(client, haircut):
    resp = await client.get(f"/services/{haircut.id}/slots?day=2030-01-08")
    assert resp.status_code == 200
    slots = resp.json()["slots"]
    # 10:00–19:00 с шагом 30 минут = 19 вариантов, минус 13:30, 14:00, 14:30 из-за перерыва
    assert len(slots) == 16
    assert slots[0] == "2030-01-08T07:00:00Z"


async def test_no_slots_in_the_past_or_beyond_horizon(client, haircut):
    past = await client.get(f"/services/{haircut.id}/slots?day=2030-01-05")
    far = await client.get(f"/services/{haircut.id}/slots?day=2030-03-01")
    assert past.json()["slots"] == [] and far.json()["slots"] == []
