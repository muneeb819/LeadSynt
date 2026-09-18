"""Authentication tests: register/login/refresh/me + audit trail."""


def test_register_login_me_flow(client, db_session):
    # register
    r = client.post("/api/v1/auth/register", json={
        "email": "newuser@example.com", "full_name": "New User",
        "password": "Strong-Password-1",
    })
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["email"] == "newuser@example.com"

    # login
    r = client.post("/api/v1/auth/login", json={
        "email": "newuser@example.com", "password": "Strong-Password-1",
    })
    assert r.status_code == 200, r.text
    tokens = r.json()
    assert tokens["access_token"] and tokens["refresh_token"]

    # me
    r = client.get("/api/v1/auth/me",
                   headers={"Authorization": f"Bearer {tokens['access_token']}"})
    assert r.status_code == 200
    me = r.json()
    assert me["email"] == "newuser@example.com"
    assert me["roles"]  # default registration role assigned


def test_login_wrong_password_rejected(client, db_session):
    client.post("/api/v1/auth/register", json={
        "email": "pw@example.com", "full_name": "PW User",
        "password": "Strong-Password-1",
    })
    r = client.post("/api/v1/auth/login", json={
        "email": "pw@example.com", "password": "wrong-password-99",
    })
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "unauthorized"
    # failed login is audited
    from app.models.ops import AuditLog

    logs = db_session.query(AuditLog).filter(AuditLog.action == "auth.login.failed").all()
    assert len(logs) == 1


def test_me_requires_token(client):
    r = client.get("/api/v1/auth/me")
    assert r.status_code == 401


def test_refresh_flow(client, db_session):
    client.post("/api/v1/auth/register", json={
        "email": "refresh@example.com", "full_name": "Refresh User",
        "password": "Strong-Password-1",
    })
    login = client.post("/api/v1/auth/login", json={
        "email": "refresh@example.com", "password": "Strong-Password-1",
    }).json()
    r = client.post("/api/v1/auth/refresh", json={"refresh_token": login["refresh_token"]})
    assert r.status_code == 200
    assert r.json()["access_token"]


def test_refresh_rejects_access_token(client, db_session):
    client.post("/api/v1/auth/register", json={
        "email": "typemix@example.com", "full_name": "Type Mix",
        "password": "Strong-Password-1",
    })
    login = client.post("/api/v1/auth/login", json={
        "email": "typemix@example.com", "password": "Strong-Password-1",
    }).json()
    r = client.post("/api/v1/auth/refresh", json={"refresh_token": login["access_token"]})
    assert r.status_code == 401


def test_duplicate_registration_conflict(client):
    for _ in range(2):
        r = client.post("/api/v1/auth/register", json={
            "email": "dup@example.com", "full_name": "Dup User",
            "password": "Strong-Password-1",
        })
    assert r.status_code == 409
