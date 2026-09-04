"""Landscape control-plane integration for omni.

This module keeps the repo as the reviewed source of truth for scripts while
using Landscape as the Ubuntu machine execution plane.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlparse
from urllib.request import Request, urlopen

import click


REPO = Path(__file__).resolve().parents[2]
MANIFEST_PATH = REPO / "modules" / "landscape-control-plane" / "scripts" / "manifest.json"
DEFAULT_ENDPOINT = "https://landscape.atius.com.br/api/"
DEFAULT_API_VERSION = "2011-08-01"
CONTROLLED_HOSTS = (
    "atius-srv-1",
    "atius-srv-2",
    "atius-srv-3",
    "atius-srv-4",
    "horistic-srv",
)
READ_ONLY_ACTION_PREFIXES = ("Get",)


class LandscapeError(click.ClickException):
    """User-facing Landscape integration error."""


@dataclass(frozen=True)
class ScriptSpec:
    script_id: str
    title: str
    version: str
    path: Path
    interpreter: str
    username: str
    time_limit: int
    access_group: str
    risk: str
    description: str

    @property
    def code(self) -> str:
        try:
            return self.path.read_text(encoding="utf-8")
        except OSError as exc:
            raise LandscapeError(f"script nao encontrado: {self.path}") from exc

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.code.encode("utf-8")).hexdigest()


def _mask(value: str | None) -> str:
    if not value:
        return "missing"
    if len(value) <= 8:
        return "***"
    return f"{value[:4]}...{value[-4:]}"


def _load_manifest() -> dict[str, Any]:
    try:
        return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise LandscapeError(f"manifest nao encontrado: {MANIFEST_PATH}") from exc
    except json.JSONDecodeError as exc:
        raise LandscapeError(f"manifest JSON invalido: {MANIFEST_PATH}: {exc}") from exc


def _script_specs() -> list[ScriptSpec]:
    manifest = _load_manifest()
    raw_scripts = manifest.get("scripts")
    if not isinstance(raw_scripts, list):
        raise LandscapeError("manifest invalido: campo scripts ausente")
    specs: list[ScriptSpec] = []
    for item in raw_scripts:
        if not isinstance(item, dict):
            raise LandscapeError("manifest invalido: script deve ser objeto")
        rel_path = item.get("path")
        script_id = item.get("id")
        if not rel_path or not script_id:
            raise LandscapeError("manifest invalido: script sem id/path")
        specs.append(
            ScriptSpec(
                script_id=str(script_id),
                title=str(item.get("title") or f"omni::{script_id}"),
                version=str(item.get("version") or "0.0.0"),
                path=MANIFEST_PATH.parent / str(rel_path),
                interpreter=str(item.get("interpreter") or "/bin/bash"),
                username=str(item.get("username") or "root"),
                time_limit=int(item.get("time_limit") or 300),
                access_group=str(item.get("access_group") or "global"),
                risk=str(item.get("risk") or "unknown"),
                description=str(item.get("description") or ""),
            )
        )
    return specs


def _find_script(script_id: str) -> ScriptSpec:
    matches = [spec for spec in _script_specs() if spec.script_id == script_id or spec.title == script_id]
    if not matches:
        raise LandscapeError(f"script nao registrado no manifesto: {script_id}")
    return matches[0]


def _endpoint() -> str:
    endpoint = (
        os.environ.get("OMNI_LANDSCAPE_ENDPOINT")
        or os.environ.get("LANDSCAPE_API_URI")
        or os.environ.get("LANDSCAPE_ENDPOINT")
        or DEFAULT_ENDPOINT
    )
    return endpoint.rstrip("/") + "/"


def _access_key() -> str | None:
    return os.environ.get("OMNI_LANDSCAPE_ACCESS_KEY") or os.environ.get("LANDSCAPE_API_KEY") or os.environ.get("LANDSCAPE_ACCESS_KEY")


def _secret_key() -> str | None:
    return os.environ.get("OMNI_LANDSCAPE_SECRET_KEY") or os.environ.get("LANDSCAPE_API_SECRET") or os.environ.get("LANDSCAPE_SECRET_KEY")


def _jwt() -> str | None:
    return os.environ.get("OMNI_LANDSCAPE_JWT") or os.environ.get("LANDSCAPE_JWT")


def _quote(value: str) -> str:
    return quote(value, safe="-_.~")


def _canonical_query(params: dict[str, str]) -> str:
    # Landscape self-hosted 26.04 validates with canonical.txapi.auth
    # get_canonical_query_params(), which preserves received parameter order.
    # Keep this in the same insertion order used by urlencode(payload).
    return "&".join(f"{_quote(str(key))}={_quote(str(value))}" for key, value in params.items())


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class LandscapeClient:
    def __init__(
        self,
        endpoint: str | None = None,
        access_key: str | None = None,
        secret_key: str | None = None,
        jwt: str | None = None,
        version: str = DEFAULT_API_VERSION,
    ) -> None:
        self.endpoint = (endpoint or _endpoint()).rstrip("/") + "/"
        self.access_key = access_key if access_key is not None else _access_key()
        self.secret_key = secret_key if secret_key is not None else _secret_key()
        self.jwt = jwt if jwt is not None else _jwt()
        self.version = version

    @property
    def can_hmac(self) -> bool:
        return bool(self.access_key and self.secret_key)

    @property
    def can_jwt(self) -> bool:
        return bool(self.jwt)

    def _request_json(self, method: str, url: str, data: bytes | None = None, headers: dict[str, str] | None = None) -> Any:
        req = Request(url, data=data, headers=headers or {}, method=method)
        try:
            with urlopen(req, timeout=60) as response:
                body = response.read().decode("utf-8")
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise LandscapeError(f"Landscape HTTP {exc.code}: {detail[:800]}") from exc
        except URLError as exc:
            raise LandscapeError(f"Landscape API indisponivel: {exc}") from exc
        if not body:
            return None
        try:
            return json.loads(body)
        except json.JSONDecodeError as exc:
            raise LandscapeError(f"Landscape retornou JSON invalido: {body[:800]}") from exc

    def legacy(self, action: str, **params: Any) -> Any:
        payload: dict[str, str] = {"action": action, "version": self.version}
        for key, value in params.items():
            if value is None:
                continue
            if isinstance(value, bool):
                payload[key] = "true" if value else "false"
            else:
                payload[key] = str(value)

        headers: dict[str, str] = {}
        if self.jwt:
            headers["Authorization"] = f"Bearer {self.jwt}"
        else:
            if not self.can_hmac:
                raise LandscapeError("credenciais Landscape ausentes: exporte OMNI_LANDSCAPE_ACCESS_KEY/SECRET_KEY ou LANDSCAPE_API_KEY/SECRET")
            payload.update(
                {
                    "access_key_id": str(self.access_key),
                    "signature_method": "HmacSHA256",
                    "signature_version": "2",
                    "timestamp": _timestamp(),
                }
            )
            parsed = urlparse(self.endpoint)
            canonical = _canonical_query(payload)
            string_to_sign = f"GET\n{parsed.netloc.lower()}\n{parsed.path or '/'}\n{canonical}"
            digest = hmac.new(str(self.secret_key).encode("utf-8"), string_to_sign.encode("utf-8"), hashlib.sha256).digest()
            payload["signature"] = base64.b64encode(digest).decode("ascii")

        return self._request_json("GET", self.endpoint + "?" + urlencode(payload), headers=headers)

    def rest_v2(self, path: str) -> Any:
        if not self.jwt:
            raise LandscapeError("REST v2 requer OMNI_LANDSCAPE_JWT/LANDSCAPE_JWT")
        base = self.endpoint
        if base.endswith("/api/"):
            base = base[:-5] + "/api/v2/"
        elif not base.endswith("/api/v2/"):
            base = base.rstrip("/") + "/api/v2/"
        return self._request_json("GET", base + path.lstrip("/"), headers={"Authorization": f"Bearer {self.jwt}"})


def _host_query(hosts: str | None, query: str | None) -> str:
    if query:
        return query
    selected = CONTROLLED_HOSTS if not hosts or hosts == "all" else tuple(item.strip() for item in hosts.split(",") if item.strip())
    unknown = [host for host in selected if host not in CONTROLLED_HOSTS]
    if unknown:
        raise LandscapeError(f"host fora do escopo controlado: {', '.join(unknown)}")
    return " OR ".join(f"hostname:{host}" for host in selected)


def _remote_scripts_by_title(client: LandscapeClient) -> dict[str, dict[str, Any]]:
    scripts = client.legacy("GetScripts", limit=1000)
    if not isinstance(scripts, list):
        raise LandscapeError("GetScripts retornou formato inesperado")
    return {str(item.get("title")): item for item in scripts if isinstance(item, dict)}


def _push_script(client: LandscapeClient, spec: ScriptSpec, yes: bool) -> dict[str, Any]:
    remote = _remote_scripts_by_title(client).get(spec.title)
    code_b64 = base64.b64encode(spec.code.encode("utf-8")).decode("ascii")
    if not remote:
        plan = {"action": "create", "title": spec.title, "version": spec.version, "sha256": spec.sha256, "username": spec.username, "time_limit": spec.time_limit, "access_group": spec.access_group}
        if not yes:
            return plan
        created = client.legacy("CreateScript", title=spec.title, time_limit=spec.time_limit, code=code_b64, username=spec.username, access_group=spec.access_group)
        return {"action": "created", "script": created, "desired": plan}

    script_id = str(remote.get("id"))
    remote_code = client.legacy("GetScriptCode", script_id=script_id)
    remote_hash = hashlib.sha256(str(remote_code).encode("utf-8")).hexdigest()
    if remote_code == spec.code:
        return {"action": "noop", "script_id": script_id, "title": spec.title, "version": spec.version, "sha256": spec.sha256}
    plan = {"action": "edit", "script_id": script_id, "title": spec.title, "version": spec.version, "old_sha256": remote_hash, "new_sha256": spec.sha256}
    if not yes:
        return plan
    edited = client.legacy("EditScript", script_id=script_id, title=spec.title, time_limit=spec.time_limit, code=code_b64, username=spec.username)
    return {"action": "edited", "script": edited, "desired": plan}


def _echo_json(data: Any) -> None:
    click.echo(json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False))


@click.group(name="landscape")
def landscape() -> None:
    """Integra Omni ao Landscape self-hosted para inventario e execucao em lote."""


@landscape.command("status")
@click.option("--json", "json_output", is_flag=True, help="Emite JSON.")
def status(json_output: bool) -> None:
    """Mostra configuracao local da integracao Landscape."""
    specs = _script_specs()
    data = {
        "endpoint": _endpoint(),
        "manifest": str(MANIFEST_PATH),
        "scripts": len(specs),
        "controlled_hosts": list(CONTROLLED_HOSTS),
        "auth": {"jwt": "present" if _jwt() else "missing", "access_key": _mask(_access_key()), "secret_key": "present" if _secret_key() else "missing"},
    }
    if json_output:
        _echo_json(data)
        return
    click.echo(f"endpoint: {data['endpoint']}")
    click.echo(f"manifest: {data['manifest']}")
    click.echo(f"scripts:  {data['scripts']}")
    click.echo(f"hosts:    {', '.join(CONTROLLED_HOSTS)}")
    click.echo(f"jwt:      {data['auth']['jwt']}")
    click.echo(f"key:      {data['auth']['access_key']}")
    click.echo(f"secret:   {data['auth']['secret_key']}")


@landscape.command("api")
@click.argument("action")
@click.option("--param", "params", multiple=True, help="Parametro key=value para legacy API.")
@click.option("--yes", is_flag=True, help="Permite action que nao comece com Get.")
@click.option("--json", "json_output", is_flag=True, help="Emite JSON.")
def api(action: str, params: tuple[str, ...], yes: bool, json_output: bool) -> None:
    """Chama uma action da legacy API com assinatura HMAC/JWT."""
    if not action.startswith(READ_ONLY_ACTION_PREFIXES) and not yes:
        raise LandscapeError("action mutavel requer --yes")
    parsed: dict[str, str] = {}
    for item in params:
        if "=" not in item:
            raise LandscapeError(f"parametro invalido, esperado key=value: {item}")
        key, value = item.split("=", 1)
        parsed[key] = value
    result = LandscapeClient().legacy(action, **parsed)
    click.echo(json.dumps(result, indent=2, sort_keys=json_output, ensure_ascii=False))


@landscape.command("computers")
@click.option("--query", default="", help="Query Landscape. Default: hosts controlados.")
@click.option("--hosts", default="all", help="all ou lista: atius-srv-1,atius-srv-2,...")
@click.option("--with-network", is_flag=True, help="Inclui rede no GetComputers.")
@click.option("--json", "json_output", is_flag=True, help="Emite JSON.")
def computers(query: str, hosts: str, with_network: bool, json_output: bool) -> None:
    """Lista computadores Landscape no escopo Omni."""
    result = LandscapeClient().legacy("GetComputers", query=_host_query(hosts, query or None), limit=1000, with_network=with_network)
    if json_output:
        _echo_json(result)
        return
    for item in result if isinstance(result, list) else []:
        click.echo(f"{item.get('id')!s:>8} {item.get('hostname') or item.get('title')} access_group={item.get('access_group')} last={item.get('last_exchange_time') or item.get('last_ping_time')}")


@landscape.group("activities")
def activities_group() -> None:
    """Consulta atividades Landscape criadas pelo Omni."""


@activities_group.command("show")
@click.argument("activity_id")
@click.option("--children", is_flag=True, help="Mostra atividades filhas.")
@click.option("--json", "json_output", is_flag=True, help="Emite JSON.")
def activities_show(activity_id: str, children: bool, json_output: bool) -> None:
    """Mostra uma atividade ou ActivityGroup."""
    query = f"parent-id:{activity_id}" if children else f"id:{activity_id}"
    result = LandscapeClient().legacy("GetActivities", query=query)
    if json_output:
        _echo_json(result)
        return
    for item in result if isinstance(result, list) else []:
        click.echo(
            f"{item.get('id')!s:>8} status={item.get('activity_status')} "
            f"computer={item.get('computer_id')} summary={item.get('summary')}"
        )
        result_text = item.get("result_text")
        if result_text:
            click.echo(str(result_text)[:2000])


@activities_group.command("recent")
@click.option("--limit", default=20, help="Numero de atividades.")
@click.option("--status", "status_name", default="", help="Filtra por status.")
@click.option("--json", "json_output", is_flag=True, help="Emite JSON.")
def activities_recent(limit: int, status_name: str, json_output: bool) -> None:
    """Lista atividades recentes."""
    query = f"status:{status_name}" if status_name else ""
    result = LandscapeClient().legacy("GetActivities", query=query, limit=limit)
    if json_output:
        _echo_json(result)
        return
    for item in result if isinstance(result, list) else []:
        click.echo(
            f"{item.get('id')!s:>8} status={item.get('activity_status')} "
            f"computer={item.get('computer_id')} summary={item.get('summary')}"
        )


@landscape.group("scripts")
def scripts_group() -> None:
    """Gerencia scripts versionados Omni/Landscape."""


@scripts_group.command("list")
@click.option("--json", "json_output", is_flag=True, help="Emite JSON.")
def scripts_list(json_output: bool) -> None:
    """Lista scripts versionados no repo."""
    rows = [{"id": spec.script_id, "title": spec.title, "version": spec.version, "risk": spec.risk, "username": spec.username, "time_limit": spec.time_limit, "sha256": spec.sha256, "path": str(spec.path.relative_to(REPO))} for spec in _script_specs()]
    if json_output:
        _echo_json(rows)
        return
    for row in rows:
        click.echo(f"{row['id']:22} {row['version']:8} {row['risk']:10} {row['title']} {row['sha256'][:12]}")


@scripts_group.command("show")
@click.argument("script_id")
@click.option("--code", is_flag=True, help="Mostra o codigo do script.")
def scripts_show(script_id: str, code: bool) -> None:
    """Mostra metadados ou codigo de um script versionado."""
    spec = _find_script(script_id)
    if code:
        click.echo(spec.code, nl=False)
        return
    _echo_json({"id": spec.script_id, "title": spec.title, "version": spec.version, "path": str(spec.path.relative_to(REPO)), "interpreter": spec.interpreter, "username": spec.username, "time_limit": spec.time_limit, "access_group": spec.access_group, "risk": spec.risk, "sha256": spec.sha256, "description": spec.description})


@scripts_group.command("push")
@click.argument("script_id")
@click.option("--yes", is_flag=True, help="Cria/edita o script no Landscape.")
@click.option("--json", "json_output", is_flag=True, help="Emite JSON.")
def scripts_push(script_id: str, yes: bool, json_output: bool) -> None:
    """Cria ou edita um script Landscape a partir do manifesto."""
    result = _push_script(LandscapeClient(), _find_script(script_id), yes=yes)
    click.echo(json.dumps(result, indent=2, sort_keys=json_output, ensure_ascii=False))
    if not yes:
        click.echo("plan-only: use --yes para aplicar no Landscape")


@scripts_group.command("sync")
@click.option("--yes", is_flag=True, help="Cria/edita todos os scripts no Landscape.")
@click.option("--json", "json_output", is_flag=True, help="Emite JSON.")
def scripts_sync(yes: bool, json_output: bool) -> None:
    """Sincroniza todos os scripts versionados com o Landscape."""
    client = LandscapeClient()
    results = [_push_script(client, spec, yes=yes) for spec in _script_specs()]
    click.echo(json.dumps(results, indent=2, sort_keys=json_output, ensure_ascii=False))
    if not yes:
        click.echo("plan-only: use --yes para aplicar no Landscape")


@scripts_group.command("versions")
@click.argument("script_id")
@click.option("--json", "json_output", is_flag=True, help="Emite JSON.")
def scripts_versions(script_id: str, json_output: bool) -> None:
    """Mostra versoes de um script via REST v2 quando JWT estiver disponivel."""
    client = LandscapeClient()
    spec = _find_script(script_id)
    remote = _remote_scripts_by_title(client).get(spec.title)
    if not remote:
        raise LandscapeError(f"script ainda nao existe no Landscape: {spec.title}")
    if client.can_jwt:
        result = client.rest_v2(f"scripts/{remote.get('id')}/versions")
    else:
        result = {"note": "REST v2 versions requer OMNI_LANDSCAPE_JWT; mostrando somente script atual via legacy API", "script": remote, "repo": {"version": spec.version, "sha256": spec.sha256}}
    click.echo(json.dumps(result, indent=2, sort_keys=json_output, ensure_ascii=False))


@landscape.command("run")
@click.argument("script_id")
@click.option("--hosts", default="all", help="all ou lista controlada.")
@click.option("--query", default="", help="Query Landscape customizada. Sobrepoe --hosts.")
@click.option("--username", default=None, help="Usuario de execucao. Default do manifesto.")
@click.option("--deliver-after", default=None, help="YYYY-MM-DDTHH:MM:SSZ.")
@click.option("--sync-script", is_flag=True, help="Sincroniza script antes de executar.")
@click.option("--yes", is_flag=True, help="Executa no Landscape. Sem isto e plan-only.")
@click.option("--json", "json_output", is_flag=True, help="Emite JSON.")
def run_script(script_id: str, hosts: str, query: str, username: str | None, deliver_after: str | None, sync_script: bool, yes: bool, json_output: bool) -> None:
    """Executa um script versionado em lote via Landscape ExecuteScript."""
    client = LandscapeClient()
    spec = _find_script(script_id)
    selected_query = _host_query(hosts, query or None)
    sync_result = _push_script(client, spec, yes=yes) if sync_script else None
    remote = _remote_scripts_by_title(client).get(spec.title)
    if not remote:
        raise LandscapeError(f"script nao existe no Landscape: rode 'omni landscape scripts push {script_id} --yes' ou use --sync-script --yes")
    payload = {"query": selected_query, "script_id": str(remote.get("id")), "username": username or spec.username, "deliver_after": deliver_after}
    plan = {"action": "ExecuteScript", "script": spec.title, "version": spec.version, "payload": {k: v for k, v in payload.items() if v}, "sync": sync_result}
    if not yes:
        click.echo(json.dumps(plan, indent=2, sort_keys=json_output, ensure_ascii=False))
        click.echo("plan-only: use --yes para executar no Landscape")
        return
    result = client.legacy("ExecuteScript", **payload)
    click.echo(json.dumps({"submitted": result, "plan": plan}, indent=2, sort_keys=json_output, ensure_ascii=False))
