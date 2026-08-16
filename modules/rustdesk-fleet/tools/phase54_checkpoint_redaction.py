#!/usr/bin/env python3
"""Value-free GUI/UAC/pre-login checkpoint projection for Phase 54.

The checker accepts only boolean markers and fixed status/checkpoint enums.
It cannot capture a screen, perform a GUI action, talk RDP, or infer a human
checkpoint from service state.  Missing or unverified checkpoints stay
``BLOCKED``/``PENDING``.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence

try:
    from phase54_preflight import Phase54PreflightBlocked, validate as _validate_preflight
except ImportError:  # pragma: no cover - direct invocation from another cwd
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from phase54_preflight import Phase54PreflightBlocked, validate as _validate_preflight


class Phase54CheckpointBlocked(RuntimeError):
    """Raised for raw GUI material or malformed checkpoint evidence."""


REPO_ROOT = Path(__file__).resolve().parents[3]
ALLOWED_TARGETS = {"horistic-srv", "GIOVANNI-W11-PC"}
CHECKPOINTS = {"horistic-lightdm-x11", "windows-uac-rdp", "windows-prelogin"}
STATUSES = {"PASS", "BLOCKED", "PENDING"}
_SECRET_KEYS = {
    "password", "private_key", "bearer_token", "client_secret", "token",
    "authorization", "authorization_header", "api_token", "secret",
    "raw_client_id", "raw_gui_payload",
}
_RAW_GUI_KEYS = {
    "screenshot", "image", "image_bytes", "screen_capture", "raw_screen",
    "gui_payload", "raw_gui_payload", "clipboard_text", "input_text",
}
_RAW_OBSERVATION_KEYS = {"id", "session_id", "fingerprint", "payload", "text", "value", "display"}
_SAFE_MARKERS = {
    "x11_active", "x11_display", "image_marker", "input_marker", "lock_logout",
    "reconnect", "reboot_recovery", "lightdm_prelogin", "uac_secure_desktop",
    "rdp_console", "rdp_session", "windows_prelogin", "service_recovery",
}
_BLOCKER_ENUMS = {
    "HUMAN_CHECKPOINT_MISSING",
    "HUMAN_VERIFICATION_MISSING",
    "OBSERVATION_MARKER_MISSING",
    "RAW_GUI_PAYLOAD_FORBIDDEN",
    "CREDENTIAL_BLOCKED",
}


def _reject_raw(value: Any, path: str = "root") -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            key_text = str(key)
            lowered = key_text.lower()
            if lowered in _SECRET_KEYS and child not in (False, None, "[REDACTED]"):
                raise Phase54CheckpointBlocked(f"secret-surface:{path}.{key_text}")
            if lowered in _RAW_GUI_KEYS:
                raise Phase54CheckpointBlocked(f"raw-gui-payload-forbidden:{path}.{key_text}")
            if lowered in _RAW_OBSERVATION_KEYS and child not in (False, None, "[REDACTED]"):
                raise Phase54CheckpointBlocked(f"raw-observation-forbidden:{path}.{key_text}")
            _reject_raw(child, f"{path}.{key_text}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _reject_raw(child, f"{path}[{index}]")
    elif isinstance(value, str) and value.lower().startswith("bearer "):
        raise Phase54CheckpointBlocked(f"secret-surface:{path}")


def _fixed_status(value: Any) -> str:
    if value not in STATUSES:
        raise Phase54CheckpointBlocked("checkpoint-status-invalid")
    return str(value)


def _expected_markers(checkpoint: str) -> set[str]:
    if checkpoint == "horistic-lightdm-x11":
        return {"x11_active", "image_marker", "input_marker", "lightdm_prelogin"}
    if checkpoint == "windows-uac-rdp":
        return {"uac_secure_desktop", "rdp_console"}
    if checkpoint == "windows-prelogin":
        return {"windows_prelogin"}
    raise Phase54CheckpointBlocked("checkpoint-unsupported")


def _canonical_marker_map(raw: Any) -> dict[str, bool]:
    if not isinstance(raw, Mapping):
        return {}
    result: dict[str, bool] = {}
    for key, value in raw.items():
        key_text = str(key)
        if key_text not in _SAFE_MARKERS:
            # Unknown marker names cannot be used to manufacture a PASS.
            continue
        if type(value) is not bool:
            raise Phase54CheckpointBlocked("checkpoint-marker-must-be-boolean")
        result[key_text] = value
    return result


def redact_checkpoint_observation(observation: Mapping[str, Any], *, target: str | None = None) -> dict[str, Any]:
    """Return a fixed-shape, value-free checkpoint result.

    A PASS requires an explicit status, ``observed=true``,
    ``human_verified=true`` and every marker required by the checkpoint.  No
    free-form evidence or requested policy is considered.
    """

    if not isinstance(observation, Mapping):
        raise Phase54CheckpointBlocked("checkpoint-observation-object-required")
    _reject_raw(observation)
    checkpoint = observation.get("checkpoint")
    if checkpoint not in CHECKPOINTS:
        raise Phase54CheckpointBlocked("checkpoint-unsupported")
    if target == "horistic-srv" and checkpoint != "horistic-lightdm-x11":
        raise Phase54CheckpointBlocked("checkpoint-target-mismatch")
    if target == "GIOVANNI-W11-PC" and checkpoint not in {"windows-uac-rdp", "windows-prelogin"}:
        raise Phase54CheckpointBlocked("checkpoint-target-mismatch")
    status = _fixed_status(observation.get("status", "PENDING"))
    observed = observation.get("observed") is True
    human_verified = observation.get("human_verified") is True
    markers = _canonical_marker_map(observation.get("markers"))
    required = _expected_markers(checkpoint)
    complete = required <= {key for key, value in markers.items() if value is True}
    if status == "PASS" and not (observed and human_verified and complete):
        raise Phase54CheckpointBlocked("checkpoint-pass-requires-human-observed-markers")
    if status == "PASS":
        blocker = None
    elif not human_verified:
        blocker = "HUMAN_VERIFICATION_MISSING"
    elif not complete:
        blocker = "OBSERVATION_MARKER_MISSING"
    else:
        blocker = "HUMAN_CHECKPOINT_MISSING"
    return {
        "schema_version": 1,
        "phase": 54,
        "checkpoint": checkpoint,
        "status": status,
        "observed": observed,
        "human_verified": human_verified,
        "markers": {key: markers.get(key, False) for key in sorted(required)},
        "blocker": blocker,
        "value_free": True,
        "secret_material_present": False,
    }


def expected_checkpoints(target: str) -> tuple[str, ...]:
    if target == "horistic-srv":
        return ("horistic-lightdm-x11",)
    if target == "GIOVANNI-W11-PC":
        return ("windows-uac-rdp", "windows-prelogin")
    raise Phase54CheckpointBlocked("target-scope-blocked")


def project_checkpoint_matrix(
    observations: Sequence[Mapping[str, Any]],
    *,
    target: str,
) -> dict[str, Any]:
    if target not in ALLOWED_TARGETS:
        raise Phase54CheckpointBlocked("target-scope-blocked")
    if not isinstance(observations, Sequence) or isinstance(observations, (str, bytes)):
        raise Phase54CheckpointBlocked("checkpoint-observations-list-required")
    projected: dict[str, dict[str, Any]] = {}
    for observation in observations:
        item = redact_checkpoint_observation(observation, target=target)
        checkpoint = item["checkpoint"]
        if checkpoint in projected:
            raise Phase54CheckpointBlocked("checkpoint-duplicate")
        projected[checkpoint] = item
    overall = "PASS"
    for checkpoint in expected_checkpoints(target):
        item = projected.get(checkpoint)
        if item is None:
            projected[checkpoint] = {
                "schema_version": 1,
                "phase": 54,
                "checkpoint": checkpoint,
                "status": "PENDING",
                "observed": False,
                "human_verified": False,
                "markers": {key: False for key in sorted(_expected_markers(checkpoint))},
                "blocker": "HUMAN_CHECKPOINT_MISSING",
                "value_free": True,
                "secret_material_present": False,
            }
        if projected[checkpoint]["status"] != "PASS":
            overall = "BLOCKED"
    return {
        "schema_version": 1,
        "phase": 54,
        "target": target,
        "state": overall,
        "value_free": True,
        "secret_material_present": False,
        "checkpoints": projected,
    }


def validate_preflight(repo: Path, receipt: Path, target: str) -> dict[str, Any]:
    try:
        return _validate_preflight(repo, receipt, target)
    except Phase54PreflightBlocked as exc:
        raise Phase54CheckpointBlocked(str(exc)) from exc


def evaluate_checkpoint_matrix(
    repo: Path,
    *,
    receipt: Path,
    target: str,
    observations: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    admission = validate_preflight(repo, receipt, target)
    result = project_checkpoint_matrix(observations, target=target)
    result["admission_state"] = admission["state"]
    return result


validate_checkpoint_matrix = evaluate_checkpoint_matrix
redact_checkpoint = redact_checkpoint_observation


def main() -> int:
    parser = argparse.ArgumentParser(description="Phase 54 GUI checkpoint redaction (fixture-only)")
    parser.add_argument("--repo", type=Path, default=REPO_ROOT)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--observations", type=Path, required=True)
    args = parser.parse_args()
    try:
        raw = json.loads(args.observations.read_text(encoding="utf-8"))
        result = evaluate_checkpoint_matrix(
            args.repo, receipt=args.receipt, target=args.target, observations=raw,
        )
    except (Phase54CheckpointBlocked, OSError, UnicodeError, json.JSONDecodeError) as exc:
        print(json.dumps({"state": "BLOCKED", "reason": str(exc), "value_free": True}, sort_keys=True))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0 if result["state"] == "PASS" else 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
