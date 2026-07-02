"""Member management + RBAC role assignment."""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

from laboratree.main import app


def _reg(client, role_hint="U"):
    email = f"user-{uuid.uuid4().hex[:10]}@example.com"
    r = client.post("/api/auth/register",
                    json={"email": email, "password": "supersecret1", "full_name": role_hint})
    body = r.json()
    return email, body["access_token"], body["org_id"]


def _h(token):
    return {"Authorization": f"Bearer {token}"}


def test_owner_can_add_and_promote_member():
    with TestClient(app) as client:
        _, owner_token, org = _reg(client, "Owner")
        member_email, _, _ = _reg(client, "Member")  # registers a second user (own org)

        add = client.post(f"/api/orgs/{org}/members",
                          headers=_h(owner_token),
                          json={"email": member_email, "role": "analyst"})
        assert add.status_code == 201, add.text
        member_id = add.json()["user_id"]
        assert add.json()["role"] == "analyst"

        members = client.get(f"/api/orgs/{org}/members", headers=_h(owner_token)).json()
        assert len(members) == 2

        promoted = client.patch(f"/api/orgs/{org}/members/{member_id}",
                                headers=_h(owner_token), json={"role": "admin"})
        assert promoted.status_code == 200
        assert promoted.json()["role"] == "admin"


def test_add_unregistered_email_404():
    with TestClient(app) as client:
        _, owner_token, org = _reg(client, "Owner")
        r = client.post(f"/api/orgs/{org}/members", headers=_h(owner_token),
                        json={"email": "nobody@nowhere.example", "role": "viewer"})
        assert r.status_code == 404


def test_non_admin_cannot_add_member():
    with TestClient(app) as client:
        # owner A + org
        _, owner_token, org = _reg(client, "Owner")
        # user B registered, added as viewer
        b_email, b_token, _ = _reg(client, "B")
        client.post(f"/api/orgs/{org}/members", headers=_h(owner_token),
                    json={"email": b_email, "role": "viewer"})
        # C registered
        c_email, _, _ = _reg(client, "C")
        # B (viewer) tries to add C to A's org -> 403 (needs X-Org-Id = A's org)
        r = client.post(f"/api/orgs/{org}/members",
                        headers={**_h(b_token), "X-Org-Id": org},
                        json={"email": c_email, "role": "analyst"})
        assert r.status_code == 403
