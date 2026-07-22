#!/usr/bin/env python3
"""Fail-closed Phase 52 RustDesk supply/capacity/recovery validator."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


SUPPLY_CONTRACT = Path("modules/rustdesk-fleet/contracts/supply-chain.json")
SUPPLY_OBSERVATION = Path("modules/rustdesk-fleet/evidence/phase52/supply-observation.json")
SERVER_COMMIT = "9bae9f2f39d92c4b4ba2e28e089da5071897b22e"
CLIENT_COMMIT = "6c578292e8ebbbec708b76986ba8c4bc7c509747"
MULTIARCH_DIGEST = "sha256:10818ec05b179039c6660f4d8e74b303f0db2858bbad2b18e24992ea22d54cd6"
ARM64_IMAGE_DIGEST = "sha256:17c3422e0a6a65199ef69ac5cbb265ce9314a04524afcf9bb7a374fec0b1c208"
ZIP_SHA256 = "4998dd6d32431f9aaf5841663339793bc154d7152313e128832d6b610580abe4"
DEB_SHA256 = "ce62c996f14d33f3bbe3a330e953644a44bace7f05885a7953f7395d69fb49c0"
MSI_SHA256 = "c87d2f4cef2a5acd6003b6507dcfbf5d5168a256db082cd90b54d35193224aaa"
CANDIDATES = ("atius-srv-2", "atius-srv-3", "horistic-srv")


@dataclass(frozen=True)
class Finding:
    category: str
    path: str
    location: str


@dataclass
class CheckResult:
    id: str
    status: str
    evidence_ids: list[str] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)


def load_json_strict(path: Path) -> Any:
    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate JSON key rejected")
            result[key] = value
        return result

    try:
        return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=reject_duplicates)
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON at {path.name}:{exc.lineno}") from None


def validate_repo_path(repo: Path, candidate: Path) -> Path:
    root = repo.resolve()
    resolved = candidate.resolve(strict=False)
    if not resolved.is_relative_to(root):
        raise ValueError("path is outside repository")
    return resolved


def derive_overall_status(results: list[CheckResult]) -> str:
    if any(item.status == "FAIL" for item in results):
        return "FAIL"
    if any(item.status == "BLOCKED" for item in results):
        return "BLOCKED"
    return "PASS"


def exit_code_for_status(status: str) -> int:
    return {"PASS": 0, "FAIL": 1, "BLOCKED": 2}[status]


def _finding(category: str, source: str, location: str = "contract") -> Finding:
    return Finding(category=category, path=source, location=location)


def _result(status: str, categories: list[str], source: str) -> CheckResult:
    return CheckResult(
        id="P52-SUPPLY-001",
        status=status,
        evidence_ids=["P52-EV-SUPPLY"],
        findings=[_finding(category, source) for category in sorted(set(categories))],
    )


def _exact_keys(value: Any, expected: set[str]) -> bool:
    return isinstance(value, dict) and set(value) == expected


def _positive_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _sha256(value: Any, prefix: bool = False) -> bool:
    pattern = r"sha256:[0-9a-f]{64}" if prefix else r"[0-9a-f]{64}"
    return isinstance(value, str) and re.fullmatch(pattern, value) is not None


def validate_supply_contract(
    payload: dict[str, Any], source: str = "modules/rustdesk-fleet/contracts/supply-chain.json"
) -> CheckResult:
    errors: list[str] = []
    if not _exact_keys(payload, {"schema_version", "workstream", "policy", "server", "clients"}):
        return _result("FAIL", ["contract-shape"], source)
    if payload.get("schema_version") != 1 or payload.get("workstream") != "rustdesk-fleet":
        errors.append("contract-shape")

    policy = payload.get("policy")
    if not _exact_keys(
        policy,
        {
            "automatic_pin_refresh",
            "build_on_target",
            "candidate_admission_performed",
            "managed_cache_root",
            "observation_ttl_seconds",
            "windows_install_performed",
        },
    ):
        errors.append("contract-shape")
        policy = policy if isinstance(policy, dict) else {}
    if policy.get("automatic_pin_refresh") is not False:
        errors.append("automatic-pin-refresh")
    if policy.get("build_on_target") is not False:
        errors.append("target-build-enabled")
    if policy.get("candidate_admission_performed") is not False:
        errors.append("candidate-admission-claimed")
    if policy.get("windows_install_performed") is not False:
        errors.append("windows-install-attempt")
    if not _positive_int(policy.get("observation_ttl_seconds")):
        errors.append("invalid-observation-ttl")
    cache_root = policy.get("managed_cache_root")
    if not isinstance(cache_root, str) or not cache_root.startswith("/") or "/GitHub/omni-srv-admin" in cache_root:
        errors.append("managed-cache-inside-repo")

    server = payload.get("server")
    if not _exact_keys(
        server,
        {
            "version",
            "tag",
            "commit",
            "git_repository",
            "release_api_url",
            "candidates",
            "classic_image",
            "release_zip",
        },
    ):
        errors.append("contract-shape")
        server = server if isinstance(server, dict) else {}
    if server.get("version") != "1.1.15" or server.get("tag") != "1.1.15":
        errors.append("mutable-reference" if server.get("tag") == "latest" else "server-version-drift")
    if server.get("commit") != SERVER_COMMIT:
        errors.append("server-commit-drift")
    if server.get("git_repository") != "https://github.com/rustdesk/rustdesk-server.git":
        errors.append("server-source-drift")
    if server.get("release_api_url") != "https://api.github.com/repos/rustdesk/rustdesk-server/releases/tags/1.1.15":
        errors.append("server-source-drift")

    image = server.get("classic_image")
    image_keys = {
        "repository",
        "tag_reference",
        "immutable_reference",
        "registry_tag_api_url",
        "multiarch_digest",
        "linux_arm64_digest",
        "architecture",
        "os",
        "cache_path",
        "phase52_action",
        "install_phase",
    }
    if not _exact_keys(image, image_keys):
        errors.append("contract-shape")
        image = image if isinstance(image, dict) else {}
    if image.get("multiarch_digest") != MULTIARCH_DIGEST or not _sha256(image.get("multiarch_digest"), True):
        errors.append("multiarch-digest-drift")
    if image.get("linux_arm64_digest") != ARM64_IMAGE_DIGEST or not _sha256(
        image.get("linux_arm64_digest"), True
    ):
        errors.append("arm64-digest-drift")
    if image.get("architecture") != "arm64" or image.get("os") != "linux":
        errors.append("server-architecture-drift")
    if image.get("immutable_reference") != f"docker.io/rustdesk/rustdesk-server@{ARM64_IMAGE_DIGEST}":
        errors.append("mutable-reference")
    if image.get("phase52_action") != "verify-and-stage" or image.get("install_phase") != 53:
        errors.append("phase-boundary-drift")

    release_zip = server.get("release_zip")
    artifact_keys = {
        "asset_name",
        "source_url",
        "sha256",
        "size_bytes",
        "architecture",
        "cache_path",
        "phase52_action",
        "install_phase",
    }
    if not _exact_keys(release_zip, artifact_keys):
        errors.append("contract-shape")
        release_zip = release_zip if isinstance(release_zip, dict) else {}
    if release_zip.get("sha256") != ZIP_SHA256 or not _sha256(release_zip.get("sha256")):
        errors.append("release-zip-checksum-drift")
    if release_zip.get("architecture") != "linux-arm64v8":
        errors.append("server-architecture-drift")
    if not _positive_int(release_zip.get("size_bytes")):
        errors.append("invalid-byte-size")

    candidates = server.get("candidates")
    if not isinstance(candidates, list) or len(candidates) != 3:
        errors.append("candidate-set-drift")
        candidates = candidates if isinstance(candidates, list) else []
    elif [item.get("host") for item in candidates if isinstance(item, dict)] != list(CANDIDATES):
        errors.append("candidate-set-drift")
    candidate_keys = {
        "host",
        "linux_arm64_digest",
        "selected",
        "client_colocation_if_selected",
        "server_identity_domain",
        "future_client_identity_domain",
    }
    for index, candidate in enumerate(candidates):
        if not _exact_keys(candidate, candidate_keys):
            errors.append("candidate-shape")
            continue
        if candidate.get("linux_arm64_digest") != ARM64_IMAGE_DIGEST:
            errors.append("candidate-artifact-drift")
        if candidate.get("selected") is not False:
            errors.append("candidate-admission-claimed")
        expected_colocation = index == 2
        if candidate.get("client_colocation_if_selected") is not expected_colocation:
            errors.append("horistic-colocation-drift")
        if candidate.get("server_identity_domain") == candidate.get("future_client_identity_domain"):
            errors.append("identity-domain-conflation")

    clients = payload.get("clients")
    if not _exact_keys(
        clients,
        {"version", "tag", "commit", "git_repository", "release_api_url", "linux_arm64_deb", "windows_x86_64_msi"},
    ):
        errors.append("contract-shape")
        clients = clients if isinstance(clients, dict) else {}
    if clients.get("version") != "1.4.9" or clients.get("tag") != "1.4.9":
        errors.append("mutable-reference" if clients.get("tag") == "latest" else "client-version-drift")
    if clients.get("commit") != CLIENT_COMMIT:
        errors.append("client-commit-drift")
    if clients.get("git_repository") != "https://github.com/rustdesk/rustdesk.git":
        errors.append("client-source-drift")
    if clients.get("release_api_url") != "https://api.github.com/repos/rustdesk/rustdesk/releases/tags/1.4.9":
        errors.append("client-source-drift")

    deb = clients.get("linux_arm64_deb")
    deb_keys = artifact_keys | {"fleet_install_phase"}
    if not _exact_keys(deb, deb_keys):
        errors.append("contract-shape")
        deb = deb if isinstance(deb, dict) else {}
    if deb.get("sha256") != DEB_SHA256 or not _sha256(deb.get("sha256")):
        errors.append("linux-deb-checksum-drift")
    if deb.get("architecture") != "arm64":
        errors.append("linux-client-architecture-drift")
    if deb.get("phase52_action") != "verify-and-stage" or deb.get("install_phase") != 54 or deb.get(
        "fleet_install_phase"
    ) != 55:
        errors.append("phase-boundary-drift")
    if not _positive_int(deb.get("size_bytes")):
        errors.append("invalid-byte-size")

    msi = clients.get("windows_x86_64_msi")
    if not _exact_keys(msi, artifact_keys):
        errors.append("contract-shape")
        msi = msi if isinstance(msi, dict) else {}
    if msi.get("sha256") != MSI_SHA256 or not _sha256(msi.get("sha256")):
        errors.append("windows-msi-checksum-drift")
    if msi.get("architecture") != "x86_64":
        errors.append("windows-client-architecture-drift")
    if msi.get("phase52_action") != "verify-and-stage" or msi.get("install_phase") != 54:
        errors.append("windows-install-attempt")
    if not _positive_int(msi.get("size_bytes")):
        errors.append("invalid-byte-size")

    for artifact in (image, release_zip, deb, msi):
        cache_path = artifact.get("cache_path") if isinstance(artifact, dict) else None
        if not isinstance(cache_path, str) or not isinstance(cache_root, str) or not cache_path.startswith(f"{cache_root}/"):
            errors.append("managed-cache-path-drift")
        source_url = artifact.get("source_url") if isinstance(artifact, dict) else None
        if source_url is not None and (not isinstance(source_url, str) or not source_url.startswith("https://github.com/rustdesk/")):
            errors.append("artifact-source-drift")

    return _result("PASS" if not errors else "FAIL", errors, source)


def validate_supply_observation(
    observation: dict[str, Any], contract: dict[str, Any], source: str = "supply-observation.json"
) -> CheckResult:
    """Task 52-01-02 extends this seam with fresh official-source checks."""
    if not isinstance(observation, dict):
        return _result("BLOCKED", ["observation-missing"], source)
    return _result("BLOCKED", ["observation-not-implemented"], source)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def collect_input_digests(repo: Path, paths: list[Path] | tuple[Path, ...]) -> list[dict[str, str]]:
    root = repo.resolve()
    rows: list[dict[str, str]] = []
    for path in paths:
        candidate = path if path.is_absolute() else root / path
        resolved = validate_repo_path(root, candidate)
        if not resolved.is_file():
            raise ValueError("report input is missing")
        rows.append({"path": resolved.relative_to(root).as_posix(), "sha256": _sha256_file(resolved)})
    return sorted(rows, key=lambda item: item["path"])


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--only", choices=("supply",), default="supply")
    parser.add_argument("--evidence-dir", type=Path, default=SUPPLY_OBSERVATION.parent)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo = args.repo.resolve()
    try:
        contract_path = validate_repo_path(repo, repo / SUPPLY_CONTRACT)
        contract = load_json_strict(contract_path)
        contract_result = validate_supply_contract(contract, contract_path.relative_to(repo).as_posix())
        if contract_result.status != "PASS":
            print(json.dumps({"status": contract_result.status, "check": contract_result.id}, sort_keys=True))
            return exit_code_for_status(contract_result.status)
        observation_path = validate_repo_path(repo, repo / args.evidence_dir / SUPPLY_OBSERVATION.name)
        if not observation_path.is_file():
            print(json.dumps({"status": "BLOCKED", "check": "P52-SUPPLY-001"}, sort_keys=True))
            return 2
        result = validate_supply_observation(load_json_strict(observation_path), contract)
    except (OSError, ValueError) as exc:
        print(f"BLOCKED: {exc.__class__.__name__}", file=sys.stderr)
        return 2
    print(json.dumps({"status": result.status, "check": result.id}, sort_keys=True))
    return exit_code_for_status(result.status)


if __name__ == "__main__":
    raise SystemExit(main())
