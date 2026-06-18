"""edge — Cloudflare Access aware client for omni admin edges.

The admin edges ``portainer.atius.com.br`` and ``docker.atius.com.br`` are
moving from Apache Basic Auth to Cloudflare Access (Phase 16 / M005
follow-up). The functions in this module let the rest of ``omni-cli``
talk to those edges transparently — they will try the Cloudflare
service token first (if available) and fall back to the legacy Basic
Auth credentials if the token is absent.

The service token lives at ``~/.hermes/secrets/cloudflare-service-token.json``
in the format documented in ``docs/operations/edge-auth.md``. The file
is created with mode 0600 and is **never** committed to the repo.
"""

from __future__ import annotations

import base64
import json
import os
import stat
from pathlib import Path
from typing import Any

import click

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Admin edges that are fronted by Cloudflare Access.
ADMIN_EDGES: dict[str, str] = {
    "portainer": "https://portainer.atius.com.br",
    "docker": "https://docker.atius.com.br",
}

# Where the service token JSON lives. Same convention as
# ~/.hermes/secrets/* used elsewhere in the repo (e.g. esm-apps tokens).
SERVICE_TOKEN_FILE = Path(
    os.environ.get(
        "OMNI_CF_SERVICE_TOKEN_FILE",
        str(Path.home() / ".hermes" / "secrets" / "cloudflare-service-token.json"),
    )
)

# Legacy Apache Basic Auth credentials. Kept as fallback per Phase 16
# Task 3: "Apache Basic Auth fallback — don't remove Basic Auth yet".
# Sourced from environment so the secret does not live in the repo.
LEGACY_BASIC_AUTH_ENV_USER = "OMNI_ADMIN_EDGE_BASIC_USER"
LEGACY_BASIC_AUTH_ENV_PASS = "OMNI_ADMIN_EDGE_BASIC_PASS"

# Cloudflare Access injects these two headers on every request when
# the caller authenticates with a service token.
CF_ACCESS_HEADER_CLIENT_ID = "CF-Access-Client-Id"
CF_ACCESS_HEADER_CLIENT_SECRET = "CF-Access-Client-Secret"

# ---------------------------------------------------------------------------
# Service token helpers
# ---------------------------------------------------------------------------


def cf_service_token_exists() -> bool:
    """Return ``True`` if the service token file is present and readable."""
    return SERVICE_TOKEN_FILE.is_file()


def load_cf_service_token() -> dict[str, str] | None:
    """Load the service token JSON from disk.

    Returns ``None`` if the file is missing or malformed. Never raises —
    the caller decides what to do when there is no token.
    """
    if not cf_service_token_exists():
        return None
    try:
        data = json.loads(SERVICE_TOKEN_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if not isinstance(data, dict):
        return None
    if "client_id" not in data or "client_secret" not in data:
        return None
    return data


def cf_service_auth_headers() -> dict[str, str]:
    """Return Cloudflare Access service token headers for ``requests``.

    The dict has the standard ``CF-Access-Client-Id`` and
    ``CF-Access-Client-Secret`` keys expected by Cloudflare Access.
    Returns an empty dict when the token file is missing, so the caller
    can fall back to Basic Auth.
    """
    token = load_cf_service_token()
    if not token:
        return {}
    return {
        CF_ACCESS_HEADER_CLIENT_ID: token["client_id"],
        CF_ACCESS_HEADER_CLIENT_SECRET: token["client_secret"],
    }


def write_cf_service_token(client_id: str, client_secret: str) -> Path:
    """Persist a service token to disk with mode 0600.

    This is the bootstrap helper used right after the operator
    generates a token in the Cloudflare dashboard. The existing file is
    only overwritten via :func:`rotate_cf_service_token`.
    """
    SERVICE_TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(
        {
            "client_id": client_id,
            "client_secret": client_secret,
            "issued_by": "cloudflare-access-dashboard",
            "comment": (
                "Phase 16 / M005 Cloudflare Access service token. "
                "Rotate annually per docs/operations/edge-auth.md."
            ),
        },
        indent=2,
    )
    SERVICE_TOKEN_FILE.write_text(payload, encoding="utf-8")
    os.chmod(SERVICE_TOKEN_FILE, stat.S_IRUSR | stat.S_IWUSR)
    return SERVICE_TOKEN_FILE


def rotate_cf_service_token(client_id: str, client_secret: str) -> Path:
    """Overwrite an existing service token. Backup goes to ``*.bak``."""
    if SERVICE_TOKEN_FILE.is_file():
        backup = SERVICE_TOKEN_FILE.with_suffix(SERVICE_TOKEN_FILE.suffix + ".bak")
        backup.write_text(SERVICE_TOKEN_FILE.read_text(encoding="utf-8"), encoding="utf-8")
        os.chmod(backup, stat.S_IRUSR | stat.S_IWUSR)
    return write_cf_service_token(client_id, client_secret)


# ---------------------------------------------------------------------------
# Edge authentication strategies
# ---------------------------------------------------------------------------


def basic_auth_header(user: str, password: str) -> dict[str, str]:
    """Build the ``Authorization: Basic ...`` header value (already encoded)."""
    raw = f"{user}:{password}".encode("utf-8")
    encoded = base64.b64encode(raw).decode("ascii")
    return {"Authorization": f"Basic {encoded}"}


def basic_auth_header_from_env() -> dict[str, str] | None:
    """Build Basic Auth headers from the legacy env vars, or ``None``."""
    user = os.environ.get(LEGACY_BASIC_AUTH_ENV_USER)
    password = os.environ.get(LEGACY_BASIC_AUTH_ENV_PASS)
    if not user or not password:
        return None
    return basic_auth_header(user, password)


def resolve_edge_auth(prefer: str = "auto") -> tuple[dict[str, str], str]:
    """Return the headers dict + a label describing the auth source.

    ``prefer`` can be:

    * ``"auto"`` — service token if present, else Basic Auth if env vars
      are set, else empty dict (caller will see 401 and report a clear
      error).
    * ``"service-token"`` — force the CF service token (returns empty
      dict if missing; caller can detect the misconfiguration).
    * ``"basic"`` — force Basic Auth from env (returns empty dict if
      env vars are unset).
    """
    if prefer == "service-token":
        headers = cf_service_auth_headers()
        label = "cf-service-token" if headers else "missing-service-token"
        return headers, label
    if prefer == "basic":
        headers = basic_auth_header_from_env() or {}
        label = "basic-auth" if headers else "missing-basic-auth"
        return headers, label
    # auto
    cf_headers = cf_service_auth_headers()
    if cf_headers:
        return cf_headers, "cf-service-token"
    basic = basic_auth_header_from_env()
    if basic:
        return basic, "basic-auth"
    return {}, "none"


# ---------------------------------------------------------------------------
# Convenience helpers
# ---------------------------------------------------------------------------


# Cloudflare WAF blocks the bare ``Python-urllib/3.x`` UA. A real-looking
# browser UA gets past the WAF and reaches the origin (where Apache
# serves the actual 401 Basic challenge).
_EDGE_PROBE_UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


def edge_url(name: str) -> str | None:
    """Return the URL of a known admin edge by its short name."""
    return ADMIN_EDGES.get(name)


def describe_auth() -> dict[str, Any]:
    """Diagnostic snapshot of the current auth configuration.

    Used by ``omni edge status`` and by the runbook. Does not leak any
    secret values — only whether the file is present and its mode.
    """
    info: dict[str, Any] = {
        "service_token_file": str(SERVICE_TOKEN_FILE),
        "service_token_present": cf_service_token_exists(),
    }
    if cf_service_token_exists():
        st = SERVICE_TOKEN_FILE.stat()
        info["service_token_mode"] = stat.filemode(st.st_mode)
        info["service_token_octal_mode"] = oct(st.st_mode & 0o777)
    info["basic_auth_user_set"] = bool(os.environ.get(LEGACY_BASIC_AUTH_ENV_USER))
    info["basic_auth_pass_set"] = bool(os.environ.get(LEGACY_BASIC_AUTH_ENV_PASS))
    return info


# ---------------------------------------------------------------------------
# Click CLI surface (``omni edge ...``)
# ---------------------------------------------------------------------------


@click.group(name="edge")
def edge() -> None:
    """Gestão dos admin edges (portainer / docker) e do Cloudflare Access."""


@edge.command("status")
def edge_status() -> None:
    """Mostra o estado atual de autenticação dos admin edges."""
    click.echo(json.dumps(describe_auth(), indent=2, ensure_ascii=False))


@edge.command("auth")
@click.option(
    "--prefer",
    type=click.Choice(["auto", "service-token", "basic"]),
    default="auto",
    show_default=True,
    help="Estratégia de auth (auto usa service token se existir).",
)
def edge_auth(prefer: str) -> None:
    """Resolve e mostra os headers de auth que serão usados.

    Útil para debugar ``omni fleet portainer status`` e similares.
    """
    headers, label = resolve_edge_auth(prefer)
    sanitized = {k: ("<redacted>" if k != k.lower() else v) for k, v in headers.items()}
    if "Authorization" in sanitized:
        sanitized["Authorization"] = f"Basic {sanitized['Authorization'].split(' ', 1)[-1][:6]}..."
    click.echo(json.dumps({"label": label, "headers": sanitized}, indent=2))


@edge.command("check")
@click.option(
    "--edge-name",
    default="portainer",
    show_default=True,
    help="Nome curto do admin edge (portainer, docker).",
)
@click.option(
    "--prefer",
    type=click.Choice(["auto", "service-token", "basic"]),
    default="auto",
    show_default=True,
)
def edge_check(edge_name: str, prefer: str) -> None:
    """Faz um probe num admin edge e mostra o HTTP code + label de auth.

    Usa ``GET`` em vez de ``HEAD`` (Cloudflare retorna 403 para HEAD
    contra admin edges) com um User-Agent de browser real (o UA padrão
    do urllib é bloqueado pelo WAF). Retorna exit code 0 com o JSON
    de resultado — a interpretação do HTTP code fica com o caller /
    com ``scripts/validate-edge-auth.py`` que tem a matriz completa.
    """
    import urllib.request
    import urllib.error

    url = edge_url(edge_name)
    if not url:
        raise click.BadParameter(f"admin edge desconhecido: {edge_name}")
    headers, label = resolve_edge_auth(prefer)
    headers.setdefault("User-Agent", _EDGE_PROBE_UA)
    req = urllib.request.Request(url, method="GET", headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:  # nosec - admin edge call
            code = resp.status
    except urllib.error.HTTPError as e:
        code = e.code
    except Exception as e:  # pragma: no cover
        click.echo(f"ERROR: {e}", err=True)
        raise SystemExit(2)
    click.echo(json.dumps({"edge": edge_name, "url": url, "auth": label, "http": code}, indent=2))
