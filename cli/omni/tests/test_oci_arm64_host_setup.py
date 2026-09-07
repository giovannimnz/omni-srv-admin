"""Contracts for the resumable OCI ARM64 host bootstrap orchestrator."""

from __future__ import annotations

import importlib.util
import io
from pathlib import Path
import subprocess
import tarfile

import pytest


REPO = Path(__file__).resolve().parents[3]
SCRIPT = REPO / "modules" / "fleet" / "scripts" / "oci-arm64-host-setup.sh"
OBSIDIAN_PULL = REPO / "modules" / "fleet" / "scripts" / "obsidian-vault-pull.sh"
OBSIDIAN_SERVICE = REPO / "modules" / "fleet" / "systemd" / "obsidian-vault-pull.service"
OBSIDIAN_TIMER = REPO / "modules" / "fleet" / "systemd" / "obsidian-vault-pull.timer"
SETUP_FILE_LIST = REPO / "modules" / "fleet" / "configs" / "oci-arm64-host-setup-files.txt"
SETUP_BUILDER = REPO / "modules" / "fleet" / "scripts" / "build-oci-arm64-host-setup-staging.py"
RUNBOOK = REPO / "docs" / "runbooks" / "atius-srv4-bootstrap.md"
SKILL = (
    REPO
    / "modules"
    / "agent-content-packs"
    / "packs"
    / "codex-skills"
    / "items"
    / "oci-arm64-new-server-bootstrap"
    / "SKILL.md"
)


def _load_setup_builder():
    spec = importlib.util.spec_from_file_location("omni_setup_staging_builder", SETUP_BUILDER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_setup_orchestrator_is_resumable_and_fail_closed() -> None:
    text = SCRIPT.read_text(encoding="utf-8")

    assert "set -Eeuo pipefail" in text
    assert "export PYTHONDONTWRITEBYTECODE=1" in text
    assert 'STATE_DIR="${XDG_STATE_HOME:-$HOME/.local/state}/omni/oci-arm64-host-setup"' in text
    assert 'LOCK_FILE="$STATE_DIR/setup.lock"' in text
    assert "/usr/bin/flock" in text
    assert "--resume" in text
    assert "--from-step" in text
    assert "--dry-run" in text
    assert "--verify-only" in text
    assert "mark_step_complete" in text
    assert '"$STATE_DIR/completed/$MODE"' in text
    assert "SOURCE_SHA256" in text
    assert "SOURCE-MANIFEST.json" in text
    assert "verify_source_manifest" in text
    assert "raw.is_symlink" in text
    assert "actual != declared" in text
    assert '"undeclared"' in text
    assert 'row["mode"]' in text
    assert '"source_sha256": source_sha256' in text
    assert '"setup_signature": setup_signature' in text
    assert '[ "$step" != "final-verify" ]' in text
    assert "receipt_is_current" in text
    assert text.index('touch "$LOG_FILE"') < text.index('exec > >(tee -a "$LOG_FILE")')
    assert text.index('chmod 600 "$LOG_FILE"') < text.index('exec > >(tee -a "$LOG_FILE")')
    assert "trap '" in text
    assert "FAILED" in text
    assert "curl -fsSL https" not in text
    assert "| bash" not in text

    loop = text.split("for step in \"${STEPS[@]}\"; do", 1)[1]
    preflight_gate = 'if [ "$step" = "preflight" ]; then'
    assert preflight_gate in loop
    assert loop.index(preflight_gate) < loop.index('if [ "$from_seen" -eq 0 ]; then')
    assert loop.index(preflight_gate) < loop.index('if [ "$RESUME" -eq 1 ]')


def test_setup_orchestrator_covers_every_canonical_step() -> None:
    text = SCRIPT.read_text(encoding="utf-8")

    required_steps = {
        "preflight",
        "packages",
        "ubuntu-pro",
        "identity-network",
        "podman",
        "desktop-xrdp",
        "landscape",
        "fleet-agent",
        "toolchains",
        "desktop-apps",
        "agents",
        "gsd-graphify",
        "agent-content",
        "obsidian",
        "resource-governor",
        "desktop-theme",
        "final-verify",
    }
    for step in required_steps:
        assert f'"{step}"' in text

    required_commands = {
        "cloud-init status",
        "podman-compose",
        "xrdp_abnt2.py",
        "pro status --format json",
        "landscape-config --is-registered",
        "omni-fleet-agent.service",
        "node --version",
        "npm --version",
        "bun --version",
        "codex --version",
        "hermes --version",
        "check auto-mode",
        "agent-content sync",
        "obsidian-vault-pull.timer",
        "resources doctor",
        "dark-themectl.sh",
        "chatgpt",
        "google-chrome-stable",
        "chatgpt.sources",
        "google-chrome.sources",
        "browser-default-reconciler",
        "hostname -f",
        "getent ahostsv4",
        "resolvectl",
        "wg show",
    }
    for command in required_commands:
        assert command in text


def test_setup_source_builder_and_allowlist_are_fail_closed() -> None:
    script = SCRIPT.read_text(encoding="utf-8")
    builder = SETUP_BUILDER.read_text(encoding="utf-8")
    paths = [line.strip() for line in SETUP_FILE_LIST.read_text(encoding="utf-8").splitlines() if line.strip()]

    assert "build-oci-arm64-host-setup-staging.py" in RUNBOOK.read_text(encoding="utf-8")
    assert "SOURCE-MANIFEST.json" in builder
    assert "verify_manifest_tree" in builder
    assert "symlink forbidden" in builder
    assert "tarfile.PAX_FORMAT" in builder
    assert "archive_sha256" in builder
    assert "manifest_sha256" in builder
    assert "BUILD-RECEIPT.json" in builder
    assert "SCHEMA" in builder
    assert len(paths) == len(set(paths))
    assert paths == sorted(paths)
    for required in {
        ".gitignore",
        ".graphifyignore",
        "modules/fleet/configs/graphify/embeddings.json",
        "modules/fleet/configs/graphify/graphify_atius_router_patch.py",
        "modules/fleet/configs/graphify/providers.json",
        "modules/fleet/configs/graphify/sitecustomize.py",
        "modules/fleet/configs/hermes/config.yaml",
        "modules/fleet/configs/ssh/github-ed25519-known-hosts",
        "modules/fleet/configs/ssh/atius-srv3-vault-known-hosts",
        "modules/fleet/scripts/oci-arm64-host-setup.sh",
        "modules/fleet/scripts/atius-vault-env",
        "modules/fleet/scripts/graphify-atius-runtime",
        "modules/fleet/scripts/build-oci-arm64-host-setup-staging.py",
        "modules/fleet/configs/oci-arm64-host-setup-files.txt",
        "modules/fleet/configs/apt/keyrings/chatgpt-archive-keyring.gpg",
        "modules/fleet/configs/apt/keyrings/google-chrome.gpg",
        "modules/fleet/configs/apt/sources.list.d/chatgpt.sources",
        "modules/fleet/configs/apt/sources.list.d/google-chrome.sources",
        "modules/fleet/configs/systemd/resolved.conf.d/60-atius-internal.conf",
        "modules/managed-apps/scripts/install-browser-default-reconciler",
        "modules/managed-apps/scripts/browser-default-reconciler.py",
        "modules/managed-apps/systemd/browser-default-reconciler.service",
        "modules/managed-apps/systemd/browser-default-reconciler.path",
        "modules/managed-apps/systemd/browser-default-reconciler.timer",
    }:
        assert required in paths
    assert "verify_source_manifest" in script


def test_setup_source_builder_rejects_symlinked_parent(tmp_path: Path) -> None:
    builder = _load_setup_builder()
    root = tmp_path / "repo"
    outside = tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    (outside / "secret.txt").write_text("outside", encoding="utf-8")
    (root / "linked").symlink_to(outside, target_is_directory=True)

    with pytest.raises(builder.BuildError, match="symlink forbidden"):
        builder.file_record(root, Path("linked/secret.txt"))


def test_setup_source_builder_builds_and_rolls_back_atomically(tmp_path: Path, monkeypatch) -> None:
    builder = _load_setup_builder()
    root = tmp_path / "repo"
    root.mkdir()
    (root / "source.txt").write_text("new-source\n", encoding="utf-8")
    file_list = root / "files.txt"
    file_list.write_text("source.txt\n", encoding="utf-8")
    output = tmp_path / "staging"
    archive = tmp_path / "staging.tgz"

    first = builder.build(root, Path("files.txt"), output, archive, False)
    assert first["status"] == "PASS"
    assert (output / "source.txt").read_text() == "new-source\n"

    old_output = (output / "source.txt").read_bytes()
    old_archive = archive.read_bytes()
    receipt = tmp_path / "staging-BUILD-RECEIPT.json"
    old_receipt = receipt.read_bytes()
    (root / "source.txt").write_text("candidate-that-must-rollback\n", encoding="utf-8")
    monkeypatch.setattr(builder, "verify_archive", lambda *_: (_ for _ in ()).throw(builder.BuildError("forced verify failure")))

    with pytest.raises(builder.BuildError, match="forced verify failure"):
        builder.build(root, Path("files.txt"), output, archive, True)

    assert (output / "source.txt").read_bytes() == old_output
    assert archive.read_bytes() == old_archive
    assert receipt.read_bytes() == old_receipt


def test_setup_source_builder_rejects_unsafe_destinations_and_archive_members(tmp_path: Path) -> None:
    builder = _load_setup_builder()
    root = tmp_path / "repo"
    root.mkdir()
    (root / "source.txt").write_text("source\n", encoding="utf-8")
    (root / "files.txt").write_text("source.txt\n", encoding="utf-8")
    output = tmp_path / "staging"
    archive = tmp_path / "staging.tgz"

    with pytest.raises(builder.BuildError, match="outside repo root"):
        builder.build(root, Path("files.txt"), root, archive, True)

    output.symlink_to(tmp_path / "elsewhere", target_is_directory=True)
    with pytest.raises(builder.BuildError, match="symlink"):
        builder.build(root, Path("files.txt"), output, archive, True)
    output.unlink()

    receipt = tmp_path / "staging-BUILD-RECEIPT.json"
    with pytest.raises(builder.BuildError, match="distinct"):
        builder.build(root, Path("files.txt"), output, receipt, True)

    with pytest.raises(builder.BuildError, match="non-overlapping"):
        builder.build(root, Path("files.txt"), tmp_path / "nested", tmp_path / "nested/archive.tgz", True)

    malicious = tmp_path / "malicious.tgz"
    with tarfile.open(malicious, "w:gz") as tar:
        info = tarfile.TarInfo("outside-link")
        info.type = tarfile.SYMTYPE
        info.linkname = "/etc/passwd"
        tar.addfile(info, io.BytesIO())
    with pytest.raises(builder.BuildError, match="regular files"):
        builder.verify_archive(malicious, {"files": []})


def test_setup_orchestrator_does_not_copy_auth_or_replace_skill_roots() -> None:
    text = SCRIPT.read_text(encoding="utf-8")

    assert "auth.json" in text
    assert "verify_host_local_auth" in text
    assert "host-local auth must be mode 0600" in text
    assert 'must_not_exist "$HOME/.codex/auth.json"' not in text
    assert 'must_not_exist "$HOME/.hermes/auth.json"' not in text
    assert "--apply" not in text or "agent-content sync" in text
    assert "rsync --delete" not in text
    assert "mv ~/.hermes/skills" not in text
    assert "mv ~/.codex/skills" not in text
    assert "source_commit_observed_at" in text
    assert "HERMES_COMMIT" in text
    assert "Hermes pinned commit" in text
    assert "refs/hermes-update-backups/orphan-" in text
    assert "grafted-orphan-reset" in text
    assert 'git -C "$repo" reset --hard "$HERMES_COMMIT"' in text
    assert "Hermes transaction failed" in text
    assert "source/config/env/skills/venv restored" in text
    assert "managed-before.tgz" in text
    assert "venv-before.tgz" in text
    assert 'hermes backup -o "$backup/hermes-state.zip"' in text
    assert "Hermes full backup was not created" in text
    assert 'git -C "$repo" bundle verify' in text
    assert "hermes config set timezone America/Sao_Paulo" in text
    assert "hermes update --plan" not in text
    assert "agent-content all managed files converge to noop" in text
    assert 'pro attach --no-auto-enable --attach-config "$attach_config"' in text
    assert 'sudo -n pro attach "$token"' not in text
    assert "Dpkg::Options::=--force-confold" in text
    assert 'require_eq "$(npm --version)" "$NPM_VERSION"' in text
    assert 'if [ "$(codex --version' in text
    assert "apply must run inside omni-builds.slice" in text
    assert "apply_host_identity" in text
    assert 'install -m 644 -o root -g root "$rendered" /etc/hosts' in text
    assert '"$TARGET_PRIVATE_IP" "self FQDN address"' in text


def test_setup_orchestrator_uses_local_modules_not_srv1_role_clone() -> None:
    text = SCRIPT.read_text(encoding="utf-8")

    assert "--generic-host" in text
    assert "inviolable-watchdog" in text
    assert "must_not_load" in text
    assert "systemctl state query failed" in text
    assert '|| true' not in text.split("must_not_load() {", 1)[1].split("}", 1)[0]
    assert "server-analysis.timer" in text
    assert "install-build-cpu-guard.sh" in text
    assert "if ! verify_resource_governor" not in text
    assert "! verify_fleet_agent" not in text
    assert 'OMNI_SRV_ADMIN="$ROOT" "$ROOT/modules/srv1-ops/scripts/install-build-cpu-guard.sh"' in text
    assert "build guard lacks nested cgroup bypass" in text
    governor_verify = text.split("verify_resource_governor() {", 1)[1].split("apply_resource_governor() {", 1)[0]
    for unit in (
        "offload-dotbackups-to-gdrive.service",
        "offload-dotbackups-to-gdrive.timer",
        "pm2-dump-sanitizer.service",
        "pm2-dump-sanitizer.path",
        "pm2-dump-sanitizer.timer",
        "inviolable-watchdog.service",
        "inviolable-watchdog.timer",
        "server-analysis.service",
        "server-analysis.timer",
    ):
        assert unit in governor_verify
    assert "srv4-codex-local" in text
    assert "srv4-hermes-local" in text
    assert ".logs/fleet/heartbeats" in text
    assert 'FROM "TbNodes"' in text
    assert "fleet cache validation failed" in text
    assert "install_desktop_app_repositories" in text
    assert "verify_desktop_app_repositories" in text
    packages = text.split("local packages=(", 1)[1].split("\n  )", 1)[0]
    assert '"chatgpt=$CHATGPT_VERSION"' in packages
    assert '"google-chrome-stable=$CHROME_VERSION"' in packages
    for package in (
        "python3-pip",
        "python3-dev",
        "libffi-dev",
        "dnsutils",
        "postgresql-client",
        "file",
        "openssl",
        "ripgrep",
        "systemd-resolved",
        "podman-compose",
        "cockpit",
        "cockpit-podman",
    ):
        assert package in packages
    assert "apt-get install --allow-downgrades -y" in text
    assert "chatgpt-archive-keyring.gpg" in text
    assert "google-chrome.gpg" in text
    assert "install-browser-default-reconciler" in text
    assert "BROWSER_DESKTOP=google-chrome.desktop" in text
    assert "CODEX_DESKTOP=chatgpt.desktop" in text


def test_setup_orchestrator_bootstraps_fresh_host_dependencies() -> None:
    text = SCRIPT.read_text(encoding="utf-8")

    assert "apply_podman()" in text
    assert "step_podman() { apply_podman; }" in text
    assert '"podman-compose==$PODMAN_COMPOSE_VERSION"' in text
    assert 'systemctl --user enable --now podman.socket' in text
    assert 'podman network create --subnet "$podman_subnet"' in text
    assert '/usr/bin/podman network inspect srv4-podman 2>/dev/null || true' in text
    assert 'gateway == "10.10.4.1"' in text
    assert 'PODMAN_SMOKE_IMAGE="docker.io/library/alpine@sha256:' in text
    assert 'podman run --rm --pull=never' in text

    assert "install_uv()" in text
    assert "install_rust_toolchain()" in text
    assert "install_bun()" in text
    assert "install_cargo_tools()" in text
    assert "RUSTUP_INIT_SHA256" in text
    assert "CARGO_BINSTALL_ARCHIVE_SHA256" in text
    assert "ZELLIJ_BINARY_SHA256" in text
    assert "BUN_ARCHIVE_SHA256" in text
    assert "UV_ARCHIVE_SHA256" in text
    assert '"$node_dir/bin/npm" install -g "npm@$NPM_VERSION"' in text
    assert "bun upgrade" not in text
    assert "rustup update stable" not in text

    assert "bootstrap_hermes()" in text
    assert 'git clone --filter=blob:none --no-checkout "$HERMES_REPO_URL" "$repo"' in text
    assert 'UV_PROJECT_ENVIRONMENT="$repo/venv"' in text
    hermes_runtime = text.split("install_hermes_runtime() {", 1)[1].split("apply_agents() {", 1)[0]
    assert "from tools.skills_sync import sync_skills" in hermes_runtime
    agents = text.split("apply_agents() {", 1)[1].split("verify_gsd_graphify() {", 1)[0]
    assert agents.index("bootstrap_hermes") < agents.index("hermes config set timezone")
    assert "hydrate_hermes_config" in text
    assert 'verify_host_local_auth "$HOME/.hermes/auth.json"' in text
    assert "StrictHostKeyChecking=yes" in (REPO / "modules/fleet/scripts/atius-vault-env").read_text()
    vault_helper = (REPO / "modules/fleet/scripts/atius-vault-env").read_text()
    for required in ("-F /dev/null", "ProxyCommand=none", "GlobalKnownHostsFile=/dev/null", "HostKeyAlgorithms=ssh-ed25519"):
        assert required in vault_helper
    assert "atius-srv3-vault-known-hosts" in text
    assert "managed_keys" in text
    assert 'source "$vault_dump"' not in text
    assert "OMNI_SETUP_EXPECTED_SOURCE_SHA256" in text
    assert "source manifest out-of-band seal" in text
    assert "assert " not in text
    assert "hydrate_fleet_db_env" in text
    assert 'install -m 0600 "$rendered" "$HOME/.config/omni-srv-admin/fleet-db.env"' in text
    assert "Fleet DB root/user cache hash" in text
    assert "install_obsidian_repo" in text
    assert "obsidian-readonly" in text
    assert "Obsidian vault repository missing" in text
    assert "github-ed25519-known-hosts" in text
    assert "ConditionPathIsDirectory" not in (REPO / "modules/fleet/systemd/obsidian-vault-pull.service").read_text()
    assert 'if [ -s "$backup/SHA256SUMS" ]; then' in text

    known_hosts = REPO / "modules/fleet/configs/ssh/atius-srv3-vault-known-hosts"
    fingerprint = subprocess.run(
        ["ssh-keygen", "-lf", str(known_hosts)],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert "SHA256:Q9tAW0aivt009FM16K+4OnZ1h4Mk/QTSjD6Ep/zBugw" in fingerprint

    assert "install_graphify()" in text
    assert 'tool install --force "graphifyy==$GRAPHIFY_VERSION"' in text
    assert '--with "openai==$GRAPHIFY_OPENAI_VERSION"' in text
    assert "graphify_atius_router_patch.py" in text
    assert "sitecustomize.py" in text
    assert "_graphify_atius_router_stream_patched" in text
    graphify_wrapper = (REPO / "modules/fleet/scripts/graphify-atius-runtime").read_text()
    assert "PYTHONPATH" in graphify_wrapper
    assert "graphify-patches" in graphify_wrapper
    graphify = text.split("apply_gsd_graphify() {", 1)[1].split("verify_agent_content() {", 1)[0]
    assert graphify.index("install_graphify") < graphify.index("verify_gsd_graphify")


def test_setup_orchestrator_requires_trusted_xrdp_leaf() -> None:
    text = SCRIPT.read_text(encoding="utf-8")

    assert "verify_xrdp_tls" in text
    assert "/etc/xrdp/atius-rdp/server.crt.pem" in text
    assert "/etc/xrdp/atius-rdp/server.key.pem" in text
    assert "root:xrdp:640" in text
    assert "openssl verify" in text
    assert "openssl x509 -checkend 2592000" in text
    assert "SSL server : Yes" in text
    assert "DNS:atius-srv-4.atius.internal" in text
    assert "IP Address:10.14.1.14" in text
    assert "IP Address:10.100.100.18" in text


def test_runbook_and_skill_name_the_versioned_orchestrator() -> None:
    orchestrator = "modules/fleet/scripts/oci-arm64-host-setup.sh"
    assert orchestrator in RUNBOOK.read_text(encoding="utf-8")
    assert orchestrator in SKILL.read_text(encoding="utf-8")


def test_obsidian_pull_only_runtime_is_versioned_and_fail_closed() -> None:
    script = OBSIDIAN_PULL.read_text(encoding="utf-8")
    service = OBSIDIAN_SERVICE.read_text(encoding="utf-8")
    timer = OBSIDIAN_TIMER.read_text(encoding="utf-8")

    assert "set -euo pipefail" in script
    assert "git fetch --prune origin" in script
    assert 'git merge --ff-only "origin/$BRANCH"' in script
    assert "git push" not in script
    assert "git commit" not in script
    assert "dirty vault replica" in script
    assert "ExecStart=%h/.local/lib/omni-fleet/obsidian-vault-pull.sh" in service
    assert "OnUnitActiveSec=5min" in timer
    assert "Persistent=true" in timer
