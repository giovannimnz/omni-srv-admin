#!/usr/bin/env python3
"""Rebuild and commit the external Phase 52 seal after the GSD SUMMARY commit."""

from __future__ import annotations

import argparse
import pathlib
import subprocess


PHASE_DIR = pathlib.Path(".planning/workstreams/rustdesk-fleet/phases/52-supply-chain-capacity-and-recoverable-placement")
EVIDENCE_DIR = pathlib.Path(".planning/workstreams/rustdesk-fleet/evidence")
MODULE_DIR = pathlib.Path("modules/rustdesk-fleet")
MANIFEST = EVIDENCE_DIR / "phase52-scoped-manifest.json"
HYGIENE = EVIDENCE_DIR / "phase52-secret-hygiene.json"
SCAN_OUT = EVIDENCE_DIR / ".phase52-secret-scan.out"


def run(repo: pathlib.Path, args: list[str], *, stdout=None) -> None:
    proc = subprocess.run(args, cwd=repo, text=True, stdout=stdout, stderr=subprocess.PIPE, check=False)
    if proc.returncode:
        raise SystemExit(f"command failed ({proc.returncode}): {' '.join(args)}\n{proc.stderr}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=".")
    parser.add_argument("--commit", action="store_true")
    args = parser.parse_args()
    repo = pathlib.Path(args.repo).resolve()
    scope = [
        "python3",
        "modules/rustdesk-fleet/tools/phase52-scope-manifest.py",
        "write",
        "--repo",
        ".",
        "--manifest",
        str(MANIFEST),
        "--scope",
        str(MODULE_DIR),
        "--scope",
        str(PHASE_DIR),
    ]
    run(repo, scope)
    SCAN_OUT.unlink(missing_ok=True)
    try:
        with SCAN_OUT.open("w", encoding="utf-8") as handle:
            run(
                repo,
                [
                    "bash",
                    "scripts/sso-secret-hygiene-scan.sh",
                    str(MODULE_DIR),
                    str(PHASE_DIR),
                ],
                stdout=handle,
            )
        run(
            repo,
            [
                "python3",
                "modules/rustdesk-fleet/tools/verify-phase52-post-live.py",
                "record-secret-hygiene",
                "--repo",
                ".",
                "--input",
                str(SCAN_OUT),
                "--input",
                str(MANIFEST),
                "--input",
                "modules/rustdesk-fleet/evidence/phase52/post-live/phase53-interval-audit.json",
                "--input",
                "modules/rustdesk-fleet/evidence/phase52/post-live/retained-phase52-audit.json",
                "--input",
                "modules/rustdesk-fleet/evidence/phase52/post-live/pytest-lanes-verdict.json",
                "--input",
                str(PHASE_DIR / "52-10-CLOSEOUT.json"),
                "--out",
                str(HYGIENE),
            ],
        )
        run(
            repo,
            [
                "python3",
                "modules/rustdesk-fleet/tools/verify-phase52-post-live.py",
                "verify-closeout-inputs",
                "--input",
                str(HYGIENE),
                "--input",
                str(MANIFEST),
                "--input",
                str(PHASE_DIR / "52-10-CLOSEOUT.json"),
            ],
        )
    finally:
        SCAN_OUT.unlink(missing_ok=True)
    run(repo, [*scope[:2], "verify", *scope[3:]])
    if args.commit:
        run(repo, ["git", "add", str(MANIFEST), str(HYGIENE)])
        run(repo, ["git", "commit", "-m", "docs(52-10): seal post-summary hygiene"])
        run(repo, [*scope[:2], "verify", *scope[3:]])
    print('{"status":"PASS","post_summary":true,"committed":' + ("true" if args.commit else "false") + "}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
