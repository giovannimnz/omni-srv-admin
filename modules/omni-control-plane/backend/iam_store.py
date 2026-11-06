"""
Keycloak SSO IAM Store & Omni Control-Plane Fleet State Engine.
Provides unified user management, RBAC roles/personas (Admin, Operator, Viewer, Partner),
granular permission matrices, dynamic destination mappings, token lifecycle, and audit logging.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import tempfile
import threading
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .search import rank_records

CANONICAL_CONTROL_PLANE_PORT = 34805
CANONICAL_SSO_GATEWAY_PORT = 8015
CANONICAL_EDGE_GATEWAY_PORT = 8210
CANONICAL_COCKPIT_PORT = 9090
CANONICAL_STORAGE_PORT = 8085


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash_password(password: str, salt: str = "atius-iam-v1") -> str:
    return hashlib.sha256(f"{salt}:{password}".encode("utf-8")).hexdigest()


DEFAULT_ROLES: Dict[str, Dict[str, Any]] = {
    "Admin": {
        "name": "Admin",
        "slug": "admin",
        "label": "Administrador Soberano (Full IAM & Infra)",
        "description": "Acesso irrestrito ao Control-Plane (:34805), Keycloak SSO (:8015), Cockpit PAM (:9090), Storage (:8085), OCI DRG e todos os destinos ATIUS.",
        "level": 100,
        "is_admin": True,
        "permissions": [
            "*",
            "iam:users:read",
            "iam:users:write",
            "iam:users:block",
            "iam:roles:manage",
            "iam:destinations:manage",
            "iam:audit:read",
            "control_plane:read",
            "control_plane:operate",
            "fleet:read",
            "fleet:operate",
            "cockpit:access",
            "storage:read",
            "storage:manage",
            "trade:execute",
            "backtest:execute",
        ],
        "default_destinations": ["*"],
    },
    "Operator": {
        "name": "Operator",
        "slug": "operator",
        "label": "Operador de Infraestrutura & DevOps",
        "description": "Operação do Omni Control-Plane (:34805), Storage & Backups (:8085), Landscape, Paseo, Plane e PM2, sem permissão de mutação de IAM soberano ou Cockpit root.",
        "level": 70,
        "is_admin": False,
        "permissions": [
            "iam:users:read",
            "iam:audit:read",
            "control_plane:read",
            "control_plane:operate",
            "fleet:read",
            "fleet:operate",
            "storage:read",
            "storage:manage",
            "trade:execute",
            "backtest:execute",
        ],
        "default_destinations": [
            "admin.atius.io",
            "admin.atius.com.br",
            "omni.atius.io",
            "omni.atius.com.br",
            "storage.atius.io",
            "storage.atius.com.br",
            "backup.atius.io",
            "backup.atius.com.br",
            "landscape.atius.io",
            "landscape.atius.com.br",
            "paseo.atius.io",
            "paseo.atius.com.br",
            "plane.atius.io",
            "plane.atius.com.br",
            "pm2.atius.io",
            "pm2.atius.com.br",
            "grafana.atius.io",
            "grafana.atius.com.br",
            "dashboard.atius.io",
            "dashboard.atius.com.br",
        ],
    },
    "Viewer": {
        "name": "Viewer",
        "slug": "viewer",
        "label": "Observador & Auditoria Read-Only",
        "description": "Visualização de métricas, dashboards, relatórios de backup (:8085) e topologia sem permissão de mutação ou execução.",
        "level": 30,
        "is_admin": False,
        "permissions": [
            "control_plane:read",
            "fleet:read",
            "storage:read",
        ],
        "default_destinations": [
            "storage.atius.io",
            "storage.atius.com.br",
            "dashboard.atius.io",
            "dashboard.atius.com.br",
            "painel.atius.io",
            "painel.atius.com.br",
            "plane.atius.io",
            "plane.atius.com.br",
        ],
    },
    "Partner": {
        "name": "Partner",
        "slug": "partner",
        "label": "Parceiro Externo & Mesa Quantitativa",
        "description": "Acesso escopado exclusivamente aos terminais operacionais autorizados (Trade, Backtest, Strategy, Remote MT5), bloqueado em painéis administrativos.",
        "level": 20,
        "is_admin": False,
        "permissions": [
            "partner:portal",
            "trade:execute",
            "backtest:execute",
        ],
        "default_destinations": [
            "trade.atius.io",
            "trade.atius.com.br",
            "backtest.atius.io",
            "backtest.atius.com.br",
            "strategy.atius.io",
            "strategy.atius.com.br",
            "remote.atius.io",
            "remote.atius.com.br",
            "dashboard.atius.io",
            "dashboard.atius.com.br",
        ],
    },
}


DEFAULT_DESTINATIONS: List[Dict[str, Any]] = [
    {
        "id": "sso.atius.io",
        "host": "sso.atius.io",
        "aliases": ["sso.atius.com.br"],
        "name": "Atius SSO IAM & Keycloak Gateway",
        "category": "IAM & Security",
        "upstream": f"http://127.0.0.1:{CANONICAL_SSO_GATEWAY_PORT}",
        "port": CANONICAL_SSO_GATEWAY_PORT,
        "edge_port": CANONICAL_EDGE_GATEWAY_PORT,
        "allowed_roles": ["Admin"],
        "required_permission": "iam:users:read",
        "auth_mode": "keycloak-sso-iam",
        "description": "Central soberana de governança de identidade, usuários, perfis RBAC e mapeamento de destinos.",
    },
    {
        "id": "admin.atius.io",
        "host": "admin.atius.io",
        "aliases": ["admin.atius.com.br", "omni.atius.io", "omni.atius.com.br"],
        "name": "Omni Control-Plane FastAPI",
        "category": "Control-Plane",
        "upstream": f"http://127.0.0.1:{CANONICAL_CONTROL_PLANE_PORT}",
        "port": CANONICAL_CONTROL_PLANE_PORT,
        "edge_port": CANONICAL_EDGE_GATEWAY_PORT,
        "allowed_roles": ["Admin", "Operator"],
        "required_permission": "control_plane:read",
        "auth_mode": "edge-sso",
        "description": "Control-Plane centralizado da infraestrutura ATIUS na porta canônica 34805 (zero colisão com Cockpit :9090).",
    },
    {
        "id": "cockpit.atius.io",
        "host": "cockpit.atius.io",
        "aliases": ["cockpit.atius.com.br"],
        "name": "Host Linux Cockpit PAM Console",
        "category": "Host OS",
        "upstream": f"http://127.0.0.1:{CANONICAL_COCKPIT_PORT}",
        "port": CANONICAL_COCKPIT_PORT,
        "edge_port": CANONICAL_EDGE_GATEWAY_PORT,
        "allowed_roles": ["Admin"],
        "required_permission": "cockpit:access",
        "auth_mode": "pam-passthrough",
        "description": "Console administrativo Linux nativo via PAM em :9090 isolado do Omni Control-Plane.",
    },
    {
        "id": "storage.atius.io",
        "host": "storage.atius.io",
        "aliases": ["storage.atius.com.br", "backup.atius.io", "backup.atius.com.br"],
        "name": "Atius Storage & Backup Control",
        "category": "Atius Storage",
        "upstream": f"http://10.14.1.14:{CANONICAL_STORAGE_PORT}",
        "port": CANONICAL_STORAGE_PORT,
        "edge_port": CANONICAL_EDGE_GATEWAY_PORT,
        "allowed_roles": ["Admin", "Operator", "Viewer"],
        "required_permission": "storage:read",
        "auth_mode": "edge-sso",
        "description": "Painel de retenção GDrive RClone, quotas VFS e dumps PostgreSQL na porta 8085.",
    },
    {
        "id": "landscape.atius.io",
        "host": "landscape.atius.io",
        "aliases": ["landscape.atius.com.br"],
        "name": "Canonical Landscape Omni Cluster Server",
        "category": "Omni Cluster Governance",
        "upstream": "https://10.3.1.1:443",
        "port": 443,
        "edge_port": CANONICAL_EDGE_GATEWAY_PORT,
        "allowed_roles": ["Admin", "Operator"],
        "required_permission": "fleet:operate",
        "auth_mode": "edge-sso",
        "description": "Gerenciamento de pacotes, scripts e auditoria de conformidade dos nós Ubuntu da frota.",
    },
    {
        "id": "paseo.atius.io",
        "host": "paseo.atius.io",
        "aliases": ["paseo.atius.com.br"],
        "name": "Paseo AI Agent Runtime",
        "category": "AI Runtime",
        "upstream": "http://10.14.1.14:37845",
        "port": 37845,
        "edge_port": CANONICAL_EDGE_GATEWAY_PORT,
        "allowed_roles": ["Admin", "Operator"],
        "required_permission": "control_plane:operate",
        "auth_mode": "edge-sso",
        "description": "Orquestrador de agentes autônomos e sessões distribuídas Paseo.",
    },
    {
        "id": "plane.atius.io",
        "host": "plane.atius.io",
        "aliases": ["plane.atius.com.br"],
        "name": "Plane Project Management",
        "category": "Product & Engineering",
        "upstream": "http://127.0.0.1:8091",
        "port": 8091,
        "edge_port": CANONICAL_EDGE_GATEWAY_PORT,
        "allowed_roles": ["Admin", "Operator", "Viewer"],
        "required_permission": "fleet:read",
        "auth_mode": "edge-sso",
        "description": "Gestão de sprints, issues, roadmaps e ciclos de engenharia ATIUS.",
    },
    {
        "id": "remote.atius.io",
        "host": "remote.atius.io",
        "aliases": ["remote.atius.com.br"],
        "name": "Atius Remote MT5 Terminal",
        "category": "Trading Infrastructure",
        "upstream": "http://127.0.0.1:8095",
        "port": 8095,
        "edge_port": CANONICAL_EDGE_GATEWAY_PORT,
        "allowed_roles": ["Admin", "Operator", "Partner"],
        "required_permission": "trade:execute",
        "auth_mode": "edge-sso",
        "description": "Sessão remota de baixa latência para execução MT5 via WebSocket/noVNC.",
    },
    {
        "id": "dashboard.atius.io",
        "host": "dashboard.atius.io",
        "aliases": ["dashboard.atius.com.br", "painel.atius.io", "painel.atius.com.br"],
        "name": "ATS Quantitative Dashboard",
        "category": "Trading Analytics",
        "upstream": "http://127.0.0.1:3040",
        "port": 3040,
        "edge_port": CANONICAL_EDGE_GATEWAY_PORT,
        "allowed_roles": ["Admin", "Operator", "Viewer", "Partner"],
        "required_permission": None,
        "auth_mode": "app-local-pm2",
        "description": "Painel analítico de performance, carteiras e telemetria ATS.",
    },
    {
        "id": "trade.atius.io",
        "host": "trade.atius.io",
        "aliases": ["trade.atius.com.br", "backtest.atius.io", "backtest.atius.com.br", "strategy.atius.io", "strategy.atius.com.br"],
        "name": "ATS Execution & Backtest Suite",
        "category": "Trading Execution",
        "upstream": "http://127.0.0.1:3040",
        "port": 3040,
        "edge_port": CANONICAL_EDGE_GATEWAY_PORT,
        "allowed_roles": ["Admin", "Operator", "Partner"],
        "required_permission": "trade:execute",
        "auth_mode": "app-local-pm2",
        "description": "Plataforma de execução de ordens, simulação quantitativa e estratégias.",
    },
]


DEFAULT_FLEET_NODES: List[Dict[str, Any]] = [
    {
        "hostname": "atius-srv-1",
        "oci_profile": "atius1",
        "vcn_cidr": "10.1.0.0/16",
        "subnet_cidr": "10.1.0.0/16",
        "private_ip": "10.1.1.1",
        "gateway_ip": "10.1.0.1",
        "dns_ip": "10.1.0.2",
        "network_model": "single-vcn-single-vnic",
        "role": "Primary Ingress, Edge SSO (:8210), Keycloak IAM (:8015), Omni Control-Plane (:34805), PostgreSQL/PgBouncer",
        "status": "online",
    },
    {
        "hostname": "atius-srv-2",
        "oci_profile": "atius2",
        "vcn_cidr": "10.2.0.0/16",
        "subnet_cidr": "10.2.0.0/16",
        "private_ip": "10.2.1.1",
        "gateway_ip": "10.2.0.1",
        "dns_ip": "10.2.0.2",
        "network_model": "single-vcn-single-vnic",
        "role": "Application Runtime, Portainer (:9443), GBrain & Obsidian MCP Bridge",
        "status": "online",
    },
    {
        "hostname": "atius-srv-3",
        "oci_profile": "atius3",
        "vcn_cidr": "10.3.0.0/16",
        "subnet_cidr": "10.3.0.0/16",
        "private_ip": "10.3.1.1",
        "gateway_ip": "10.3.0.1",
        "dns_ip": "10.3.0.2",
        "network_model": "single-vcn-single-vnic",
        "role": "HashiCorp Vault (:8202), Canonical Landscape Server, Grafana (:3005)",
        "status": "online",
    },
    {
        "hostname": "atius-srv-4",
        "oci_profile": "atius4",
        "vcn_cidr": "10.4.0.0/16",
        "subnet_cidr": "10.4.0.0/16",
        "private_ip": "10.4.1.1",
        "gateway_ip": "10.4.0.1",
        "dns_ip": "10.4.0.2",
        "network_model": "single-vcn-single-vnic",
        "role": "Atius Storage Hub & Backup Web (:8085), RClone GDrive Offload, Paseo Runtime (:37845)",
        "status": "online",
    },
    {
        "hostname": "horistic-srv",
        "oci_profile": "horistic",
        "vcn_cidr": "10.51.0.0/16",
        "subnet_cidr": "10.51.0.0/16",
        "private_ip": "10.51.1.1",
        "gateway_ip": "10.51.0.1",
        "dns_ip": "10.51.0.2",
        "network_model": "single-vcn-single-vnic",
        "role": "Horistic Partner Ingress & DRG Private Proxy",
        "status": "online",
    },
    {
        "hostname": "aln-srv",
        "oci_profile": "alnrec",
        "vcn_cidr": "10.52.0.0/16",
        "subnet_cidr": "10.52.0.0/16",
        "private_ip": "10.52.1.1",
        "gateway_ip": "10.52.0.1",
        "dns_ip": "10.52.0.2",
        "network_model": "single-vcn-single-vnic",
        "role": "ALN Partner Node via OCI Central DRG",
        "status": "online",
    },
]


DEFAULT_USERS: List[Dict[str, Any]] = [
    {
        "id": "usr-giovanni-admin",
        "email": "giovanni@atius.io",
        "username": "giovanni",
        "name": "Giovanni Muniz",
        "email_aliases": [
            "giovanni.muniz@atius.io",
            "admin.atius@gmail.com",
            "giovannimunizds@gmail.com",
            "holding.atius@gmail.com",
        ],
        "role": "Admin",
        "roles": ["Admin"],
        "is_admin": True,
        "status": "active",
        "blocked": False,
        "mfa_enabled": True,
        "keycloak_realm": "atius-sovereign",
        "cpf": "111.222.333-44",
        "cnpj": "12.345.678/0001-90",
        "document": "11122233344",
        "custom_permissions": ["*"],
        "allowed_destinations": ["*"],
        "denied_destinations": [],
        "password_hash": _hash_password("AtiusSovereign#2026"),
        "created_at": "2026-11-01T00:00:00+00:00",
        "updated_at": "2026-11-06T00:00:00+00:00",
    },
    {
        "id": "usr-livia-operator",
        "email": "livia.nascimento@atius.io",
        "username": "livia.operator",
        "name": "Lívia Nascimento",
        "email_aliases": ["livia@atius.io"],
        "role": "Operator",
        "roles": ["Operator"],
        "is_admin": False,
        "status": "active",
        "blocked": False,
        "mfa_enabled": True,
        "keycloak_realm": "atius-sovereign",
        "cpf": "555.666.777-88",
        "cnpj": "",
        "document": "55566677788",
        "custom_permissions": ["control_plane:read", "control_plane:operate", "storage:read"],
        "allowed_destinations": [
            "admin.atius.io",
            "admin.atius.com.br",
            "storage.atius.io",
            "storage.atius.com.br",
            "landscape.atius.io",
            "paseo.atius.io",
        ],
        "denied_destinations": ["cockpit.atius.io", "sso.atius.io"],
        "password_hash": _hash_password("OperatorAtius#2026"),
        "created_at": "2026-11-02T00:00:00+00:00",
        "updated_at": "2026-11-06T00:00:00+00:00",
    },
    {
        "id": "usr-carlos-viewer",
        "email": "carlos.auditor@atius.io",
        "username": "carlos.viewer",
        "name": "Carlos Mendonça",
        "email_aliases": ["carlos@atius.io"],
        "role": "Viewer",
        "roles": ["Viewer"],
        "is_admin": False,
        "status": "active",
        "blocked": False,
        "mfa_enabled": False,
        "keycloak_realm": "atius-sovereign",
        "cpf": "999.888.777-66",
        "cnpj": "",
        "document": "99988877766",
        "custom_permissions": ["storage:read", "fleet:read"],
        "allowed_destinations": [
            "storage.atius.io",
            "storage.atius.com.br",
            "dashboard.atius.io",
            "painel.atius.io",
        ],
        "denied_destinations": ["admin.atius.io", "sso.atius.io", "cockpit.atius.io"],
        "password_hash": _hash_password("ViewerAtius#2026"),
        "created_at": "2026-11-03T00:00:00+00:00",
        "updated_at": "2026-11-06T00:00:00+00:00",
    },
    {
        "id": "usr-julio-partner",
        "email": "julio@atius.io",
        "username": "julio",
        "name": "Julio Gambarra",
        "email_aliases": ["julio.gambarra@atius.io", "jcgambarra2013@gmail.com"],
        "role": "Partner",
        "roles": ["Partner"],
        "is_admin": False,
        "status": "active",
        "blocked": False,
        "mfa_enabled": True,
        "keycloak_realm": "atius-sovereign",
        "cpf": "",
        "cnpj": "",
        "document": "",
        "custom_permissions": ["partner:portal", "trade:execute", "backtest:execute", "strategy:read"],
        "allowed_destinations": [
            "dashboard.atius.io",
            "dashboard.atius.com.br",
            "painel.atius.io",
            "painel.atius.com.br",
            "trade.atius.io",
            "trade.atius.com.br",
            "backtest.atius.io",
            "backtest.atius.com.br",
            "strategy.atius.io",
            "strategy.atius.com.br",
            "remote.atius.io",
            "remote.atius.com.br",
        ],
        "denied_destinations": [
            "admin.atius.io",
            "admin.atius.com.br",
            "cockpit.atius.io",
            "cockpit.atius.com.br",
            "landscape.atius.io",
            "landscape.atius.com.br",
            "vault.atius.io",
            "vault.atius.com.br",
            "storage.atius.io",
            "storage.atius.com.br",
        ],
        "password_hash": _hash_password("PartnerAtius#2026"),
        "created_at": "2026-11-06T00:00:00+00:00",
        "updated_at": "2026-11-06T00:00:00+00:00",
    },
    {
        "id": "usr-diego-partner",
        "email": "diego@atius.io",
        "username": "diego",
        "name": "Diego Carvalho",
        "email_aliases": ["diego.carvalho@atius.io", "diegopolaroid01@gmail.com", "parceiro.quant@horistic.com"],
        "role": "Partner",
        "roles": ["Partner"],
        "is_admin": False,
        "status": "active",
        "blocked": False,
        "mfa_enabled": True,
        "keycloak_realm": "atius-sovereign",
        "cpf": "321.654.987-00",
        "cnpj": "45.678.912/0001-33",
        "document": "32165498700",
        "custom_permissions": ["partner:portal", "trade:execute", "backtest:execute", "strategy:read"],
        "allowed_destinations": [
            "dashboard.atius.io",
            "dashboard.atius.com.br",
            "painel.atius.io",
            "painel.atius.com.br",
            "trade.atius.io",
            "trade.atius.com.br",
            "backtest.atius.io",
            "backtest.atius.com.br",
            "strategy.atius.io",
            "strategy.atius.com.br",
            "remote.atius.io",
            "remote.atius.com.br",
        ],
        "denied_destinations": [
            "admin.atius.io",
            "admin.atius.com.br",
            "cockpit.atius.io",
            "cockpit.atius.com.br",
            "landscape.atius.io",
            "landscape.atius.com.br",
            "vault.atius.io",
            "vault.atius.com.br",
            "storage.atius.io",
            "storage.atius.com.br",
        ],
        "password_hash": _hash_password("PartnerAtius#2026"),
        "created_at": "2026-11-04T00:00:00+00:00",
        "updated_at": "2026-11-06T00:00:00+00:00",
    },
]


class IAMControlPlaneStore:
    """In-memory and file-persisted IAM & Control-Plane Store with cross-process sync."""

    def __init__(self, state_file: Optional[Path] = None, secret_key: Optional[str] = None) -> None:
        self._lock = threading.RLock()
        env_state = os.environ.get("ATIUS_IAM_STATE_FILE", "").strip()
        if state_file is not None:
            self.state_file: Optional[Path] = Path(state_file)
        elif env_state:
            self.state_file = Path(env_state)
        else:
            self.state_file = None
        self._last_mtime_ns: int = -1
        self.secret_key = secret_key or os.environ.get("ATIUS_IAM_SECRET_KEY", "atius-sovereign-iam-secret-key-2026")
        self.roles: Dict[str, Dict[str, Any]] = deepcopy(DEFAULT_ROLES)
        self.destinations: Dict[str, Dict[str, Any]] = {
            d["host"]: deepcopy(d) for d in DEFAULT_DESTINATIONS
        }
        self.users: Dict[str, Dict[str, Any]] = {
            u["id"]: deepcopy(u) for u in DEFAULT_USERS
        }
        self.tokens: Dict[str, Dict[str, Any]] = {}
        self.audit_logs: List[Dict[str, Any]] = []
        self._seed_default_tokens()
        self._record_audit("system", "iam.initialized", "sso.atius.io", {"port_control_plane": CANONICAL_CONTROL_PLANE_PORT, "port_sso": CANONICAL_SSO_GATEWAY_PORT})
        if self.state_file and self.state_file.exists():
            self._load()

    def _seed_default_tokens(self) -> None:
        for uid, user in self.users.items():
            tok = self._make_deterministic_token(uid, user["email"])
            if tok not in self.tokens:
                self.tokens[tok] = {
                    "token": tok,
                    "user_id": uid,
                    "email": user["email"],
                    "issued_at": utc_now_iso(),
                    "revoked": False,
                }

    def _make_deterministic_token(self, user_id: str, email: str) -> str:
        digest = hmac.new(
            self.secret_key.encode("utf-8"),
            f"{user_id}:{email}".encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()[:32]
        return f"atius_iam_{user_id}_{digest}"

    def _load_if_changed(self) -> None:
        if not self.state_file or not self.state_file.exists():
            return
        with self._lock:
            try:
                mtime_ns = self.state_file.stat().st_mtime_ns
                if mtime_ns != self._last_mtime_ns:
                    self._load()
            except OSError:
                pass

    def _load(self) -> None:
        if not self.state_file or not self.state_file.exists():
            return
        with self._lock:
            try:
                raw = json.loads(self.state_file.read_text(encoding="utf-8"))
                if isinstance(raw.get("roles"), dict):
                    self.roles = raw["roles"]
                if isinstance(raw.get("destinations"), dict):
                    self.destinations = raw["destinations"]
                if isinstance(raw.get("users"), dict):
                    self.users = raw["users"]
                if isinstance(raw.get("tokens"), dict):
                    self.tokens = raw["tokens"]
                if isinstance(raw.get("audit_logs"), list):
                    self.audit_logs = raw["audit_logs"]
                self._seed_default_tokens()
                self._last_mtime_ns = self.state_file.stat().st_mtime_ns
            except Exception:
                pass

    def _save(self) -> None:
        if not self.state_file:
            return
        with self._lock:
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "roles": self.roles,
                "destinations": self.destinations,
                "users": self.users,
                "tokens": self.tokens,
                "audit_logs": self.audit_logs[-500:],
            }
            serialized = json.dumps(payload, indent=2, ensure_ascii=False)
            tmp_file = self.state_file.parent / f".{self.state_file.name}.{os.getpid()}.{threading.get_ident()}.tmp"
            tmp_file.write_text(serialized, encoding="utf-8")
            os.replace(tmp_file, self.state_file)
            try:
                self._last_mtime_ns = self.state_file.stat().st_mtime_ns
            except OSError:
                pass

    def _record_audit(self, actor: str, action: str, target: str, details: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        with self._lock:
            entry = {
                "id": f"aud-{len(self.audit_logs) + 1:04d}",
                "timestamp": utc_now_iso(),
                "actor": actor,
                "action": action,
                "target": target,
                "details": details or {},
            }
            self.audit_logs.insert(0, entry)
            return entry

    def canonical_role_name(self, role_input: str) -> str:
        cleaned = str(role_input or "").strip()
        for rname in self.roles:
            if rname.lower() == cleaned.lower():
                return rname
        raise ValueError(f"Invalid role/persona '{role_input}'. Valid roles: {list(self.roles.keys())}")

    def resolve_destination(self, host_or_id: str) -> Optional[Dict[str, Any]]:
        self._load_if_changed()
        cleaned = str(host_or_id or "").strip().lower()
        if not cleaned:
            return None
        if cleaned in self.destinations:
            return self.destinations[cleaned]
        for dest in self.destinations.values():
            if dest["id"].lower() == cleaned or cleaned in [a.lower() for a in dest.get("aliases", [])]:
                return dest
        return None

    def compute_effective_access(self, user: Dict[str, Any]) -> Dict[str, Any]:
        """Compute effective permissions and authorized destinations for a user."""
        user_roles = user.get("roles") or ([user["role"]] if user.get("role") else [])
        effective_perms: List[str] = []
        role_destinations: List[str] = []
        is_admin = bool(user.get("is_admin", False))

        for rname in user_roles:
            role_obj = None
            for k, v in self.roles.items():
                if k.lower() == str(rname).lower():
                    role_obj = v
                    break
            if role_obj:
                if role_obj.get("is_admin"):
                    is_admin = True
                for p in role_obj.get("permissions", []):
                    if p not in effective_perms:
                        effective_perms.append(p)
                for d in role_obj.get("default_destinations", []):
                    if d not in role_destinations:
                        role_destinations.append(d)

        for cp in user.get("custom_permissions", []):
            if cp not in effective_perms:
                effective_perms.append(cp)

        explicit_allowed = user.get("allowed_destinations")
        if isinstance(explicit_allowed, list) and len(explicit_allowed) > 0:
            merged_dests = list(dict.fromkeys(explicit_allowed))
        else:
            merged_dests = list(dict.fromkeys(role_destinations))

        denied_set = {str(d).lower() for d in user.get("denied_destinations", [])}
        if "*" not in merged_dests:
            expanded: List[str] = []
            for d in merged_dests:
                d_low = str(d).lower()
                if d_low in denied_set:
                    continue
                if d not in expanded:
                    expanded.append(d)
                dest_obj = self.resolve_destination(d)
                if dest_obj:
                    for cand in [dest_obj["host"]] + list(dest_obj.get("aliases", [])):
                        if cand.lower() not in denied_set and cand not in expanded:
                            expanded.append(cand)
            merged_dests = expanded

        permissions_map = {p: True for p in effective_perms}
        return {
            "is_admin": is_admin,
            "roles": user_roles,
            "primary_role": user_roles[0] if user_roles else "Viewer",
            "permissions": effective_perms,
            "permissions_map": permissions_map,
            "allowed_destinations": merged_dests,
            "denied_destinations": list(denied_set),
        }

    def sanitize_user(self, user: Dict[str, Any]) -> Dict[str, Any]:
        eff = self.compute_effective_access(user)
        out = {k: deepcopy(v) for k, v in user.items() if k != "password_hash"}
        out["is_admin"] = eff["is_admin"]
        out["role"] = eff["primary_role"]
        out["roles"] = eff["roles"]
        out["permissions"] = eff["permissions"]
        out["permissions_map"] = eff["permissions_map"]
        out["allowed_destinations"] = eff["allowed_destinations"]
        return out

    def find_user(self, identifier: str) -> Optional[Dict[str, Any]]:
        self._load_if_changed()
        ident = str(identifier or "").strip().lower()
        if not ident:
            return None
        if ident in self.users:
            return self.users[ident]
        for u in self.users.values():
            aliases = [str(a).lower() for a in u.get("email_aliases", [])]
            if (
                u["id"].lower() == ident
                or u["email"].lower() == ident
                or u.get("username", "").lower() == ident
                or ident in aliases
            ):
                return u
        return None

    def list_users(
        self,
        query: Optional[str] = None,
        role: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        self._load_if_changed()
        items = [self.sanitize_user(u) for u in self.users.values()]
        if role:
            role_low = role.strip().lower()
            items = [
                u for u in items
                if u["role"].lower() == role_low or any(r.lower() == role_low for r in u.get("roles", []))
            ]
        if status:
            st_low = status.strip().lower()
            items = [u for u in items if u.get("status", "").lower() == st_low]

        if query and query.strip():
            items = rank_records(
                items,
                query=query,
                text_fields=("name", "email", "username", "email_aliases", "role", "allowed_destinations"),
                doc_fields=("cpf", "cnpj", "document", "rg", "renach"),
            )
        return items

    def create_user(self, payload: Dict[str, Any], actor: str = "admin") -> Dict[str, Any]:
        email = str(payload.get("email") or "").strip().lower()
        name = str(payload.get("name") or "").strip()
        if not email or "@" not in email:
            raise ValueError("Valid email is required")
        if not name:
            raise ValueError("User name is required")
        if self.find_user(email):
            raise ValueError(f"User with email '{email}' already exists")

        raw_aliases = payload.get("email_aliases") or payload.get("aliases") or []
        if isinstance(raw_aliases, str):
            email_aliases = [a.strip().lower() for a in raw_aliases.split(",") if a.strip()]
        else:
            email_aliases = [str(a).strip().lower() for a in raw_aliases if str(a).strip()]

        raw_role = payload.get("role") or (payload.get("roles")[0] if payload.get("roles") else "Viewer")
        canon_role = self.canonical_role_name(raw_role)
        raw_roles = payload.get("roles") or [canon_role]
        canon_roles = [self.canonical_role_name(r) for r in raw_roles]

        uid = payload.get("id") or f"usr-{secrets.token_hex(4)}"
        role_def = self.roles[canon_role]
        blocked = bool(payload.get("blocked", False))
        status = "blocked" if blocked else str(payload.get("status") or "active").lower()
        if status == "blocked":
            blocked = True

        allowed_dests = payload.get("allowed_destinations")
        if allowed_dests is None:
            allowed_dests = deepcopy(role_def["default_destinations"])

        now = utc_now_iso()
        new_user: Dict[str, Any] = {
            "id": uid,
            "email": email,
            "username": str(payload.get("username") or email.split("@")[0]).strip().lower(),
            "name": name,
            "role": canon_role,
            "roles": canon_roles,
            "is_admin": bool(payload.get("is_admin", role_def["is_admin"])),
            "status": status,
            "blocked": blocked,
            "mfa_enabled": bool(payload.get("mfa_enabled", False)),
            "keycloak_realm": str(payload.get("keycloak_realm") or "atius-sovereign"),
            "cpf": str(payload.get("cpf") or ""),
            "cnpj": str(payload.get("cnpj") or ""),
            "document": str(payload.get("document") or payload.get("cpf") or ""),
            "email_aliases": email_aliases,
            "custom_permissions": list(payload.get("custom_permissions") or []),
            "allowed_destinations": list(allowed_dests),
            "denied_destinations": list(payload.get("denied_destinations") or []),
            "password_hash": _hash_password(str(payload.get("password") or "AtiusDefault#2026")),
            "created_at": now,
            "updated_at": now,
        }
        self.users[uid] = new_user
        tok = self._make_deterministic_token(uid, email)
        self.tokens[tok] = {
            "token": tok,
            "user_id": uid,
            "email": email,
            "issued_at": now,
            "revoked": False,
        }
        self._record_audit(actor, "iam.user.created", email, {"user_id": uid, "role": canon_role, "allowed_destinations": new_user["allowed_destinations"]})
        self._save()
        return self.sanitize_user(new_user)

    def update_user(self, user_id: str, payload: Dict[str, Any], actor: str = "admin") -> Dict[str, Any]:
        user = self.find_user(user_id)
        if not user:
            raise KeyError(f"User '{user_id}' not found")

        if "name" in payload and payload["name"]:
            user["name"] = str(payload["name"]).strip()
        if "email" in payload and payload["email"]:
            user["email"] = str(payload["email"]).strip().lower()
        if "email_aliases" in payload:
            raw_aliases = payload["email_aliases"]
            if isinstance(raw_aliases, str):
                user["email_aliases"] = [a.strip().lower() for a in raw_aliases.split(",") if a.strip()]
            elif isinstance(raw_aliases, list):
                user["email_aliases"] = [str(a).strip().lower() for a in raw_aliases if str(a).strip()]
        if "role" in payload and payload["role"]:
            canon_role = self.canonical_role_name(payload["role"])
            user["role"] = canon_role
            if "roles" not in payload:
                user["roles"] = [canon_role]
            user["is_admin"] = bool(self.roles[canon_role]["is_admin"])
        if "roles" in payload and isinstance(payload["roles"], list) and payload["roles"]:
            canon_roles = [self.canonical_role_name(r) for r in payload["roles"]]
            user["roles"] = canon_roles
            user["role"] = canon_roles[0]
            user["is_admin"] = any(self.roles[r]["is_admin"] for r in canon_roles)
        if "is_admin" in payload:
            user["is_admin"] = bool(payload["is_admin"])
        if "allowed_destinations" in payload and isinstance(payload["allowed_destinations"], list):
            user["allowed_destinations"] = [str(d).strip() for d in payload["allowed_destinations"] if str(d).strip()]
        if "denied_destinations" in payload and isinstance(payload["denied_destinations"], list):
            user["denied_destinations"] = [str(d).strip() for d in payload["denied_destinations"] if str(d).strip()]
        if "custom_permissions" in payload and isinstance(payload["custom_permissions"], list):
            user["custom_permissions"] = [str(p).strip() for p in payload["custom_permissions"] if str(p).strip()]
        if "cpf" in payload:
            user["cpf"] = str(payload["cpf"] or "")
        if "cnpj" in payload:
            user["cnpj"] = str(payload["cnpj"] or "")
        if "mfa_enabled" in payload:
            user["mfa_enabled"] = bool(payload["mfa_enabled"])
        if "blocked" in payload:
            user["blocked"] = bool(payload["blocked"])
            user["status"] = "blocked" if user["blocked"] else "active"
        elif "status" in payload:
            st = str(payload["status"]).strip().lower()
            user["status"] = st
            user["blocked"] = st == "blocked"
        if "password" in payload and payload["password"]:
            user["password_hash"] = _hash_password(str(payload["password"]))

        user["updated_at"] = utc_now_iso()
        self._record_audit(actor, "iam.user.updated", user["email"], {"user_id": user["id"], "fields": list(payload.keys())})
        self._save()
        return self.sanitize_user(user)

    def set_user_blocked(self, user_id: str, blocked: bool, reason: str = "", actor: str = "admin") -> Dict[str, Any]:
        user = self.find_user(user_id)
        if not user:
            raise KeyError(f"User '{user_id}' not found")
        user["blocked"] = bool(blocked)
        user["status"] = "blocked" if blocked else "active"
        user["updated_at"] = utc_now_iso()
        action = "iam.user.blocked" if blocked else "iam.user.unblocked"
        self._record_audit(actor, action, user["email"], {"user_id": user["id"], "reason": reason})
        self._save()
        return self.sanitize_user(user)

    def update_role(self, role_name: str, payload: Dict[str, Any], actor: str = "admin") -> Dict[str, Any]:
        canon = self.canonical_role_name(role_name)
        role_obj = self.roles[canon]
        if "description" in payload:
            role_obj["description"] = str(payload["description"])
        if "permissions" in payload and isinstance(payload["permissions"], list):
            role_obj["permissions"] = [str(p).strip() for p in payload["permissions"] if str(p).strip()]
        if "default_destinations" in payload and isinstance(payload["default_destinations"], list):
            role_obj["default_destinations"] = [str(d).strip() for d in payload["default_destinations"] if str(d).strip()]
        self._record_audit(actor, "iam.role.updated", canon, {"fields": list(payload.keys())})
        self._save()
        return deepcopy(role_obj)

    def update_destination(self, host_or_id: str, payload: Dict[str, Any], actor: str = "admin") -> Dict[str, Any]:
        dest = self.resolve_destination(host_or_id)
        if not dest:
            raise KeyError(f"Destination '{host_or_id}' not found")
        if "allowed_roles" in payload and isinstance(payload["allowed_roles"], list):
            dest["allowed_roles"] = [self.canonical_role_name(r) for r in payload["allowed_roles"]]
        if "required_permission" in payload:
            dest["required_permission"] = payload["required_permission"]
        if "upstream" in payload and payload["upstream"]:
            dest["upstream"] = str(payload["upstream"])
        if "description" in payload and payload["description"]:
            dest["description"] = str(payload["description"])
        self._record_audit(actor, "iam.destination.updated", dest["host"], {"fields": list(payload.keys())})
        self._save()
        return deepcopy(dest)

    def issue_token(self, username_or_email: str, password: Optional[str] = None, force_issue: bool = False) -> Tuple[str, Dict[str, Any]]:
        self._load_if_changed()
        user = self.find_user(username_or_email)
        if not user:
            self._record_audit("anonymous", "iam.auth.failed", username_or_email, {"reason": "user_not_found"})
            self._save()
            raise PermissionError("Invalid credentials")

        if user.get("blocked") or user.get("status") == "blocked":
            self._record_audit(user["email"], "iam.auth.refused_blocked", user["email"], {"user_id": user["id"]})
            self._save()
            raise PermissionError("User account is blocked")

        if not force_issue:
            if not password or _hash_password(password) != user.get("password_hash"):
                self._record_audit(user["email"], "iam.auth.failed", user["email"], {"reason": "bad_password"})
                self._save()
                raise PermissionError("Invalid credentials")

        tok = self._make_deterministic_token(user["id"], user["email"])
        self.tokens[tok] = {
            "token": tok,
            "user_id": user["id"],
            "email": user["email"],
            "issued_at": utc_now_iso(),
            "revoked": False,
        }
        self._record_audit(user["email"], "iam.token.issued", user["email"], {"user_id": user["id"], "role": user["role"]})
        self._save()
        return tok, self.sanitize_user(user)

    def revoke_token(self, token: str) -> bool:
        self._load_if_changed()
        cleaned = str(token or "").strip()
        if cleaned.lower().startswith("bearer "):
            cleaned = cleaned[7:].strip()
        if not cleaned or cleaned not in self.tokens:
            return False
        self.tokens[cleaned]["revoked"] = True
        self._record_audit(self.tokens[cleaned]["email"], "iam.token.revoked", "sso.atius.io", {})
        self._save()
        return True

    def verify_token(self, token: str) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        self._load_if_changed()
        cleaned = str(token or "").strip()
        if cleaned.lower().startswith("bearer "):
            cleaned = cleaned[7:].strip()
        if not cleaned:
            return False, "missing_token", None

        meta = self.tokens.get(cleaned)
        if not meta or meta.get("revoked"):
            return False, "invalid_token", None

        user = self.users.get(meta["user_id"])
        if not user:
            return False, "user_not_found", None

        if user.get("blocked") or user.get("status") == "blocked":
            return False, "user_blocked", self.sanitize_user(user)

        return True, "ok", self.sanitize_user(user)

    def authorize_access(
        self,
        user_or_token: str,
        destination: str,
        required_permission: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Evaluate complete IAM authorization (user status + RBAC persona/role + destination mapping + granular permission).
        """
        user_obj: Optional[Dict[str, Any]] = None
        if str(user_or_token).startswith("atius_iam_"):
            ok, reason, sanitized = self.verify_token(user_or_token)
            if not ok and reason != "user_blocked":
                self._record_audit("anonymous", "iam.authorize.denied", destination, {"reason": reason})
                return {"authorized": False, "status_code": 401, "reason": reason, "destination": destination}
            user_obj = self.find_user(sanitized["id"]) if sanitized else None
        else:
            user_obj = self.find_user(user_or_token)

        if not user_obj:
            self._record_audit("anonymous", "iam.authorize.denied", destination, {"reason": "user_not_found"})
            return {"authorized": False, "status_code": 401, "reason": "user_not_found", "destination": destination}

        if user_obj.get("blocked") or user_obj.get("status") == "blocked":
            self._record_audit(user_obj["email"], "iam.authorize.denied", destination, {"reason": "user_blocked"})
            return {
                "authorized": False,
                "status_code": 403,
                "reason": "user_blocked",
                "destination": destination,
                "user": self.sanitize_user(user_obj),
            }

        eff = self.compute_effective_access(user_obj)
        dest_obj = self.resolve_destination(destination)
        target_host = dest_obj["host"] if dest_obj else str(destination).strip().lower()
        target_aliases = [target_host.lower()] + ([a.lower() for a in dest_obj.get("aliases", [])] if dest_obj else [])

        # 1. Check explicit denied_destinations
        if any(alias in eff["denied_destinations"] for alias in target_aliases):
            self._record_audit(user_obj["email"], "iam.authorize.denied", target_host, {"reason": "destination_explicitly_denied", "role": eff["primary_role"]})
            return {
                "authorized": False,
                "status_code": 403,
                "reason": "destination_explicitly_denied",
                "destination": target_host,
                "user": self.sanitize_user(user_obj),
            }

        # 2. Check destination allowed_roles if destination is registered
        if dest_obj and dest_obj.get("allowed_roles"):
            allowed_roles_low = {r.lower() for r in dest_obj["allowed_roles"]}
            user_roles_low = {r.lower() for r in eff["roles"]}
            if not (user_roles_low & allowed_roles_low):
                self._record_audit(user_obj["email"], "iam.authorize.denied", target_host, {"reason": "missing_role", "user_roles": eff["roles"], "required_roles": dest_obj["allowed_roles"]})
                return {
                    "authorized": False,
                    "status_code": 403,
                    "reason": "missing_role",
                    "required_roles": dest_obj["allowed_roles"],
                    "destination": target_host,
                    "user": self.sanitize_user(user_obj),
                }

        # 3. Check user's allowed_destinations mapping
        allowed_dests_low = {d.lower() for d in eff["allowed_destinations"]}
        if "*" not in allowed_dests_low and not any(alias in allowed_dests_low for alias in target_aliases):
            self._record_audit(user_obj["email"], "iam.authorize.denied", target_host, {"reason": "destination_not_allowed", "allowed_destinations": eff["allowed_destinations"]})
            return {
                "authorized": False,
                "status_code": 403,
                "reason": "destination_not_allowed",
                "destination": target_host,
                "user": self.sanitize_user(user_obj),
            }

        # 4. Check granular permission (either passed explicitly or required by destination)
        perm_to_check = required_permission or (dest_obj.get("required_permission") if dest_obj else None)
        if perm_to_check:
            user_perms = set(eff["permissions"])
            if "*" not in user_perms and perm_to_check not in user_perms and not eff["is_admin"]:
                self._record_audit(user_obj["email"], "iam.authorize.denied", target_host, {"reason": "missing_permission", "required_permission": perm_to_check})
                return {
                    "authorized": False,
                    "status_code": 403,
                    "reason": "missing_permission",
                    "required_permission": perm_to_check,
                    "destination": target_host,
                    "user": self.sanitize_user(user_obj),
                }

        self._record_audit(user_obj["email"], "iam.authorize.granted", target_host, {"role": eff["primary_role"]})
        return {
            "authorized": True,
            "status_code": 200,
            "reason": "authorized",
            "destination": target_host,
            "user": self.sanitize_user(user_obj),
        }
