"""Vault sync must honor an external operator hold before Git/vault mutation."""

from pathlib import Path
import os
import subprocess


REPO = Path(__file__).resolve().parents[3]
SCRIPT = REPO / "modules" / "srv1-ops" / "scripts" / "sync-vault.sh"


def test_sync_vault_hold_exits_before_vault_or_git_access(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    hold = tmp_path / "sync-vault.hold"
    hold.write_text("security remediation in progress\n")
    log = tmp_path / "sync.log"
    missing_repo = tmp_path / "must-not-be-opened"

    result = subprocess.run(
        ["bash", str(SCRIPT)],
        env={
            **os.environ,
            "HOME": str(home),
            "SYNC_VAULT_HOLD_FILE": str(hold),
            "SYNC_VAULT_LOG": str(log),
            "SYNC_VAULT_REPO": str(missing_repo),
        },
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode == 0, result.stderr
    assert "HOLD: security remediation in progress" in log.read_text()
    assert not missing_repo.exists()


def test_sync_vault_default_hold_is_outside_git_vault() -> None:
    source = SCRIPT.read_text()
    assert 'HOLD_FILE="${SYNC_VAULT_HOLD_FILE:-$HOME/.local/state/omni/sync-vault.hold}"' in source
    assert source.index('if [ -e "$HOLD_FILE" ]') < source.index('cd "$VAULT"')
    assert source.index('if [ -e "$HOLD_FILE" ]') < source.index('git add -u')
