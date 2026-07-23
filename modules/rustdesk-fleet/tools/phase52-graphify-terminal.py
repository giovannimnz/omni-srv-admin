#!/usr/bin/env python3
"""Fail-closed Phase 52 post-live Graphify and frozen-contract assertion."""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import shutil
import subprocess
from typing import Any


ALLOWED_SOURCE_FILES = {
    "modules/rustdesk-fleet/tools/verify-phase52-post-live.py",
    "modules/rustdesk-fleet/tools/phase52-post-live-lanes.py",
    "modules/rustdesk-fleet/tools/phase52-graphify-terminal.py",
    "modules/rustdesk-fleet/tools/phase52-post-summary-seal.py",
    "modules/rustdesk-fleet/tests/test_phase52_post_live_successor.py",
    ".planning/workstreams/rustdesk-fleet/phases/52-supply-chain-capacity-and-recoverable-placement/52-08-PLAN.md",
    ".planning/workstreams/rustdesk-fleet/phases/52-supply-chain-capacity-and-recoverable-placement/52-09-PLAN.md",
    ".planning/workstreams/rustdesk-fleet/phases/52-supply-chain-capacity-and-recoverable-placement/52-10-PLAN.md",
    ".planning/workstreams/rustdesk-fleet/phases/52-supply-chain-capacity-and-recoverable-placement/52-08-SUMMARY.md",
    ".planning/workstreams/rustdesk-fleet/phases/52-supply-chain-capacity-and-recoverable-placement/52-09-SUMMARY.md",
    ".planning/workstreams/rustdesk-fleet/phases/52-supply-chain-capacity-and-recoverable-placement/52-10-SUMMARY.md",
    ".planning/workstreams/rustdesk-fleet/phases/52-supply-chain-capacity-and-recoverable-placement/52-VALIDATION.md",
    ".planning/workstreams/rustdesk-fleet/phases/52-supply-chain-capacity-and-recoverable-placement/52-VERIFICATION.md",
}
CONTRACT_SHA256 = "dee24466b8ab9f2127fb18688927e88d690fde28f9f9fd8899cae16bf0ddb1fa"
CONTRACT_REL = pathlib.Path("modules/rustdesk-fleet/contracts/phase52-post-live-successor.json")


def run_json(cmd: list[str], cwd: pathlib.Path) -> dict[str, Any]:
    proc = subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, check=False)
    if proc.returncode:
        raise SystemExit(f"command failed ({proc.returncode}): {' '.join(cmd)}\n{proc.stderr}")
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"non-JSON output from {' '.join(cmd)}: {exc}") from exc


def graphify_rebuild(repo: pathlib.Path, ws: str) -> None:
    chain = (
        "set -eu; graphify update . --force; "
        "cp graphify-out/graph.json .planning/graphs/graph.json; "
        "[ -f graphify-out/graph.html ] && cp graphify-out/graph.html .planning/graphs/graph.html || true; "
        "cp graphify-out/GRAPH_REPORT.md .planning/graphs/GRAPH_REPORT.md; "
        f'node "$HOME/.codex/gsd-core/bin/gsd-tools.cjs" graphify build snapshot --ws {ws}'
    )
    omni = shutil.which("omni")
    if not omni:
        raise SystemExit("omni resource-governor wrapper is required for Graphify rebuild")
    proc = subprocess.run(
        [omni, "srv1-ops", "resources", "run", "builds", "--", "zsh", "-lc", chain],
        cwd=repo,
        text=True,
        check=False,
    )
    if proc.returncode:
        raise SystemExit(f"governed Graphify rebuild failed with exit {proc.returncode}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=".")
    parser.add_argument("--ws", default="rustdesk-fleet")
    parser.add_argument("--rebuild-if-stale", action="store_true")
    args = parser.parse_args()
    repo = pathlib.Path(args.repo).resolve()
    tools = repo / ".codex/gsd-core/bin/gsd-tools.cjs"
    if not tools.exists():
        tools = pathlib.Path.home() / ".codex/gsd-core/bin/gsd-tools.cjs"

    status_cmd = ["node", str(tools), "graphify", "status", "--ws", args.ws, "--raw"]
    status = run_json(status_cmd, repo)
    if args.rebuild_if_stale and (status.get("stale") or status.get("commit_stale")):
        graphify_rebuild(repo, args.ws)
        status = run_json(status_cmd, repo)
    if status.get("stale") or status.get("commit_stale"):
        raise SystemExit("Graphify is stale or commit-stale")

    query = run_json(
        ["node", str(tools), "graphify", "query", "post-live", "--budget", "50000", "--ws", args.ws, "--raw"],
        repo,
    )
    nodes = query.get("nodes") or []
    edges = query.get("edges") or []
    if not nodes or not edges:
        raise SystemExit("post-live Graphify query returned no nodes or edges")
    rows = nodes + edges
    empty_source = [row for row in rows if not row.get("source_file")]
    if not all(row.get("_origin") == "ast" and row.get("file_type") == "code" and row.get("id") for row in empty_source):
        raise SystemExit("unexpected Graphify row without source_file")
    source_files = {row["source_file"] for row in rows if row.get("source_file")}
    if not source_files <= ALLOWED_SOURCE_FILES:
        raise SystemExit(f"Graphify source-file allowlist drift: {sorted(source_files - ALLOWED_SOURCE_FILES)}")
    verifier = "modules/rustdesk-fleet/tools/verify-phase52-post-live.py"
    if verifier not in source_files:
        raise SystemExit("frozen verifier is absent from post-live Graphify query")

    contract = repo / CONTRACT_REL
    digest = hashlib.sha256(contract.read_bytes()).hexdigest()
    if digest != CONTRACT_SHA256:
        raise SystemExit(f"frozen contract digest drift: {digest}")
    if "phase52_post_live_successor_v1" not in contract.read_text():
        raise SystemExit("frozen contract anchor missing")
    print(json.dumps({"status": "PASS", "nodes": len(nodes), "edges": len(edges), "source_files": sorted(source_files)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
