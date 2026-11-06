"""
Unit and Integration Test Suite for ATIUS Sovereign IAM (sso.atius.io :8015)
and Omni Control-Plane FastAPI (admin.atius.io :34805).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.main import (
    DEFAULT_CONTROL_PLANE_PORT,
    DEFAULT_SSO_GATEWAY_PORT,
    _backend,
    create_app,
)

EDGE_GATEWAY_JSON = REPO_ROOT / "modules" / "atius-admin-edge-sso" / "configs" / "atius-admin-edge-gateway.json"
APACHE_DIR = REPO_ROOT / "modules" / "atius-admin-edge-sso" / "configs" / "apache"


@pytest.fixture()
def client(tmp_path: Path) -> TestClient:
    state_file = tmp_path / "iam_state.json"
    test_app = create_app(state_file=state_file)
    return TestClient(test_app)


def test_canonical_ports_and_health_contract(client: TestClient) -> None:
    assert DEFAULT_CONTROL_PLANE_PORT == 34805
    assert DEFAULT_SSO_GATEWAY_PORT == 8015

    res = client.get("/api/v1/health", headers={"Host": "admin.atius.io"})
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "healthy"
    assert body["service"] == "omni-control-plane"
    assert body["canonical_port"] == 34805
    assert body["sso_gateway_port"] == 8015
    assert body["cockpit_port"] == 9090
    assert body["storage_port"] == 8085
    assert body["zero_cockpit_collision"] is True
    assert body["legacy_port_8000_migrated"] is True

    sso_res = client.get("/api/v1/health", headers={"X-Forwarded-Host": "sso.atius.io"})
    assert sso_res.status_code == 200
    assert sso_res.json()["service"] == "atius-sso-iam-gateway"


def test_cors_allows_atius_dual_domains(client: TestClient) -> None:
    for origin in ("https://admin.atius.io", "https://sso.atius.io", "https://admin.atius.com.br", "https://sso.atius.com.br"):
        res = client.options(
            "/api/v1/health",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "GET",
            },
        )
        assert res.status_code == 200
        assert res.headers.get("access-control-allow-origin") == origin


def test_fleet_ports_and_single_vnic_topology(client: TestClient) -> None:
    ports_res = client.get("/api/v1/fleet/ports")
    assert ports_res.status_code == 200
    ports_data = ports_res.json()
    assert ports_data["collision_audit"]["cockpit_9090_isolated"] is True
    assert ports_data["collision_audit"]["legacy_8000_retired"] is True
    assert ports_data["collision_audit"]["control_plane_34805_active"] is True
    assert ports_data["collision_audit"]["sso_iam_8015_active"] is True

    topo_res = client.get("/api/v1/fleet/topology")
    assert topo_res.status_code == 200
    topo = topo_res.json()
    assert topo["network_architecture"] == "single-vcn-single-vnic"
    assert topo["control_plane_port"] == 34805
    assert topo["sso_iam_port"] == 8015
    assert topo["total"] == 6
    ips = {n["hostname"]: n["private_ip"] for n in topo["nodes"]}
    assert ips["atius-srv-1"] == "10.1.1.1"
    assert ips["atius-srv-2"] == "10.2.1.1"
    assert ips["atius-srv-3"] == "10.3.1.1"
    assert ips["atius-srv-4"] == "10.4.1.1"
    assert ips["horistic-srv"] == "10.51.1.1"
    assert ips["aln-srv"] == "10.52.1.1"


def test_sso_authentication_and_token_lifecycle(client: TestClient) -> None:
    # 1. Valid Admin login
    login_res = client.post(
        "/v1/token/generate",
        json={"email": "giovannimunizds@gmail.com", "password": "AtiusSovereign#2026"},
    )
    assert login_res.status_code == 200
    token = login_res.json()["access_token"]
    assert token.startswith("atius_iam_")
    assert "auth-token" in login_res.cookies

    # 2. Verify /v1/auth/me with Bearer token
    me_res = client.get("/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_res.status_code == 200
    me_data = me_res.json()
    assert me_data["authenticated"] is True
    assert me_data["user"]["email"] == "giovanni@atius.io"
    assert "giovannimunizds@gmail.com" in me_data["user"].get("email_aliases", [])
    assert me_data["user"]["role"] == "Admin"
    assert me_data["user"]["is_admin"] is True

    # 3. Bad password returns 401
    bad_res = client.post(
        "/v1/token/generate",
        json={"email": "giovannimunizds@gmail.com", "password": "wrong-password"},
    )
    assert bad_res.status_code == 401

    # 4. Logout revokes token
    logout_res = client.post("/api/sso/logout", headers={"Authorization": f"Bearer {token}"})
    assert logout_res.status_code == 200
    after_logout = client.get("/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert after_logout.status_code == 401


def test_rbac_personas_and_destination_refusal_matrix(client: TestClient) -> None:
    # Admin: allowed everywhere (sso.atius.io, admin.atius.io, cockpit.atius.io, storage.atius.io)
    for dest in ("sso.atius.io", "admin.atius.io", "cockpit.atius.io", "storage.atius.io"):
        res = client.post(
            "/api/v1/iam/authorize",
            json={"user": "giovannimunizds@gmail.com", "destination": dest},
        )
        assert res.status_code == 200, f"Admin should be allowed on {dest}"
        assert res.json()["authorized"] is True

    # Operator (Lívia): allowed on admin.atius.io & storage.atius.io, REFUSED (403) on sso.atius.io & cockpit.atius.io
    for allowed_dest in ("admin.atius.io", "storage.atius.io"):
        res = client.post(
            "/api/v1/iam/authorize",
            json={"user": "livia.nascimento@atius.io", "destination": allowed_dest},
        )
        assert res.status_code == 200
        assert res.json()["authorized"] is True

    for denied_dest in ("sso.atius.io", "cockpit.atius.io"):
        res = client.post(
            "/api/v1/iam/authorize",
            json={"user": "livia.nascimento@atius.io", "destination": denied_dest},
        )
        assert res.status_code == 403
        assert res.json()["authorized"] is False

    # Viewer (Carlos): allowed on storage.atius.io & dashboard.atius.io, REFUSED (403) on admin.atius.io & sso.atius.io
    res_viewer_ok = client.post(
        "/api/v1/iam/authorize",
        json={"user": "carlos.auditor@atius.io", "destination": "storage.atius.io"},
    )
    assert res_viewer_ok.status_code == 200

    res_viewer_denied = client.post(
        "/api/v1/iam/authorize",
        json={"user": "carlos.auditor@atius.io", "destination": "admin.atius.io"},
    )
    assert res_viewer_denied.status_code == 403
    assert res_viewer_denied.json()["authorized"] is False

    # Partner (Diego): allowed on trade.atius.io & remote.atius.io, REFUSED (403) on admin.atius.io, storage.atius.io, sso.atius.io
    res_partner_ok = client.post(
        "/api/v1/iam/authorize",
        json={"user": "parceiro.quant@horistic.com", "destination": "trade.atius.io"},
    )
    assert res_partner_ok.status_code == 200

    for forbidden_for_partner in ("admin.atius.io", "sso.atius.io", "storage.atius.io", "cockpit.atius.io"):
        res_partner_denied = client.post(
            "/api/v1/iam/authorize",
            json={"user": "parceiro.quant@horistic.com", "destination": forbidden_for_partner},
        )
        assert res_partner_denied.status_code == 403
        assert res_partner_denied.json()["authorized"] is False


def test_control_plane_execution_enforces_operator_or_admin_role(client: TestClient) -> None:
    # Login as Operator
    op_login = client.post(
        "/v1/token/generate",
        json={"email": "livia.nascimento@atius.io", "password": "OperatorAtius#2026"},
    )
    assert op_login.status_code == 200
    op_token = op_login.json()["access_token"]

    exec_ok = client.post(
        "/api/v1/control-plane/execute",
        headers={"Authorization": f"Bearer {op_token}"},
        json={"action": "sync_edge_gateway", "target_host": "atius-srv-1"},
    )
    assert exec_ok.status_code == 200
    assert exec_ok.json()["executed"] is True
    assert exec_ok.json()["control_plane_port"] == 34805

    # Login as Viewer -> must be refused with 403 Forbidden on control-plane execution
    vw_login = client.post(
        "/v1/token/generate",
        json={"email": "carlos.auditor@atius.io", "password": "ViewerAtius#2026"},
    )
    assert vw_login.status_code == 200
    vw_token = vw_login.json()["access_token"]

    exec_denied = client.post(
        "/api/v1/control-plane/execute",
        headers={"Authorization": f"Bearer {vw_token}"},
        json={"action": "sync_edge_gateway", "target_host": "atius-srv-1"},
    )
    assert exec_denied.status_code == 403
    assert exec_denied.json()["executed"] is False


def test_user_crud_blocking_and_dynamic_destination_assignment(client: TestClient) -> None:
    # 1. Create a new user with Partner role
    create_res = client.post(
        "/api/v1/iam/users",
        json={
            "email": "novo.operador@atius.io",
            "name": "Álvaro Gonçalves",
            "role": "Partner",
            "cpf": "123.456.789-01",
            "allowed_destinations": ["trade.atius.io"],
            "password": "TempPass#123",
        },
    )
    assert create_res.status_code == 201
    new_user = create_res.json()["user"]
    uid = new_user["id"]
    token = create_res.json()["token"]

    # Initially cannot access admin.atius.io
    authz_before = client.post(
        "/api/v1/iam/authorize",
        json={"token": token, "destination": "admin.atius.io"},
    )
    assert authz_before.status_code == 403

    # 2. Elevate user to Operator and grant admin.atius.io destination
    patch_res = client.patch(
        f"/api/v1/iam/users/{uid}",
        json={
            "role": "Operator",
            "allowed_destinations": ["admin.atius.io", "trade.atius.io"],
        },
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["user"]["role"] == "Operator"

    # Now authorized for admin.atius.io
    authz_after = client.post(
        "/api/v1/iam/authorize",
        json={"token": token, "destination": "admin.atius.io"},
    )
    assert authz_after.status_code == 200
    assert authz_after.json()["authorized"] is True

    # 3. Block user -> immediately refused on /v1/auth/me, /v1/token/generate, and /api/v1/iam/authorize
    block_res = client.post(f"/api/v1/iam/users/{uid}/block", json={"reason": "Suspicious activity"})
    assert block_res.status_code == 200
    assert block_res.json()["blocked"] is True

    me_blocked = client.get("/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_blocked.status_code == 403
    assert me_blocked.json()["reason"] == "user_blocked"

    authz_blocked = client.post(
        "/api/v1/iam/authorize",
        json={"token": token, "destination": "admin.atius.io"},
    )
    assert authz_blocked.status_code == 403
    assert authz_blocked.json()["reason"] == "user_blocked"

    # 4. Unblock user -> access restored
    unblock_res = client.post(f"/api/v1/iam/users/{uid}/unblock")
    assert unblock_res.status_code == 200
    assert unblock_res.json()["blocked"] is False

    me_restored = client.get("/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_restored.status_code == 200
    assert me_restored.json()["authenticated"] is True


def test_bidirectional_accent_folding_and_9_tier_search(client: TestClient) -> None:
    score_text_match = _backend.score_price if hasattr(_backend, "score_price") else None
    from app.main import _load_control_plane_module

    search_mod = __import__("omni_control_plane_backend.search", fromlist=["score_text_match", "score_document_match"])

    # Bidirectional accent-folding: 'lívia' matches 'Livia Nascimento' AND 'livia' matches 'Lívia Nascimento'
    s1, t1 = search_mod.score_text_match("lívia nascimento", "Livia Nascimento")
    s2, t2 = search_mod.score_text_match("livia nascimento", "Lívia Nascimento")
    assert s1 == 0.98 and t1 == 3
    assert s2 == 0.98 and t2 == 3

    # API search: searching 'livia' (without accent) finds 'Lívia Nascimento'
    res_no_accent = client.get("/api/v1/iam/users", params={"q": "livia"})
    assert res_no_accent.status_code == 200
    users_found = res_no_accent.json()["users"]
    assert len(users_found) >= 1
    assert users_found[0]["name"] == "Lívia Nascimento"

    # API search: searching 'lívia' (with accent) finds 'Lívia Nascimento'
    res_with_accent = client.get("/api/v1/iam/users", params={"q": "lívia"})
    assert res_with_accent.status_code == 200
    assert res_with_accent.json()["users"][0]["name"] == "Lívia Nascimento"

    # Numeric CPF search
    res_cpf = client.get("/api/v1/iam/users", params={"q": "555666"})
    assert res_cpf.status_code == 200
    assert res_cpf.json()["users"][0]["email"] == "livia.nascimento@atius.io"


def test_edge_gateway_and_apache_vhosts_contracts() -> None:
    cfg = json.loads(EDGE_GATEWAY_JSON.read_text(encoding="utf-8"))
    assert cfg["authCheckUrl"] == "http://127.0.0.1:8015/v1/auth/me"
    assert cfg["sites"]["admin.atius.com.br"]["upstream"] == "http://127.0.0.1:34805"
    assert cfg["sites"]["sso.atius.com.br"]["upstream"] == "http://127.0.0.1:8015"
    assert cfg["sites"]["cockpit.atius.com.br"]["upstream"] == "http://127.0.0.1:9090"

    for vhost_name in ("admin.atius.com.br.conf", "admin.atius.io.conf", "sso.atius.com.br.conf", "sso.atius.io.conf"):
        vhost_path = APACHE_DIR / vhost_name
        assert vhost_path.exists(), f"Missing Apache vhost {vhost_name}"
        content = vhost_path.read_text(encoding="utf-8")
        if vhost_name.startswith("admin."):
            assert "http://127.0.0.1:34805" in content
        if vhost_name.startswith("sso."):
            assert "http://127.0.0.1:8015" in content


def test_edge_gateway_login_senha_payload_and_cookie_domains(client: TestClient) -> None:
    # Edge Gateway handleLogin sends {"login": ..., "senha": ...} with X-Forwarded-Host
    res_br = client.post(
        "/v1/token/generate",
        headers={"X-Forwarded-Host": "admin.atius.com.br"},
        json={"login": "livia.nascimento@atius.io", "senha": "OperatorAtius#2026"},
    )
    assert res_br.status_code == 200
    assert res_br.json()["user"]["role"] == "Operator"
    set_cookie_br = res_br.headers.get("set-cookie", "")
    assert "Domain=.atius.com.br" in set_cookie_br
    assert "omni.atius.io" in res_br.json()["user"]["allowed_destinations"]
    assert "admin.atius.com.br" in res_br.json()["user"]["allowed_destinations"]

    res_io = client.post(
        "/v1/token/generate",
        headers={"X-Forwarded-Host": "admin.atius.io"},
        json={"login": "livia.operator", "senha": "OperatorAtius#2026"},
    )
    assert res_io.status_code == 200
    set_cookie_io = res_io.headers.get("set-cookie", "")
    assert "Domain=admin.atius.io" in set_cookie_io


def test_auth_me_enforces_rbac_on_com_br_and_alias_forwarded_hosts(client: TestClient) -> None:
    op_tok = client.post(
        "/v1/token/generate",
        json={"email": "livia.nascimento@atius.io", "password": "OperatorAtius#2026"},
    ).json()["access_token"]
    vw_tok = client.post(
        "/v1/token/generate",
        json={"email": "carlos.auditor@atius.io", "password": "ViewerAtius#2026"},
    ).json()["access_token"]

    # Operator allowed on admin.atius.com.br and omni.atius.io, refused on sso.atius.com.br and cockpit.atius.com.br
    for allowed_host in ("admin.atius.com.br", "omni.atius.io", "omni.atius.com.br", "backup.atius.io"):
        r = client.get("/v1/auth/me", headers={"Authorization": f"Bearer {op_tok}", "X-Forwarded-Host": allowed_host})
        assert r.status_code == 200, f"Operator should be 200 on {allowed_host}"

    for denied_host in ("sso.atius.com.br", "cockpit.atius.com.br"):
        r = client.get("/v1/auth/me", headers={"Authorization": f"Bearer {op_tok}", "X-Forwarded-Host": denied_host})
        assert r.status_code == 403, f"Operator should be 403 on {denied_host}"

    # Viewer allowed on storage.atius.com.br & backup.atius.io, refused on admin.atius.com.br & omni.atius.io
    for allowed_host in ("storage.atius.com.br", "backup.atius.io"):
        r = client.get("/v1/auth/me", headers={"Authorization": f"Bearer {vw_tok}", "X-Forwarded-Host": allowed_host})
        assert r.status_code == 200, f"Viewer should be 200 on {allowed_host}"

    for denied_host in ("admin.atius.com.br", "omni.atius.io", "sso.atius.com.br"):
        r = client.get("/v1/auth/me", headers={"Authorization": f"Bearer {vw_tok}", "X-Forwarded-Host": denied_host})
        assert r.status_code == 403, f"Viewer should be 403 on {denied_host}"


def test_cross_process_state_sync_between_sso_8015_and_control_plane_34805(tmp_path: Path) -> None:
    shared_state = tmp_path / "shared_iam_state.json"
    sso_client = TestClient(create_app(state_file=shared_state))
    cp_client = TestClient(create_app(state_file=shared_state))

    # 1. Create a new Operator user on SSO (:8015) instance
    created = sso_client.post(
        "/api/v1/iam/users",
        json={
            "email": "cross.sync@atius.io",
            "name": "Helena Sincronizada",
            "role": "Operator",
            "allowed_destinations": ["admin.atius.io"],
            "password": "SyncPass#2026",
        },
    )
    assert created.status_code == 201
    uid = created.json()["user"]["id"]

    # 2. Issue token on SSO (:8015) and immediately execute action on Control-Plane (:34805)
    tok_res = sso_client.post(
        "/v1/token/generate",
        json={"login": "cross.sync@atius.io", "senha": "SyncPass#2026"},
    )
    assert tok_res.status_code == 200
    tok = tok_res.json()["access_token"]

    exec_ok = cp_client.post(
        "/api/v1/control-plane/execute",
        headers={"Authorization": f"Bearer {tok}"},
        json={"action": "verify_sync", "target_host": "atius-srv-1"},
    )
    assert exec_ok.status_code == 200

    # 3. Block user on SSO (:8015) -> Control-Plane (:34805) immediately refuses with 403
    sso_client.post(f"/api/v1/iam/users/{uid}/block", json={"reason": "Cross-process block test"})
    exec_blocked = cp_client.post(
        "/api/v1/control-plane/execute",
        headers={"Authorization": f"Bearer {tok}"},
        json={"action": "verify_sync", "target_host": "atius-srv-1"},
    )
    assert exec_blocked.status_code == 403
    assert exec_blocked.json()["error"] == "user_blocked"

    # 4. Unblock on SSO (:8015), then logout (revoke token) on SSO (:8015) -> Control-Plane (:34805) refuses with 401
    sso_client.post(f"/api/v1/iam/users/{uid}/unblock")
    sso_client.post("/api/sso/logout", headers={"Authorization": f"Bearer {tok}"})
    me_revoked = cp_client.get("/v1/auth/me", headers={"Authorization": f"Bearer {tok}"})
    assert me_revoked.status_code == 401


def test_email_aliases_and_partner_role_for_socios(client: TestClient) -> None:
    # 1. Giovanni Muniz (Admin Soberano) - all 5 aliases must login with same password
    giovanni_aliases = [
        "giovanni@atius.io",
        "giovanni.muniz@atius.io",
        "admin.atius@gmail.com",
        "giovannimunizds@gmail.com",
        "holding.atius@gmail.com",
    ]
    for g_login in giovanni_aliases:
        res = client.post(
            "/v1/token/generate",
            json={"email": g_login, "password": "AtiusSovereign#2026"},
        )
        assert res.status_code == 200, f"Login failed for Giovanni alias {g_login}"
        body = res.json()
        assert body["user"]["email"] == "giovanni@atius.io"
        assert body["user"]["role"] == "Admin"
        assert body["user"]["is_admin"] is True
        token = body["access_token"]

        # Giovanni has sovereign access to control-plane execute and admin.atius.io
        me = client.get("/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert me.status_code == 200
        assert me.json()["user"]["is_admin"] is True

        exec_res = client.post(
            "/api/v1/control-plane/execute",
            headers={"Authorization": f"Bearer {token}"},
            json={"action": "test_alias_admin", "target_host": "atius-srv-1"},
        )
        assert exec_res.status_code == 200

    # 2. Julio Gambarra (Partner / Sócio ATS) - all aliases authenticate with PartnerAtius#2026
    julio_aliases = [
        "julio@atius.io",
        "julio.gambarra@atius.io",
        "jcgambarra2013@gmail.com",
    ]
    for j_login in julio_aliases:
        res = client.post(
            "/v1/token/generate",
            json={"email": j_login, "password": "PartnerAtius#2026"},
        )
        assert res.status_code == 200, f"Login failed for Julio alias {j_login}"
        body = res.json()
        assert body["user"]["email"] == "julio@atius.io"
        assert body["user"]["role"] == "Partner"
        assert body["user"]["is_admin"] is False
        token = body["access_token"]

        # Allowed on ATS destinations (dashboard, trade, backtest, remote, strategy, painel)
        for ats_dest in ("dashboard.atius.io", "trade.atius.io", "backtest.atius.io", "remote.atius.io", "strategy.atius.io", "painel.atius.io"):
            authz_ats = client.post(
                "/api/v1/iam/authorize",
                json={"token": token, "destination": ats_dest},
            )
            assert authz_ats.status_code == 200, f"Julio should access ATS {ats_dest}"

        # STRICTLY REFUSED (403) on admin.atius.io, cockpit.atius.io, landscape, and control-plane execution
        for blocked_dest in ("admin.atius.io", "cockpit.atius.io", "landscape.atius.io", "vault.atius.io", "storage.atius.io"):
            authz_blocked = client.post(
                "/api/v1/iam/authorize",
                json={"token": token, "destination": blocked_dest},
            )
            assert authz_blocked.status_code == 403, f"Julio must NOT access {blocked_dest}"

        exec_denied = client.post(
            "/api/v1/control-plane/execute",
            headers={"Authorization": f"Bearer {token}"},
            json={"action": "reboot", "target_host": "atius-srv-1"},
        )
        assert exec_denied.status_code == 403

    # 3. Diego Carvalho (Partner / Sócio ATS) - all aliases authenticate with PartnerAtius#2026
    diego_aliases = [
        "diego@atius.io",
        "diego.carvalho@atius.io",
        "diegopolaroid01@gmail.com",
        "parceiro.quant@horistic.com",
    ]
    for d_login in diego_aliases:
        res = client.post(
            "/v1/token/generate",
            json={"email": d_login, "password": "PartnerAtius#2026"},
        )
        assert res.status_code == 200, f"Login failed for Diego alias {d_login}"
        body = res.json()
        assert body["user"]["email"] == "diego@atius.io"
        assert body["user"]["role"] == "Partner"
        assert body["user"]["is_admin"] is False
        token = body["access_token"]

        # ATS destinations authorized
        for ats_dest in ("dashboard.atius.io", "trade.atius.io", "backtest.atius.io", "remote.atius.io"):
            authz_ats = client.post(
                "/api/v1/iam/authorize",
                json={"token": token, "destination": ats_dest},
            )
            assert authz_ats.status_code == 200

        # Control-plane & Admin forbidden
        authz_admin = client.post(
            "/api/v1/iam/authorize",
            json={"token": token, "destination": "admin.atius.io"},
        )
        assert authz_admin.status_code == 403

    # 4. Search by alias finds users
    res_search_g = client.get("/api/v1/iam/users", params={"q": "admin.atius@gmail.com"})
    assert res_search_g.status_code == 200
    assert res_search_g.json()["users"][0]["name"] == "Giovanni Muniz"

    res_search_j = client.get("/api/v1/iam/users", params={"q": "julio.gambarra@atius.io"})
    assert res_search_j.status_code == 200
    assert res_search_j.json()["users"][0]["name"] == "Julio Gambarra"

    res_search_d = client.get("/api/v1/iam/users", params={"q": "diego.carvalho@atius.io"})
    assert res_search_d.status_code == 200
    assert res_search_d.json()["users"][0]["name"] == "Diego Carvalho"

    # 5. Create new Partner user with aliases & verify CRUD
    create_partner = client.post(
        "/api/v1/iam/users",
        json={
            "email": "marina@atius.io",
            "name": "Marina Costa",
            "role": "Partner",
            "email_aliases": ["marina.costa@atius.io", "marinacosta@gmail.com"],
            "password": "PartnerMarina#2026",
            "allowed_destinations": ["trade.atius.io", "dashboard.atius.io"],
        },
    )
    assert create_partner.status_code == 201
    created_id = create_partner.json()["user"]["id"]
    assert "marina.costa@atius.io" in create_partner.json()["user"]["email_aliases"]

    # Login via alias
    login_alias = client.post(
        "/v1/token/generate",
        json={"email": "marinacosta@gmail.com", "password": "PartnerMarina#2026"},
    )
    assert login_alias.status_code == 200
    assert login_alias.json()["user"]["email"] == "marina@atius.io"

    # Update aliases via PATCH
    patch_alias = client.patch(
        f"/api/v1/iam/users/{created_id}",
        json={"email_aliases": ["marina.costa@atius.io", "marinacosta@gmail.com", "marina.quant@atius.io"]},
    )
    assert patch_alias.status_code == 200
    assert "marina.quant@atius.io" in patch_alias.json()["user"]["email_aliases"]


def test_omni_and_cluster_api_aliases_and_storage_branding(client: TestClient) -> None:
    # 1. Test /api/v1/omni/ports and /api/v1/cluster/ports aliases
    for path in ("/api/v1/omni/ports", "/api/v1/cluster/ports"):
        res = client.get(path)
        assert res.status_code == 200, f"Failed on {path}"
        data = res.json()
        assert data["collision_audit"]["control_plane_34805_active"] is True
        # Check storage branding in canonical ports
        storage_contract = next(c for c in data["canonical_port_contracts"] if "storage.atius" in c["subdomain"])
        assert storage_contract["service"] == "Atius Storage & Backup Web"

    # 2. Test /api/v1/omni/topology and /api/v1/cluster/topology aliases
    for path in ("/api/v1/omni/topology", "/api/v1/cluster/topology", "/api/v1/omni/hosts", "/api/v1/cluster/hosts"):
        res = client.get(path)
        assert res.status_code == 200, f"Failed on {path}"
        data = res.json()
        assert data["network_architecture"] == "single-vcn-single-vnic"
        assert data["cluster_architecture"] == "single-vcn-single-vnic"
        assert data["omni_cluster"] == "atius-sovereign"
        assert data["control_plane_port"] == 34805
        assert data["total"] == 6

    # 3. Test /api/v1/omni/search and /api/v1/cluster/search aliases
    for path in ("/api/v1/omni/search", "/api/v1/cluster/search"):
        res = client.get(path, params={"q": "storage"})
        assert res.status_code == 200, f"Failed on {path}"
        data = res.json()
        assert any("storage.atius.io" in d["host"] for d in data.get("destinations", []))

    # 4. Verify Atius Storage branding in destinations
    dests_res = client.get("/api/v1/iam/destinations")
    assert dests_res.status_code == 200
    dests = {d["host"]: d for d in dests_res.json()["destinations"]}

    storage_dest = dests["storage.atius.io"]
    assert storage_dest["name"] == "Atius Storage & Backup Control"
    assert storage_dest["category"] == "Atius Storage"

    landscape_dest = dests["landscape.atius.io"]
    assert landscape_dest["name"] == "Canonical Landscape Omni Cluster Server"
    assert landscape_dest["category"] == "Omni Cluster Governance"
