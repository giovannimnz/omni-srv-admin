"""Contract tests for the SRV-1 RustDesk public edge."""

from pathlib import Path
import os
import shutil
import subprocess



REPO = Path(__file__).resolve().parents[3]
ROOT = REPO / "modules" / "srv1-ops" / "apps" / "rustdesk"


def test_edge_uses_approved_external_ports_and_same_host_native_targets() -> None:
    source = (ROOT / "atius-rustdesk-edge.nft").read_text()
    expected = {
        'iifname "enp0s6" ip daddr 10.0.0.238 tcp dport 34100 counter dnat ip to 10.0.0.238:21115',
        'iifname "enp0s6" ip daddr 10.0.0.238 tcp dport 34125 counter dnat ip to 10.0.0.238:21116',
        'iifname "enp0s6" ip daddr 10.0.0.238 udp dport 34125 counter dnat ip to 10.0.0.238:21116',
        'iifname "enp0s6" ip daddr 10.0.0.238 tcp dport 34126 counter dnat ip to 10.0.0.238:21117',
    }
    assert all(item in source for item in expected)
    assert "10.21.1.21" not in source
    assert "34101" not in source
    assert "34099" not in source


def test_edge_blocks_direct_public_native_ports_but_not_private_interfaces() -> None:
    source = (ROOT / "atius-rustdesk-edge.nft").read_text()
    assert 'iifname "enp0s6" ip daddr 10.0.0.238 tcp dport { 21114, 21115, 21116, 21117, 21118, 21119 } counter drop' in source
    assert 'iifname "enp0s6" ip daddr 10.0.0.238 udp dport 21116 counter drop' in source
    assert 'iifname "enp0s6" meta nfproto ipv6 meta l4proto udp udp dport { 21116, 34125 } counter drop' in source
    assert source.count('ct original ip daddr 10.0.0.238') == 4
    assert 'meta nfproto ipv6 meta l4proto tcp tcp dport { 21114, 21115, 21116, 21117, 21118, 21119, 34100, 34125, 34126 } counter drop' in source
    assert 'iifname "enp1s0"' not in source
    assert 'iifname "wg100"' not in source


def test_edge_service_is_persistent_and_owns_only_its_table() -> None:
    source = (ROOT / "atius-rustdesk-edge.service").read_text()
    assert "nftables.service" in source
    assert "ExecStart=/usr/local/lib/atius-rustdesk/apply-edge.sh" in source
    assert "ExecReload=/usr/local/lib/atius-rustdesk/apply-edge.sh" in source
    assert "| /usr/sbin/nft" not in source
    assert "ExecStop=" not in source
    assert "WantedBy=multi-user.target" in source


def test_edge_applicator_is_fail_closed_and_validates_before_apply() -> None:
    source = (ROOT / "apply-rustdesk-edge.sh").read_text()
    assert "set -euo pipefail" in source
    assert '[ -f "$POLICY" ] && [ ! -L "$POLICY" ]' in source
    assert '"$NFT_BIN" -c -f "$batch"' in source
    assert '"$NFT_BIN" -f "$batch"' in source
    assert source.index('"$NFT_BIN" -c -f "$batch"') < source.index('"$NFT_BIN" -f "$batch"')


def test_edge_applicator_missing_policy_never_invokes_nft(tmp_path: Path) -> None:
    marker = tmp_path / "nft-called"
    fake_nft = tmp_path / "nft"
    fake_nft.write_text(f"#!/bin/sh\ntouch {marker}\nexit 0\n")
    fake_nft.chmod(0o755)
    result = subprocess.run(
        ["bash", str(ROOT / "apply-rustdesk-edge.sh")],
        env={**os.environ, "NFT_BIN": str(fake_nft), "POLICY": str(tmp_path / "missing.nft")},
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert not marker.exists()


def test_edge_applicator_invalid_policy_checks_but_never_applies(tmp_path: Path) -> None:
    marker = tmp_path / "nft.calls"
    fake_nft = tmp_path / "nft"
    fake_nft.write_text(
        "#!/bin/sh\n"
        f'printf "%s\\n" "$*" >> {marker}\n'
        'if [ "$1" = list ]; then exit 0; fi\n'
        'if [ "$1" = -c ]; then exit 1; fi\n'
        'exit 99\n'
    )
    fake_nft.chmod(0o755)
    policy = tmp_path / "invalid.nft"
    policy.write_text("table inet atius_rustdesk_edge {\n    INVALID\n}\n")
    policy.chmod(0o644)
    result = subprocess.run(
        ["bash", str(ROOT / "apply-rustdesk-edge.sh")],
        env={
            **os.environ,
            "NFT_BIN": str(fake_nft),
            "POLICY": str(policy),
            "EXPECTED_POLICY_UID": str(os.getuid()),
            "RUNTIME_DIR": str(tmp_path),
        },
        capture_output=True,
        text=True,
    )
    calls = marker.read_text().splitlines()
    assert calls[0].startswith("list table inet atius_rustdesk_edge")
    assert any(call.startswith("-c -f ") for call in calls)
    assert not any(call.startswith("-f ") for call in calls)


def test_edge_apply_reapply_and_invalid_policy_are_transactional_in_netns() -> None:
    if not all((shutil.which("unshare"), Path("/usr/sbin/nft").exists())):
        __import__("pytest").skip("unshare/nft unavailable")
    script = f'''set -euo pipefail
tmp=$(mktemp -d); trap 'rm -rf "$tmp"' EXIT
install -m 0600 {ROOT / "atius-rustdesk-edge.nft"} "$tmp/policy.nft"
/usr/sbin/nft add table inet unrelated
/usr/sbin/nft add chain inet unrelated keep
NFT_BIN=/usr/sbin/nft POLICY="$tmp/policy.nft" EXPECTED_POLICY_UID=0 RUNTIME_DIR="$tmp" {ROOT / "apply-rustdesk-edge.sh"}
before=$(/usr/sbin/nft list table inet atius_rustdesk_edge | sha256sum | cut -d' ' -f1)
NFT_BIN=/usr/sbin/nft POLICY="$tmp/policy.nft" EXPECTED_POLICY_UID=0 RUNTIME_DIR="$tmp" {ROOT / "apply-rustdesk-edge.sh"}
after=$(/usr/sbin/nft list table inet atius_rustdesk_edge | sha256sum | cut -d' ' -f1)
test "$before" = "$after"
/usr/sbin/nft list table inet unrelated >/dev/null
printf 'table inet atius_rustdesk_edge {{ INVALID }}\n' > "$tmp/invalid.nft"
if NFT_BIN=/usr/sbin/nft POLICY="$tmp/invalid.nft" EXPECTED_POLICY_UID=0 RUNTIME_DIR="$tmp" {ROOT / "apply-rustdesk-edge.sh"}; then exit 99; fi
final=$(/usr/sbin/nft list table inet atius_rustdesk_edge | sha256sum | cut -d' ' -f1)
test "$before" = "$final"
/usr/sbin/nft list table inet unrelated >/dev/null
'''
    result = subprocess.run(
        ["sudo", "-n", "unshare", "-n", "bash", "-c", script],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr


def test_edge_guard_reloads_atomic_policy_every_minute() -> None:
    service = (ROOT / "atius-rustdesk-edge-guard.service").read_text()
    timer = (ROOT / "atius-rustdesk-edge-guard.timer").read_text()
    assert "Requires=atius-rustdesk-edge.service" in service
    assert "systemctl reload atius-rustdesk-edge.service" in service
    assert "OnUnitActiveSec=1min" in timer
    assert "Persistent=true" in timer
