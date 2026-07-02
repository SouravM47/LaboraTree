"""Phase 2 integration tests: auth flow + tenant isolation. Requires a live Postgres."""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

from laboratree.main import app


def _email() -> str:
    return f"user-{uuid.uuid4().hex[:10]}@example.com"


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_register_login_me_and_project_flow():
    with TestClient(app) as client:
        email = _email()
        # register -> creates a starter org + owner membership
        r = client.post(
            "/api/auth/register",
            json={"email": email, "password": "supersecret1", "full_name": "Ada"},
        )
        assert r.status_code == 201, r.text
        token = r.json()["access_token"]

        # me
        me = client.get("/api/auth/me", headers=_auth(token))
        assert me.status_code == 200
        assert me.json()["email"] == email
        assert me.json()["role"] == "owner"

        # login returns a working token too
        r2 = client.post("/api/auth/login", json={"email": email, "password": "supersecret1"})
        assert r2.status_code == 200

        # create a project
        cp = client.post(
            "/api/projects", json={"name": "Study A"}, headers=_auth(token)
        )
        assert cp.status_code == 201, cp.text
        project_id = cp.json()["id"]

        # it appears in the list
        lst = client.get("/api/projects", headers=_auth(token))
        assert lst.status_code == 200
        assert any(p["id"] == project_id for p in lst.json())


def test_tenant_isolation_between_orgs():
    with TestClient(app) as client:
        # user A + project
        ra = client.post(
            "/api/auth/register",
            json={"email": _email(), "password": "supersecret1", "full_name": "A"},
        )
        token_a = ra.json()["access_token"]
        pa = client.post("/api/projects", json={"name": "A secret"}, headers=_auth(token_a))
        project_a = pa.json()["id"]

        # user B in a different org
        rb = client.post(
            "/api/auth/register",
            json={"email": _email(), "password": "supersecret1", "full_name": "B"},
        )
        token_b = rb.json()["access_token"]

        # B cannot list A's project
        lst_b = client.get("/api/projects", headers=_auth(token_b))
        assert all(p["id"] != project_a for p in lst_b.json())

        # B cannot fetch A's project by id
        got = client.get(f"/api/projects/{project_a}", headers=_auth(token_b))
        assert got.status_code == 404


def test_unauthenticated_is_rejected():
    with TestClient(app) as client:
        assert client.get("/api/projects").status_code == 401
        assert client.get("/api/auth/me").status_code == 401
