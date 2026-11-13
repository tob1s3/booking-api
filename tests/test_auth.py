async def test_register_login_and_me(client):
    resp = await client.post(
        "/auth/register",
        json={"email": "Pavel@Example.com", "password": "long-enough-1", "name": "Павел"},
    )
    assert resp.status_code == 201
    assert resp.json()["email"] == "pavel@example.com"
    assert "password" not in resp.text and "password_hash" not in resp.text

    resp = await client.post(
        "/auth/token", data={"username": "pavel@example.com", "password": "long-enough-1"}
    )
    assert resp.status_code == 200
    headers = {"Authorization": f"Bearer {resp.json()['access_token']}"}

    resp = await client.get("/users/me", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["name"] == "Павел"
    assert resp.json()["is_admin"] is False


async def test_duplicate_email_is_rejected(client):
    body = {"email": "a@example.com", "password": "long-enough-1", "name": "A"}
    assert (await client.post("/auth/register", json=body)).status_code == 201
    body["email"] = "A@EXAMPLE.COM"
    assert (await client.post("/auth/register", json=body)).status_code == 409


async def test_short_password_is_rejected(client):
    resp = await client.post(
        "/auth/register", json={"email": "a@example.com", "password": "short", "name": "A"}
    )
    assert resp.status_code == 422


async def test_wrong_password_and_unknown_user_look_the_same(client, user_headers):
    wrong = await client.post(
        "/auth/token", data={"username": "client@example.com", "password": "nope-nope-nope"}
    )
    unknown = await client.post(
        "/auth/token", data={"username": "ghost@example.com", "password": "nope-nope-nope"}
    )
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()


async def test_protected_route_requires_valid_token(client):
    assert (await client.get("/users/me")).status_code == 401
    bad = {"Authorization": "Bearer not-a-real-token"}
    assert (await client.get("/users/me", headers=bad)).status_code == 401
