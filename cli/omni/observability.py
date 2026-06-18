"""observability — health/status for the OMNI observability stack (Phase 17 / M005).

This module is the read-only companion to ``modules/k3s-ha-portainer-oci/
monitoring/scripts/``. It talks to the K3s cluster via ``sudo k3s kubectl``,
queries the Prometheus + Loki + AlertManager HTTP endpoints, and prints
a small green/yellow/red table the operator can read at a glance.

The module is deliberately self-contained — no third-party client libs.
HTTP is done with stdlib ``urllib.request``. JSON parsing with stdlib
``json``. The aim is for the CLI to work in a Python environment
without ``requests`` and to fail loudly when a component is unreachable
instead of silently returning "ok".

CLI:
    omni srv observability status
    omni srv observability status --json
    omni srv observability validate
    omni srv observability dry-run

Backed by:
    - K3s kubeconfig (``/etc/rancher/k3s/k3s.yaml``) via ``sudo -n k3s kubectl``
    - Prometheus (port-forwarded via ``kubectl`` or reachable via ClusterIP service)
    - Loki HTTP API at :3100
    - AlertManager HTTP API at :9093

NOTE: when run from outside the K3s node, port-forwarding is required.
``omni srv observability status`` starts a port-forward in the
background, runs the queries, then tears it down. This keeps the
operator workflow "one command" without requiring manual setup.
"""
from __future__ import annotations

import json
import os
import shlex
import shutil
import socket
import subprocess
import time
import urllib.error
import urllib.request
from contextlib import contextmanager
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Iterator

import click

REPO = Path(os.environ.get("OMNI_SRV_ADMIN", "/home/ubuntu/GitHub/omni-srv-admin"))
MONITORING_DIR = REPO / "modules" / "k3s-ha-portainer-oci" / "monitoring"
KPS_NAMESPACE = "monitoring"
KPS_RELEASE = "omni-monitoring"
# The live Loki release is named `loki` (deployed with `helm install loki
# grafana/loki-stack ...` on 2026-06-17). The Phase 17 plan calls for
# `omni-loki` for new installs, but the current cluster has `loki`. The
# CLI checks both at startup and reports whichever one is present.
LOKI_RELEASE_CANDIDATES = ("omni-loki", "loki")
LOKI_RELEASE = "loki"  # live on the cluster (set 2026-06-17)

# Default ports — overridable via env for tests.
PROMETHEUS_PORT = int(os.environ.get("OMNI_PROM_PORT", "30090"))
LOKI_PORT = int(os.environ.get("OMNI_LOKI_PORT", "30100"))
ALERTMANAGER_PORT = int(os.environ.get("OMNI_AM_PORT", "30093"))

# Standard scrape wait — 5s default. Configurable via env.
SCRAPE_TIMEOUT_S = int(os.environ.get("OMNI_SCRAPE_TIMEOUT_S", "5"))


# ── Errors ───────────────────────────────────────────────────────────


class ObservabilityError(RuntimeError):
    """Raised when the observability stack is unreachable or invalid."""


# ── K3s / kubectl helpers ───────────────────────────────────────────


def _which_sudo() -> str | None:
    return shutil.which("sudo")


def _k3s_kubectl_cmd(json_out: bool = False) -> list[str]:
    """Return a ``sudo -n k3s kubectl ...`` argv prefix.

    The kubeconfig is mode 0600 root:root, so a non-root user must use
    ``sudo -n`` to read it. If sudo is not cached, the caller should
    treat the result as 'k3s unavailable' (not an error).
    """
    cmd = ["sudo", "-n", "k3s", "kubectl"]
    if json_out:
        cmd += ["-o", "json"]
    return cmd


def k3s_available() -> bool:
    """True iff ``sudo -n k3s kubectl get nodes`` succeeds (cluster reachable)."""
    if _which_sudo() is None:
        return False
    try:
        out = subprocess.run(
            _k3s_kubectl_cmd() + ["get", "nodes", "--request-timeout=5s"],
            capture_output=True, text=True, timeout=10,
        )
    except (subprocess.TimeoutExpired, OSError):
        return False
    return out.returncode == 0


def namespace_exists(name: str) -> bool:
    try:
        out = subprocess.run(
            _k3s_kubectl_cmd() + ["get", "namespace", name, "--request-timeout=5s"],
            capture_output=True, text=True, timeout=10,
        )
    except (subprocess.TimeoutExpired, OSError):
        return False
    return out.returncode == 0


def get_pods(namespace: str, label_selector: str | None = None) -> list[dict[str, Any]]:
    cmd = _k3s_kubectl_cmd(json_out=True)
    cmd += ["-n", namespace, "get", "pods"]
    if label_selector:
        cmd += ["-l", label_selector]
    out = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
    if out.returncode != 0:
        return []
    try:
        return json.loads(out.stdout).get("items", [])
    except json.JSONDecodeError:
        return []


# ── HTTP health probes ──────────────────────────────────────────────


def _http_get(url: str, timeout: float) -> tuple[int, str]:
    """GET an HTTP endpoint and return (status_code, body)."""
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:  # noqa: S310
            return resp.status, resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, ""
    except (urllib.error.URLError, OSError, TimeoutError) as e:
        raise ObservabilityError(f"http {url}: {e}") from e


@dataclass
class ComponentState:
    name: str
    status: str = "unknown"  # "green" | "yellow" | "red" | "unknown"
    summary: str = ""
    details: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _classify_pod_health(pods: list[dict[str, Any]]) -> tuple[str, str]:
    """Classify a pod list: green if all Running, yellow if any Pending, red if any failed."""
    if not pods:
        return "red", "no pods found"
    running, pending, failed = 0, 0, 0
    for p in pods:
        phase = (p.get("status") or {}).get("phase", "")
        if phase == "Running":
            running += 1
        elif phase in ("Pending", "ContainerCreating"):
            pending += 1
        else:
            failed += 1
    total = len(pods)
    if failed > 0:
        return "red", f"{running}/{total} running, {failed} failed"
    if pending > 0:
        return "yellow", f"{running}/{total} running, {pending} pending"
    return "green", f"{running}/{total} running"


def _query_prometheus_targets(prom_base: str) -> dict[str, Any]:
    """Query ``/api/v1/targets`` and return ``activeTargets`` and ``droppedTargets``."""
    code, body = _http_get(f"{prom_base}/api/v1/targets", timeout=SCRAPE_TIMEOUT_S)
    if code != 200:
        raise ObservabilityError(f"prometheus /api/v1/targets http {code}")
    return json.loads(body).get("data", {})


def _query_prometheus_alerts(prom_base: str) -> list[dict[str, Any]]:
    """Query ``/api/v1/alerts`` and return the active alerts list."""
    code, body = _http_get(f"{prom_base}/api/v1/alerts", timeout=SCRAPE_TIMEOUT_S)
    if code != 200:
        return []
    return json.loads(body).get("data", {}).get("alerts", [])


def _query_loki_liveness(loki_base: str) -> tuple[int, str]:
    """Query ``/ready`` and return (status_code, body)."""
    return _http_get(f"{loki_base}/ready", timeout=SCRAPE_TIMEOUT_S)


def _query_alertmanager_health(am_base: str) -> tuple[int, str]:
    """Query ``/-/healthy`` and return (status_code, body)."""
    return _http_get(f"{am_base}/-/healthy", timeout=SCRAPE_TIMEOUT_S)


# ── Port forwarding (optional) ──────────────────────────────────────


def _port_forward_service_for(component: str) -> str:
    """Return the Kubernetes service name for a given component.

    The kube-prometheus-stack chart applies a `fullnameOverride` (we
    set it to `omni-monitoring` in the values file), so the actual
    service names are::

        omni-monitoring-prometheus
        omni-monitoring-alertmanager
        omni-monitoring-grafana
        omni-monitoring-kube-state-metrics

    In practice the chart renders the service as
    ``<release>-prometheus`` and ``<release>-alertmanager`` — the
    ``-kube-prometheus-`` infix from the upstream chart disappears
    when ``fullnameOverride`` is set. We resolve at runtime by listing
    services and matching the label ``app.kubernetes.io/name`` so a
    future values change doesn't break the CLI.
    """
    label_map = {
        "prometheus": "prometheus",
        "alertmanager": "alertmanager",
    }
    label = label_map.get(component)
    if label is None:
        return component
    try:
        out = subprocess.run(
            _k3s_kubectl_cmd()
            + ["-n", KPS_NAMESPACE, "get", "svc",
               "-l", f"app.kubernetes.io/name={label}",
               "-o", "jsonpath={.items[*].metadata.name}"],
            capture_output=True, text=True, timeout=10,
        )
    except (subprocess.TimeoutExpired, OSError):
        return component
    if out.returncode == 0 and out.stdout.strip():
        return out.stdout.strip().split()[0]
    # Fallback to the conventional name
    return f"{KPS_RELEASE}-prometheus" if label == "prometheus" else f"{KPS_RELEASE}-alertmanager"


def _resolve_loki_service() -> str | None:
    """Return the live Loki service name, or None if not deployed."""
    try:
        for cand in LOKI_RELEASE_CANDIDATES:
            out = subprocess.run(
                _k3s_kubectl_cmd() + ["-n", KPS_NAMESPACE, "get", "svc", cand],
                capture_output=True, text=True, timeout=10,
            )
            if out.returncode == 0 and out.stdout.strip():
                return cand
    except (subprocess.TimeoutExpired, OSError):
        return None
    return None


@contextmanager
def _port_forward(service: str, namespace: str, local_port: int, remote_port: int) -> Iterator[str]:
    """Start a ``kubectl port-forward`` for the lifetime of the context.

    Yields the ``http://127.0.0.1:<local_port>`` base URL. The process
    is started in the background and terminated when the context exits.

    This is intentionally lightweight — no PID file, no flock, no
    timeout. The caller is expected to be short-lived (a single CLI
    invocation).
    """
    if _which_sudo() is None:
        raise ObservabilityError("sudo not available for kubectl port-forward")
    cmd = [
        "sudo", "-n", "k3s", "kubectl", "-n", namespace,
        "port-forward", f"svc/{service}", f"{local_port}:{remote_port}",
    ]
    proc = subprocess.Popen(  # noqa: S603
        cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    base_url = f"http://127.0.0.1:{local_port}"
    try:
        # Wait for the port to be ready (max 10s)
        deadline = time.time() + 10
        while time.time() < deadline:
            try:
                with socket.create_connection(("127.0.0.1", local_port), timeout=0.5):
                    break
            except OSError:
                time.sleep(0.2)
        else:
            raise ObservabilityError(f"port-forward to {service} did not become ready in 10s")
        yield base_url
    finally:
        try:
            proc.terminate()
            proc.wait(timeout=3)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass


# ── Status aggregation ──────────────────────────────────────────────


def collect_status(use_port_forward: bool = True) -> dict[str, Any]:
    """Collect the live state of every observability component.

    Returns a dict shaped for JSON serialization. Each component is
    classified as ``green | yellow | red | unknown`` with a short
    summary message.

    The K3s component is checked first; if the cluster is unreachable,
    the function returns early with a single red "k3s" component and
    marks all the rest as ``unknown`` (with a reason).
    """
    components: dict[str, ComponentState] = {}

    # 1) K3s reachability
    if not k3s_available():
        components["k3s"] = ComponentState(
            name="k3s",
            status="red",
            summary="k3s cluster unreachable (sudo -n k3s kubectl failed)",
        )
        for c in ("prometheus", "loki", "alertmanager", "prometheus-rules", "dashboards"):
            components[c] = ComponentState(name=c, status="unknown", summary="k3s unreachable")
        return {c.name: c.as_dict() for c in components.values()}

    if not namespace_exists(KPS_NAMESPACE):
        components["k3s"] = ComponentState(
            name="k3s",
            status="yellow",
            summary=f"namespace {KPS_NAMESPACE} does not exist — observability not installed",
        )
        for c in ("prometheus", "loki", "alertmanager", "prometheus-rules", "dashboards"):
            components[c] = ComponentState(name=c, status="unknown", summary="namespace missing")
        return {c.name: c.as_dict() for c in components.values()}

    components["k3s"] = ComponentState(name="k3s", status="green", summary="cluster reachable")

    # 2) Prometheus
    prom_svc = _port_forward_service_for("prometheus")
    if use_port_forward:
        with _port_forward(prom_svc, KPS_NAMESPACE, PROMETHEUS_PORT, 9090) as base:
            components["prometheus"] = _check_prometheus(base)
    else:
        # Direct ClusterIP access — works from inside the cluster or
        # when the operator already has a tunnel.
        base = f"http://{prom_svc}.{KPS_NAMESPACE}.svc:9090"
        components["prometheus"] = _check_prometheus(base)

    # 3) Loki — check release candidates at runtime.
    loki_svc = _resolve_loki_service()
    if loki_svc is None:
        components["loki"] = ComponentState(
            name="loki", status="red",
            summary=f"no loki service found in namespace {KPS_NAMESPACE} (tried {LOKI_RELEASE_CANDIDATES})",
        )
    else:
        if use_port_forward:
            with _port_forward(loki_svc, KPS_NAMESPACE, LOKI_PORT, 3100) as base:
                components["loki"] = _check_loki(base)
        else:
            base = f"http://{loki_svc}.{KPS_NAMESPACE}.svc:3100"
            components["loki"] = _check_loki(base)

    # 4) AlertManager
    am_svc = _port_forward_service_for("alertmanager")
    if use_port_forward:
        with _port_forward(am_svc, KPS_NAMESPACE, ALERTMANAGER_PORT, 9093) as base:
            components["alertmanager"] = _check_alertmanager(base)
    else:
        base = f"http://{am_svc}.{KPS_NAMESPACE}.svc:9093"
        components["alertmanager"] = _check_alertmanager(base)

    # 5) PrometheusRules
    components["prometheus-rules"] = _check_prometheus_rules()

    # 6) Dashboards
    components["dashboards"] = _check_dashboards()

    return {c.name: c.as_dict() for c in components.values()}


def _check_prometheus(base: str) -> ComponentState:
    pods = get_pods(KPS_NAMESPACE, "app.kubernetes.io/name=prometheus")
    pod_status, pod_summary = _classify_pod_health(pods)
    try:
        targets_data = _query_prometheus_targets(base)
        active = targets_data.get("activeTargets", [])
        dropped = targets_data.get("droppedTargets", [])
        healthy = sum(1 for t in active if t.get("health") == "up")
        total = len(active)
        alerts = _query_prometheus_alerts(base)
        firing = sum(1 for a in alerts if a.get("state") == "firing")
        details = {
            "targets_total": total,
            "targets_healthy": healthy,
            "targets_dropped": len(dropped),
            "alerts_firing": firing,
        }
        if pod_status == "green" and healthy == total and total > 0 and firing == 0:
            return ComponentState(name="prometheus", status="green", summary=pod_summary, details=details)
        if pod_status == "green" and (healthy < total or firing > 0):
            return ComponentState(name="prometheus", status="yellow",
                                  summary=f"{healthy}/{total} targets up, {firing} firing", details=details)
        return ComponentState(name="prometheus", status=pod_status, summary=pod_summary, details=details)
    except ObservabilityError as e:
        return ComponentState(name="prometheus", status="red", summary=f"http error: {e}")


def _check_loki(base: str) -> ComponentState:
    # The chart labels Loki pods with `app.kubernetes.io/instance=<release>`
    # and `app=loki` (the latter is the legacy label). We try both.
    pods = get_pods(KPS_NAMESPACE, "app=loki")
    if not pods:
        pods = get_pods(KPS_NAMESPACE, "app.kubernetes.io/instance=loki")
    if not pods:
        pods = get_pods(KPS_NAMESPACE, "app.kubernetes.io/instance=omni-loki")
    pod_status, pod_summary = _classify_pod_health(pods)
    try:
        code, body = _query_loki_liveness(base)
        if code == 200 and "ready" in body.lower():
            return ComponentState(name="loki", status=pod_status, summary=pod_summary,
                                  details={"ready_endpoint": code, "body": body[:80]})
        return ComponentState(name="loki", status="red",
                              summary=f"/ready http {code}: {body[:80]}")
    except ObservabilityError as e:
        return ComponentState(name="loki", status="red", summary=f"http error: {e}")


def _check_alertmanager(base: str) -> ComponentState:
    pods = get_pods(KPS_NAMESPACE, "app.kubernetes.io/name=alertmanager")
    pod_status, pod_summary = _classify_pod_health(pods)
    try:
        code, body = _query_alertmanager_health(base)
        if code == 200:
            return ComponentState(name="alertmanager", status=pod_status, summary=pod_summary,
                                  details={"healthy_endpoint": code, "body": body[:80]})
        return ComponentState(name="alertmanager", status="red",
                              summary=f"/-/healthy http {code}: {body[:80]}")
    except ObservabilityError as e:
        return ComponentState(name="alertmanager", status="red", summary=f"http error: {e}")


def _check_prometheus_rules() -> ComponentState:
    try:
        out = subprocess.run(
            _k3s_kubectl_cmd(json_out=True)
            + ["-n", KPS_NAMESPACE, "get", "prometheusrule", "-o", "json"],
            capture_output=True, text=True, timeout=15,
        )
    except (subprocess.TimeoutExpired, OSError):
        return ComponentState(name="prometheus-rules", status="red", summary="kubectl failed")
    if out.returncode != 0:
        return ComponentState(name="prometheus-rules", status="red", summary=f"kubectl http {out.returncode}")
    try:
        data = json.loads(out.stdout)
    except json.JSONDecodeError:
        return ComponentState(name="prometheus-rules", status="red", summary="invalid json")
    items = data.get("items", [])
    omni_rules = [r for r in items if r.get("metadata", {}).get("name", "").startswith("omni-")]
    if not omni_rules:
        return ComponentState(name="prometheus-rules", status="red",
                              summary="no omni-monitoring-rules found — apply prometheus-rules/omni-rules.yaml")
    return ComponentState(name="prometheus-rules", status="green",
                          summary=f"{len(omni_rules)} rule(s) loaded",
                          details={"rules": [r["metadata"]["name"] for r in omni_rules]})


def _check_dashboards() -> ComponentState:
    try:
        out = subprocess.run(
            _k3s_kubectl_cmd(json_out=True)
            + ["-n", KPS_NAMESPACE, "get", "cm", "-l", "grafana_dashboard=1", "-o", "json"],
            capture_output=True, text=True, timeout=15,
        )
    except (subprocess.TimeoutExpired, OSError):
        return ComponentState(name="dashboards", status="red", summary="kubectl failed")
    if out.returncode != 0:
        return ComponentState(name="dashboards", status="red", summary=f"kubectl http {out.returncode}")
    try:
        data = json.loads(out.stdout)
    except json.JSONDecodeError:
        return ComponentState(name="dashboards", status="red", summary="invalid json")
    items = data.get("items", [])
    expected = {"k3s-ha", "portainer", "pm2-fleet", "jenkins-gdrive"}
    found = set()
    for it in items:
        name = it.get("metadata", {}).get("name", "")
        for s in expected:
            if s in name:
                found.add(s)
    missing = expected - found
    if not missing:
        return ComponentState(name="dashboards", status="green",
                              summary=f"{len(found)}/4 dashboards present",
                              details={"dashboards": sorted(found)})
    return ComponentState(name="dashboards", status="yellow",
                          summary=f"missing: {sorted(missing)}",
                          details={"dashboards": sorted(found), "missing": sorted(missing)})


# ── Static validation (no cluster) ──────────────────────────────────


def validate_files_only() -> list[str]:
    """Validate the on-disk observability artifacts without contacting K3s.

    Returns a list of problems (empty list = all good). This is what
    ``omni srv observability validate`` runs in CI / pre-commit.
    """
    problems: list[str] = []

    prom_values = MONITORING_DIR.parent / "k8s" / "kube-prometheus-stack-values.yaml"
    if not prom_values.is_file():
        problems.append(f"missing: {prom_values}")
    else:
        try:
            import yaml  # type: ignore
        except ImportError:
            problems.append("pyyaml not installed; cannot validate YAML files")
        else:
            try:
                yaml.safe_load(prom_values.read_text())
            except yaml.YAMLError as e:
                problems.append(f"kube-prometheus-stack-values.yaml: {e}")

    loki_values = MONITORING_DIR / "loki" / "values.yaml"
    if not loki_values.is_file():
        problems.append(f"missing: {loki_values}")
    else:
        try:
            import yaml  # type: ignore
            yaml.safe_load(loki_values.read_text())
        except (ImportError, Exception) as e:
            problems.append(f"loki/values.yaml: {e}")

    am_values = MONITORING_DIR / "alertmanager" / "values.yaml"
    if not am_values.is_file():
        problems.append(f"missing: {am_values}")

    rules = MONITORING_DIR / "prometheus-rules"
    if not rules.is_dir():
        problems.append(f"missing dir: {rules}")
    else:
        for f in rules.glob("*.yaml"):
            try:
                import yaml  # type: ignore
                list(yaml.safe_load_all(f.read_text()))
            except Exception as e:  # noqa: BLE001
                problems.append(f"{f.name}: {e}")

    dashboards = MONITORING_DIR / "dashboards"
    if not dashboards.is_dir():
        problems.append(f"missing dir: {dashboards}")
    else:
        for f in dashboards.glob("*.json"):
            try:
                payload = json.loads(f.read_text())
                if "title" not in payload or "uid" not in payload:
                    problems.append(f"{f.name}: missing 'title' or 'uid'")
            except json.JSONDecodeError as e:
                problems.append(f"{f.name}: {e}")

    scripts = MONITORING_DIR / "scripts"
    if not scripts.is_dir():
        problems.append(f"missing dir: {scripts}")
    else:
        for f in scripts.glob("*.sh"):
            if not os.access(f, os.X_OK):
                problems.append(f"{f.name}: not executable")

    return problems


def dry_run_install() -> list[str]:
    """Render the helm template commands that *would* be issued by the install scripts.

    Returns a list of command lines. The operator can paste them into a
    terminal on SRV-1 (with `sudo -n` available) to install the stack.
    """
    return [
        "sudo -n k3s kubectl --kubeconfig /etc/rancher/k3s/k3s.yaml create namespace monitoring || true",
        "helm repo add prometheus-community https://prometheus-community.github.io/helm-charts",
        "helm repo add grafana https://grafana.github.io/helm-charts",
        "helm repo update",
        f"helm install omni-monitoring prometheus-community/kube-prometheus-stack "
        f"--namespace monitoring --create-namespace "
        f"--values {MONITORING_DIR.parent}/k8s/kube-prometheus-stack-values.yaml",
        f"sudo -n k3s kubectl --kubeconfig /etc/rancher/k3s/k3s.yaml apply -f "
        f"{MONITORING_DIR}/prometheus-rules/omni-rules.yaml",
        f"sudo -n k3s kubectl --kubeconfig /etc/rancher/k3s/k3s.yaml -n monitoring create configmap "
        f"grafana-dashboard-{{k3s-ha,portainer,pm2-fleet,jenkins-gdrive}} "
        f"--from-file={MONITORING_DIR}/dashboards/ "
        f"--dry-run=client -o yaml | "
        f"sudo -n k3s kubectl --kubeconfig /etc/rancher/k3s/k3s.yaml -n monitoring label --local -f- "
        f"grafana_dashboard=1 -o yaml | "
        f"sudo -n k3s kubectl --kubeconfig /etc/rancher/k3s/k3s.yaml apply -f -",
        f"helm install omni-loki grafana/loki-stack --namespace monitoring "
        f"--values {MONITORING_DIR}/loki/values.yaml",
    ]


# ── Click sub-group ─────────────────────────────────────────────────


@click.group(name="observability")
def observability() -> None:
    """OMNI observability stack — status, validate, dry-run."""


@observability.command("status")
@click.option("--json", "use_json", is_flag=True, help="Output as JSON.")
@click.option("--no-port-forward", is_flag=True,
              help="Skip port-forwarding (use ClusterIP DNS). Requires running inside the cluster.")
def status_cmd(use_json: bool, no_port_forward: bool) -> None:
    """Report the health of every observability component."""
    if not k3s_available():
        click.echo("k3s cluster unreachable. Run from a host with sudo -n + kubeconfig access.")
        if not use_json:
            click.echo("Component       Status   Summary")
            click.echo("--------------- -------- -------")
            click.echo("k3s             red      cluster unreachable")
        else:
            click.echo(json.dumps({"k3s": {"status": "red", "summary": "cluster unreachable"}}, indent=2))
        raise SystemExit(2)

    state = collect_status(use_port_forward=not no_port_forward)
    if use_json:
        click.echo(json.dumps(state, indent=2))
    else:
        click.echo(f"{'Component':<20} {'Status':<10} Summary")
        click.echo("-" * 80)
        for name in ("k3s", "prometheus", "loki", "alertmanager", "prometheus-rules", "dashboards"):
            comp = state.get(name, {"status": "unknown", "summary": "n/a"})
            status = comp.get("status", "unknown")
            summary = comp.get("summary", "")
            click.echo(f"{name:<20} {status:<10} {summary}")
    if any(c.get("status") in ("red", "unknown") for c in state.values()):
        raise SystemExit(1)


@observability.command("validate")
def validate_cmd() -> None:
    """Validate the observability artifacts on disk (no cluster contact)."""
    problems = validate_files_only()
    if not problems:
        click.echo("✓ all observability artifacts present and well-formed")
        return
    click.echo(f"✗ {len(problems)} problem(s):")
    for p in problems:
        click.echo(f"  - {p}")
    raise SystemExit(1)


@observability.command("dry-run")
@click.option("--shell", "shell_kind", default="bash", type=click.Choice(["bash"]))
def dry_run_cmd(shell_kind: str) -> None:
    """Print the helm/kubectl commands that would install the observability stack."""
    click.echo("# Dry-run — copy/paste on ATIUS-SRV-1 with sudo -n available:")
    click.echo("")
    for line in dry_run_install():
        click.echo(line)


def _resolve_loki_service() -> str | None:
    """Return the live Loki service name, or None if not deployed.

    Tries the canonical Phase 17 release name (``omni-loki``) first,
    then falls back to ``loki`` (the actual release name on the
    cluster as of 2026-06-17).
    """
    try:
        for cand in LOKI_RELEASE_CANDIDATES:
            out = subprocess.run(
                _k3s_kubectl_cmd() + ["-n", KPS_NAMESPACE, "get", "svc", cand],
                capture_output=True, text=True, timeout=10,
            )
            if out.returncode == 0 and out.stdout.strip():
                return cand
    except (subprocess.TimeoutExpired, OSError):
        return None
    return None


@observability.command("config")
def config_cmd() -> None:
    """Print the paths this module uses (for debugging)."""
    click.echo(f"REPO:                 {REPO}")
    click.echo(f"MONITORING_DIR:       {MONITORING_DIR}")
    click.echo(f"KPS_NAMESPACE:        {KPS_NAMESPACE}")
    click.echo(f"KPS_RELEASE:          {KPS_RELEASE}")
    click.echo(f"LOKI_RELEASE:         {LOKI_RELEASE}")
    click.echo(f"PROMETHEUS_PORT:      {PROMETHEUS_PORT}")
    click.echo(f"LOKI_PORT:            {LOKI_PORT}")
    click.echo(f"ALERTMANAGER_PORT:    {ALERTMANAGER_PORT}")
