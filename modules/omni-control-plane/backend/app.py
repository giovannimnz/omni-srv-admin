"""
Omni Control-Plane FastAPI (127.0.0.1:34805) & Atius SSO IAM Gateway (127.0.0.1:8015).
Consolidates ATIUS fleet governance on canonical port 34805 and Keycloak SSO IAM access control on port 8015.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import Cookie, FastAPI, Header, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from pydantic import BaseModel, Field

from .iam_store import (
    CANONICAL_COCKPIT_PORT,
    CANONICAL_CONTROL_PLANE_PORT,
    CANONICAL_EDGE_GATEWAY_PORT,
    CANONICAL_SSO_GATEWAY_PORT,
    CANONICAL_STORAGE_PORT,
    DEFAULT_FLEET_NODES,
    IAMControlPlaneStore,
)
from .search import rank_records

MODULE_ROOT = Path(__file__).resolve().parent.parent
FRONTEND_DIR = MODULE_ROOT / "frontend"

DEFAULT_CONTROL_PLANE_PORT = int(os.environ.get("OMNI_CONTROL_PLANE_PORT", str(CANONICAL_CONTROL_PLANE_PORT)))
DEFAULT_SSO_GATEWAY_PORT = int(os.environ.get("ATIUS_SSO_IAM_PORT", str(CANONICAL_SSO_GATEWAY_PORT)))
DEFAULT_BIND_HOST = os.environ.get("OMNI_CONTROL_PLANE_HOST", "127.0.0.1")

ALLOWED_CORS_ORIGINS = [
    "https://admin.atius.io",
    "https://admin.atius.com.br",
    "https://omni.atius.io",
    "https://omni.atius.com.br",
    "https://sso.atius.io",
    "https://sso.atius.com.br",
    "https://cockpit.atius.io",
    "https://cockpit.atius.com.br",
    "https://storage.atius.io",
    "https://storage.atius.com.br",
    "http://127.0.0.1:34805",
    "http://localhost:34805",
    "http://127.0.0.1:8015",
    "http://localhost:8015",
    "http://127.0.0.1:8210",
]


class UserCreateRequest(BaseModel):
    id: Optional[str] = None
    email: str
    username: Optional[str] = None
    name: str
    role: str = "Viewer"
    roles: Optional[List[str]] = None
    is_admin: Optional[bool] = None
    status: str = "active"
    blocked: bool = False
    mfa_enabled: bool = False
    cpf: Optional[str] = ""
    cnpj: Optional[str] = ""
    document: Optional[str] = ""
    custom_permissions: List[str] = Field(default_factory=list)
    allowed_destinations: Optional[List[str]] = None
    denied_destinations: List[str] = Field(default_factory=list)
    password: Optional[str] = "AtiusDefault#2026"


class UserUpdateRequest(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    role: Optional[str] = None
    roles: Optional[List[str]] = None
    is_admin: Optional[bool] = None
    status: Optional[str] = None
    blocked: Optional[bool] = None
    mfa_enabled: Optional[bool] = None
    cpf: Optional[str] = None
    cnpj: Optional[str] = None
    custom_permissions: Optional[List[str]] = None
    allowed_destinations: Optional[List[str]] = None
    denied_destinations: Optional[List[str]] = None
    password: Optional[str] = None


class BlockUserRequest(BaseModel):
    reason: str = "Administrative policy enforcement"
    actor: str = "admin"


class RoleUpdateRequest(BaseModel):
    description: Optional[str] = None
    permissions: Optional[List[str]] = None
    default_destinations: Optional[List[str]] = None


class DestinationUpdateRequest(BaseModel):
    allowed_roles: Optional[List[str]] = None
    required_permission: Optional[str] = None
    upstream: Optional[str] = None
    description: Optional[str] = None


class TokenGenerateRequest(BaseModel):
    login: Optional[str] = None
    senha: Optional[str] = None
    username: Optional[str] = None
    email: Optional[str] = None
    password: Optional[str] = None


class AuthorizeRequest(BaseModel):
    user: Optional[str] = None
    token: Optional[str] = None
    destination: str
    permission: Optional[str] = None


class ControlPlaneActionRequest(BaseModel):
    action: str
    target_host: str = "atius-srv-1"
    parameters: Dict[str, Any] = Field(default_factory=dict)


def _extract_token(
    request: Request,
    authorization: Optional[str] = None,
) -> str:
    if authorization and authorization.strip():
        raw = authorization.strip()
        if raw.lower().startswith("bearer "):
            return raw[7:].strip()
        return raw

    cookie_header = request.headers.get("cookie") or ""
    for part in cookie_header.split(";"):
        if "=" not in part:
            continue
        k, v = part.split("=", 1)
        if k.strip() in ("auth-token", "atius_access_token") and v.strip():
            return v.strip()
    return ""


def create_app(state_file: Optional[Path] = None) -> FastAPI:
    store = IAMControlPlaneStore(state_file=state_file)
    app = FastAPI(
        title="ATIUS Omni Control-Plane & Keycloak SSO IAM Gateway",
        description=(
            "Centralized Control-Plane on canonical port 34805 (admin.atius.io) "
            "and Keycloak SSO IAM Access Controller on port 8015 (sso.atius.io)."
        ),
        version="2.0.0",
    )
    app.state.iam_store = store

    app.add_middleware(
        CORSMiddleware,
        allow_origins=ALLOWED_CORS_ORIGINS,
        allow_origin_regex=r"^https://([a-z0-9-]+\.)?atius\.(io|com\.br)$",
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    # -------------------------------------------------------------------------
    # Health, Ports & Fleet Topology (Omni Control-Plane :34805)
    # -------------------------------------------------------------------------
    @app.get("/healthz")
    @app.get("/api/v1/health")
    def get_health(request: Request) -> Dict[str, Any]:
        store._load_if_changed()
        host_header = (request.headers.get("x-forwarded-host") or request.headers.get("host") or "").split(":")[0]
        is_sso_portal = host_header.startswith("sso.")
        return {
            "status": "healthy",
            "service": "atius-sso-iam-gateway" if is_sso_portal else "omni-control-plane",
            "host": host_header or "127.0.0.1",
            "canonical_port": CANONICAL_CONTROL_PLANE_PORT,
            "sso_gateway_port": CANONICAL_SSO_GATEWAY_PORT,
            "edge_gateway_port": CANONICAL_EDGE_GATEWAY_PORT,
            "cockpit_port": CANONICAL_COCKPIT_PORT,
            "storage_port": CANONICAL_STORAGE_PORT,
            "zero_cockpit_collision": True,
            "legacy_port_8000_migrated": True,
            "iam_realm": "atius-sovereign",
            "roles_available": list(store.roles.keys()),
            "users_count": len(store.users),
            "destinations_count": len(store.destinations),
        }

    @app.get("/api/v1/fleet/ports")
    def get_fleet_ports() -> Dict[str, Any]:
        return {
            "canonical_port_contracts": [
                {
                    "subdomain": "admin.atius.io / admin.atius.com.br",
                    "aliases": ["omni.atius.io", "omni.atius.com.br"],
                    "service": "Omni Control-Plane FastAPI",
                    "bind_address": f"127.0.0.1:{CANONICAL_CONTROL_PLANE_PORT}",
                    "port": CANONICAL_CONTROL_PLANE_PORT,
                    "edge_gateway_port": CANONICAL_EDGE_GATEWAY_PORT,
                    "legacy_port_retired": 8000,
                    "cockpit_collision": False,
                },
                {
                    "subdomain": "sso.atius.io / sso.atius.com.br",
                    "aliases": [],
                    "service": "Keycloak SSO Admin & IAM Gateway",
                    "bind_address": f"127.0.0.1:{CANONICAL_SSO_GATEWAY_PORT}",
                    "port": CANONICAL_SSO_GATEWAY_PORT,
                    "edge_gateway_port": CANONICAL_EDGE_GATEWAY_PORT,
                    "cockpit_collision": False,
                },
                {
                    "subdomain": "cockpit.atius.io / cockpit.atius.com.br",
                    "aliases": [],
                    "service": "Host Linux Cockpit PAM Web Console",
                    "bind_address": f"127.0.0.1:{CANONICAL_COCKPIT_PORT}",
                    "port": CANONICAL_COCKPIT_PORT,
                    "edge_gateway_port": CANONICAL_EDGE_GATEWAY_PORT,
                    "cockpit_collision": False,
                },
                {
                    "subdomain": "storage.atius.io / storage.atius.com.br",
                    "aliases": ["backup.atius.io", "backup.atius.com.br"],
                    "service": "Omni Backup & Storage Web",
                    "bind_address": f"10.14.1.14:{CANONICAL_STORAGE_PORT}",
                    "port": CANONICAL_STORAGE_PORT,
                    "edge_gateway_port": CANONICAL_EDGE_GATEWAY_PORT,
                    "cockpit_collision": False,
                },
            ],
            "collision_audit": {
                "cockpit_9090_isolated": True,
                "legacy_8000_retired": True,
                "control_plane_34805_active": True,
                "sso_iam_8015_active": True,
            },
        }

    @app.get("/api/v1/fleet/hosts")
    @app.get("/api/v1/fleet/topology")
    def get_fleet_topology(q: Optional[str] = Query(default=None)) -> Dict[str, Any]:
        nodes = list(DEFAULT_FLEET_NODES)
        if q and q.strip():
            nodes = rank_records(
                nodes,
                query=q,
                text_fields=("hostname", "oci_profile", "private_ip", "role", "vcn_cidr"),
                doc_fields=(),
            )
        return {
            "network_architecture": "single-vcn-single-vnic",
            "subnet_pattern": "10.X.0.0/16",
            "host_ip_pattern": "10.X.1.1",
            "gateway_ip_pattern": "10.X.0.1",
            "dns_ip_pattern": "10.X.0.2",
            "control_plane_port": CANONICAL_CONTROL_PLANE_PORT,
            "sso_iam_port": CANONICAL_SSO_GATEWAY_PORT,
            "nodes": nodes,
            "total": len(nodes),
        }

    @app.get("/api/v1/fleet/search")
    def search_ecosystem(q: str = Query(default="")) -> Dict[str, Any]:
        matched_users = store.list_users(query=q)
        matched_destinations = rank_records(
            list(store.destinations.values()),
            query=q,
            text_fields=("host", "name", "category", "description", "upstream", "aliases"),
            doc_fields=(),
        )
        matched_nodes = rank_records(
            DEFAULT_FLEET_NODES,
            query=q,
            text_fields=("hostname", "oci_profile", "private_ip", "role"),
            doc_fields=(),
        )
        return {
            "query": q,
            "users": matched_users,
            "destinations": matched_destinations,
            "nodes": matched_nodes,
            "total_matches": len(matched_users) + len(matched_destinations) + len(matched_nodes),
        }

    # -------------------------------------------------------------------------
    # Keycloak SSO Auth Gateway Compatibility (/v1/auth/me, /v1/token/generate)
    # -------------------------------------------------------------------------
    @app.get("/v1/auth/me")
    def auth_me(
        request: Request,
        authorization: Optional[str] = Header(default=None),
    ) -> JSONResponse:
        token = _extract_token(request, authorization)
        ok, reason, user = store.verify_token(token)
        if not ok:
            status_code = 403 if reason == "user_blocked" else 401
            return JSONResponse(
                status_code=status_code,
                content={
                    "authenticated": False,
                    "reason": reason,
                    "user": user,
                },
            )

        forwarded_host = (request.headers.get("x-forwarded-host") or "").split(",")[0].split(":")[0].strip().lower()
        if forwarded_host and store.resolve_destination(forwarded_host):
            authz = store.authorize_access(user["id"], forwarded_host)
            if not authz["authorized"]:
                return JSONResponse(
                    status_code=403,
                    content={
                        "authenticated": False,
                        "reason": authz["reason"],
                        "destination": forwarded_host,
                        "user": user,
                    },
                )

        return JSONResponse(
            status_code=200,
            content={
                "authenticated": True,
                "realm": "atius-sovereign",
                "user": user,
            },
        )

    @app.post("/v1/token/generate")
    def generate_token(payload: TokenGenerateRequest, request: Request, response: Response) -> JSONResponse:
        ident = (payload.email or payload.username or payload.login or "").strip()
        secret = payload.password if payload.password is not None else payload.senha
        if not ident:
            raise HTTPException(status_code=400, detail="username or email is required")
        user_check = store.find_user(ident)
        if user_check and (user_check.get("blocked") or user_check.get("status") == "blocked"):
            return JSONResponse(
                status_code=403,
                content={"error": "user_blocked", "detail": "User credentials are blocked by IAM policy"},
            )
        try:
            token, user = store.issue_token(ident, password=secret, force_issue=False)
        except PermissionError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc

        res = JSONResponse(
            status_code=200,
            content={
                "access_token": token,
                "token_type": "bearer",
                "realm": "atius-sovereign",
                "user": user,
            },
        )
        forwarded_host = (request.headers.get("x-forwarded-host") or request.headers.get("host") or "").split(",")[0].split(":")[0].strip().lower()
        cookie_domain: Optional[str] = None
        if forwarded_host.endswith(".atius.com.br"):
            cookie_domain = ".atius.com.br"
        elif forwarded_host.endswith(".atius.io"):
            cookie_domain = forwarded_host

        res.set_cookie(
            key="auth-token",
            value=token,
            domain=cookie_domain,
            httponly=True,
            secure=True,
            samesite="lax",
            path="/",
        )
        return res

    @app.post("/api/sso/logout")
    def sso_logout(
        request: Request,
        authorization: Optional[str] = Header(default=None),
    ) -> JSONResponse:
        token = _extract_token(request, authorization)
        if token:
            store.revoke_token(token)
        res = JSONResponse(status_code=200, content={"ok": True, "logged_out": True})
        res.delete_cookie("auth-token", path="/")
        return res

    # -------------------------------------------------------------------------
    # IAM Access Controller Endpoints (Users, Roles/Personas, Destinations, RBAC)
    # -------------------------------------------------------------------------
    @app.get("/api/v1/iam/summary")
    def get_iam_summary() -> Dict[str, Any]:
        store._load_if_changed()
        users = list(store.users.values())
        active_count = sum(1 for u in users if not u.get("blocked") and u.get("status") != "blocked")
        blocked_count = len(users) - active_count
        role_counts: Dict[str, int] = {r: 0 for r in store.roles}
        for u in users:
            r = u.get("role", "Viewer")
            role_counts[r] = role_counts.get(r, 0) + 1
        return {
            "realm": "atius-sovereign",
            "sso_portal": "https://sso.atius.io",
            "sso_upstream": f"http://127.0.0.1:{CANONICAL_SSO_GATEWAY_PORT}",
            "control_plane_portal": "https://admin.atius.io",
            "control_plane_upstream": f"http://127.0.0.1:{CANONICAL_CONTROL_PLANE_PORT}",
            "total_users": len(users),
            "active_users": active_count,
            "blocked_users": blocked_count,
            "roles_distribution": role_counts,
            "total_roles": len(store.roles),
            "total_destinations": len(store.destinations),
            "audit_events_count": len(store.audit_logs),
        }

    @app.get("/api/v1/iam/users")
    def list_iam_users(
        q: Optional[str] = Query(default=None, description="9-Tier accent-folding & CPF/CNPJ search query"),
        role: Optional[str] = Query(default=None),
        status: Optional[str] = Query(default=None),
    ) -> Dict[str, Any]:
        items = store.list_users(query=q, role=role, status=status)
        return {
            "users": items,
            "total": len(items),
            "query": q or "",
        }

    @app.get("/api/v1/iam/users/{user_id}")
    def get_iam_user(user_id: str) -> Dict[str, Any]:
        user = store.find_user(user_id)
        if not user:
            raise HTTPException(status_code=404, detail=f"User '{user_id}' not found")
        return {"user": store.sanitize_user(user)}

    @app.post("/api/v1/iam/users", status_code=201)
    def create_iam_user(payload: UserCreateRequest) -> Dict[str, Any]:
        try:
            created = store.create_user(payload.model_dump(exclude_none=True))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        tok = store._make_deterministic_token(created["id"], created["email"])
        return {"user": created, "token": tok}

    @app.patch("/api/v1/iam/users/{user_id}")
    @app.put("/api/v1/iam/users/{user_id}")
    def update_iam_user(user_id: str, payload: UserUpdateRequest) -> Dict[str, Any]:
        try:
            updated = store.update_user(user_id, payload.model_dump(exclude_none=True))
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"user": updated}

    @app.post("/api/v1/iam/users/{user_id}/block")
    def block_iam_user(user_id: str, payload: Optional[BlockUserRequest] = None) -> Dict[str, Any]:
        req = payload or BlockUserRequest()
        try:
            updated = store.set_user_blocked(user_id, blocked=True, reason=req.reason, actor=req.actor)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return {"user": updated, "blocked": True}

    @app.post("/api/v1/iam/users/{user_id}/unblock")
    def unblock_iam_user(user_id: str, payload: Optional[BlockUserRequest] = None) -> Dict[str, Any]:
        req = payload or BlockUserRequest(reason="Administrative unblock")
        try:
            updated = store.set_user_blocked(user_id, blocked=False, reason=req.reason, actor=req.actor)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return {"user": updated, "blocked": False}

    @app.get("/api/v1/iam/roles")
    def list_iam_roles() -> Dict[str, Any]:
        store._load_if_changed()
        return {
            "roles": list(store.roles.values()),
            "total": len(store.roles),
        }

    @app.put("/api/v1/iam/roles/{role_name}")
    def update_iam_role(role_name: str, payload: RoleUpdateRequest) -> Dict[str, Any]:
        try:
            updated = store.update_role(role_name, payload.model_dump(exclude_none=True))
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return {"role": updated}

    @app.get("/api/v1/iam/destinations")
    def list_iam_destinations(q: Optional[str] = Query(default=None)) -> Dict[str, Any]:
        store._load_if_changed()
        items = list(store.destinations.values())
        if q and q.strip():
            items = rank_records(
                items,
                query=q,
                text_fields=("host", "name", "category", "description", "upstream", "aliases"),
                doc_fields=(),
            )
        return {
            "destinations": items,
            "total": len(items),
            "query": q or "",
        }

    @app.put("/api/v1/iam/destinations/{destination_id}")
    def update_iam_destination(destination_id: str, payload: DestinationUpdateRequest) -> Dict[str, Any]:
        try:
            updated = store.update_destination(destination_id, payload.model_dump(exclude_none=True))
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"destination": updated}

    @app.post("/api/v1/iam/authorize")
    def evaluate_iam_authorization(
        payload: AuthorizeRequest,
        request: Request,
        authorization: Optional[str] = Header(default=None),
    ) -> JSONResponse:
        subject = payload.token or payload.user or _extract_token(request, authorization)
        result = store.authorize_access(
            user_or_token=subject,
            destination=payload.destination,
            required_permission=payload.permission,
        )
        return JSONResponse(status_code=result["status_code"], content=result)

    @app.get("/api/v1/iam/audit")
    def list_iam_audit(limit: int = Query(default=50, ge=1, le=500)) -> Dict[str, Any]:
        store._load_if_changed()
        return {
            "audit_logs": store.audit_logs[:limit],
            "total": len(store.audit_logs),
        }

    # -------------------------------------------------------------------------
    # Protected Control-Plane Action Endpoint (Requires Admin or Operator)
    # -------------------------------------------------------------------------
    @app.post("/api/v1/control-plane/execute")
    def execute_control_plane_action(
        payload: ControlPlaneActionRequest,
        request: Request,
        authorization: Optional[str] = Header(default=None),
    ) -> JSONResponse:
        token = _extract_token(request, authorization)
        authz = store.authorize_access(
            user_or_token=token,
            destination="admin.atius.io",
            required_permission="control_plane:operate",
        )
        if not authz["authorized"]:
            return JSONResponse(
                status_code=authz["status_code"],
                content={
                    "executed": False,
                    "error": authz["reason"],
                    "destination": "admin.atius.io",
                    "required_permission": "control_plane:operate",
                },
            )

        actor = authz["user"]["email"]
        audit_entry = store._record_audit(
            actor=actor,
            action=f"control_plane.{payload.action}",
            target=payload.target_host,
            details=payload.parameters,
        )
        return JSONResponse(
            status_code=200,
            content={
                "executed": True,
                "action": payload.action,
                "target_host": payload.target_host,
                "operator": actor,
                "role": authz["user"]["role"],
                "control_plane_port": CANONICAL_CONTROL_PLANE_PORT,
                "audit_id": audit_entry["id"],
            },
        )

    # -------------------------------------------------------------------------
    # Frontend SPA Routes (/, /iam, /login)
    # -------------------------------------------------------------------------
    @app.get("/", response_class=HTMLResponse)
    @app.get("/iam", response_class=HTMLResponse)
    @app.get("/login", response_class=HTMLResponse)
    def serve_spa() -> Response:
        index_file = FRONTEND_DIR / "index.html"
        if index_file.exists():
            return FileResponse(index_file, media_type="text/html; charset=utf-8")
        return HTMLResponse(
            "<!doctype html><html lang='pt-BR'><head><title>ATIUS Control-Plane</title></head>"
            "<body><main><h1>ATIUS Omni Control-Plane (:34805) & SSO IAM (:8015)</h1></main></body></html>"
        )

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=DEFAULT_BIND_HOST, port=DEFAULT_CONTROL_PLANE_PORT)
