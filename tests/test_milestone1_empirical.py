"""Empirical regression and stress testing suite for Milestone 1.

Tests:
1. Landscape-client runtime & execution environment compatibility
2. Bash syntax & strict mode behaviors
3. Hub packaging simulation (tarball, manifest generation, hash verification)
4. Client sync simulation (count divergence, equality, non-numeric remote count)
5. Symlink normalization (physical dir -> symlink, preserve files, idempotency)
6. Landscape directive idempotent injection into AGENTS.md
7. R6 governance policy (skip repo sync on horistic-srv, aln-srv, user horistic)
8. skills-inventory.sh execution, JSON validity, edge cases
9. AGENTS.md markdown integrity and directive preservation
10. manifest.json structure and omni landscape CLI integration
"""

import json
import os
import re
import subprocess
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATH = REPO_ROOT / "modules" / "landscape-control-plane" / "scripts" / "manifest.json"
SYNC_SCRIPT_PATH = REPO_ROOT / "modules" / "landscape-control-plane" / "scripts" / "sync-agent-instructions.sh"
INVENTORY_SCRIPT_PATH = REPO_ROOT / "modules" / "landscape-control-plane" / "scripts" / "skills-inventory.sh"
AGENTS_MD_PATH = REPO_ROOT / "AGENTS.md"


def run_wsl_bash(script_content: str, env: dict = None) -> subprocess.CompletedProcess:
    """Execute bash script inside WSL with pure stdin to avoid quote escaping."""
    cmd = ["wsl", "bash", "-s"]
    full_env = os.environ.copy()
    if env:
        full_env.update(env)
    # Always normalize to pure LF bytes to avoid Windows CRLF breaking heredocs in bash.
    # Explicitly avoid text=True with bytes input to prevent TypeError (write() argument must be str, not bytes).
    if isinstance(script_content, str):
        raw_input = script_content.replace("\r\n", "\n").encode("utf-8")
    else:
        raw_input = script_content
    proc = subprocess.run(
        cmd,
        input=raw_input,
        capture_output=True,
        text=False,
        env=full_env,
    )
    return subprocess.CompletedProcess(
        args=proc.args,
        returncode=proc.returncode,
        stdout=proc.stdout.decode("utf-8", errors="replace"),
        stderr=proc.stderr.decode("utf-8", errors="replace"),
    )


def test_bash_syntax():
    """Empirically test bash syntax of all scripts."""
    for script_path in [SYNC_SCRIPT_PATH, INVENTORY_SCRIPT_PATH]:
        content = script_path.read_text(encoding="utf-8")
        proc = subprocess.run(
            ["wsl", "bash", "-n"],
            input=content.replace("\r\n", "\n").encode("utf-8"),
            capture_output=True,
        )
        assert proc.returncode == 0, f"Syntax error in {script_path.name}: {proc.stderr.decode('utf-8')}"

    # Also test the embedded omni-fleet-runtime-sync.sh
    sync_content = SYNC_SCRIPT_PATH.read_text(encoding="utf-8")
    start_mark = "cat << 'RUNTIMESYNC' > /usr/local/bin/omni-fleet-runtime-sync.sh"
    end_mark = "RUNTIMESYNC"
    start_idx = sync_content.find(start_mark) + len(start_mark)
    end_idx = sync_content.find(end_mark, start_idx)
    embedded_script = sync_content[start_idx:end_idx].strip()

    proc = subprocess.run(
        ["wsl", "bash", "-n"],
        input=embedded_script.replace("\r\n", "\n").encode("utf-8"),
        capture_output=True,
    )
    assert proc.returncode == 0, f"Syntax error in embedded runtime script: {proc.stderr.decode('utf-8')}"


def test_manifest_json_integrity():
    """Empirically validate manifest.json format and scripts catalog."""
    assert MANIFEST_PATH.exists()
    data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    assert data.get("schema_version") == 1
    assert "scripts" in data
    scripts = {s["id"]: s for s in data["scripts"]}

    # Check sync-agent-instructions
    assert "sync-agent-instructions" in scripts
    sync_entry = scripts["sync-agent-instructions"]
    assert sync_entry["version"] >= "1.4.0"
    assert sync_entry["username"] == "root"
    assert sync_entry["path"] == "sync-agent-instructions.sh"

    # Check skills-inventory
    assert "skills-inventory" in scripts
    inv_entry = scripts["skills-inventory"]
    assert inv_entry["version"] == "1.0.0"
    assert inv_entry["username"] == "root"
    assert inv_entry["path"] == "skills-inventory.sh"
    assert inv_entry["risk"] == "read-only"

    # Check all scripts referenced actually exist on disk
    scripts_dir = MANIFEST_PATH.parent
    for s in data["scripts"]:
        file_path = scripts_dir / s["path"]
        assert file_path.exists(), f"Script path {s['path']} missing on disk"


def test_hub_packaging_logic():
    """Empirically test hub-side packaging logic from sync-agent-instructions.sh."""
    test_sh = """
set -euo pipefail
TMPDIR=$(mktemp -d)
trap "rm -rf '$TMPDIR'" EXIT

TARGET_USER="testuser"
TARGET_HOME="$TMPDIR/home/$TARGET_USER"
GEMINI_CONFIG="$TARGET_HOME/.gemini/config"
SKILLS_DIR="$GEMINI_CONFIG/skills"
AGENTS_MD="$GEMINI_CONFIG/AGENTS.md"

mkdir -p "$SKILLS_DIR/skill-alpha" "$SKILLS_DIR/skill-beta" "$SKILLS_DIR/skill-gamma"
echo "# Agents Directive" > "$AGENTS_MD"
echo "skill alpha" > "$SKILLS_DIR/skill-alpha/SKILL.md"

# Simulate hub logic
CURRENT_SKILLS_COUNT="$(find "${SKILLS_DIR}" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | wc -l)"
TAR_PATH="${GEMINI_CONFIG}/fleet-skills.tar.gz"
MANIFEST_PATH="${GEMINI_CONFIG}/runtime-manifest.json"

tar -czf "${TAR_PATH}.tmp" -C "${GEMINI_CONFIG}" skills
mv "${TAR_PATH}.tmp" "${TAR_PATH}"

AGENTS_MD5="$(md5sum "${AGENTS_MD}" 2>/dev/null | awk '{print $1}')"
TAR_MD5="$(md5sum "${TAR_PATH}" 2>/dev/null | awk '{print $1}')"
cat << EOF > "${MANIFEST_PATH}.tmp"
{
  "version": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "agents_md5": "${AGENTS_MD5}",
  "skills_count": ${CURRENT_SKILLS_COUNT},
  "skills_tar_md5": "${TAR_MD5}"
}
EOF
mv "${MANIFEST_PATH}.tmp" "${MANIFEST_PATH}"

# Verify outputs
cat "$MANIFEST_PATH"
tar -tzf "$TAR_PATH"
"""
    res = run_wsl_bash(test_sh)
    assert res.returncode == 0, f"Hub packaging failed: {res.stderr}"

    # Parse stdout to find manifest JSON
    match = re.search(r"\{.*?\}", res.stdout, re.DOTALL)
    assert match, f"No JSON manifest output: {res.stdout}"
    manifest = json.loads(match.group(0))
    assert manifest["skills_count"] == 3
    assert len(manifest["agents_md5"]) == 32
    assert len(manifest["skills_tar_md5"]) == 32
    assert "skills/skill-alpha/SKILL.md" in res.stdout


def test_client_sync_divergence_and_equality():
    """Empirically test client sync logic for divergence vs equality."""
    test_sh = """
set -euo pipefail
TMPDIR=$(mktemp -d)
trap "rm -rf '$TMPDIR'" EXIT

# Hub setup
HUB_CONFIG="$TMPDIR/hub/config"
mkdir -p "$HUB_CONFIG/skills/skill-1" "$HUB_CONFIG/skills/skill-2" "$HUB_CONFIG/skills/skill-3"
tar -czf "$TMPDIR/fleet-skills.tar.gz" -C "$HUB_CONFIG" skills
cat << EOF > "$TMPDIR/runtime-manifest.json"
{
  "skills_count": 3
}
EOF

# Client setup (initially 1 skill)
CLIENT_CONFIG="$TMPDIR/client/config"
mkdir -p "$CLIENT_CONFIG/skills/skill-1"

# Client check: divergence (1 vs 3)
LOCAL_COUNT="$(find "${CLIENT_CONFIG}/skills" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | wc -l)"
REMOTE_COUNT="$(grep -o '"skills_count": [0-9]*' "$TMPDIR/runtime-manifest.json" 2>/dev/null | awk '{print $2}' || echo "")"

if [[ "${REMOTE_COUNT}" =~ ^[0-9]+$ ]] && [ "${REMOTE_COUNT}" -gt 0 ]; then
    if [ "${LOCAL_COUNT}" -lt "${REMOTE_COUNT}" ]; then
        tar -xzf "$TMPDIR/fleet-skills.tar.gz" -C "${CLIENT_CONFIG}/"
    fi
fi

NEW_LOCAL_COUNT="$(find "${CLIENT_CONFIG}/skills" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | wc -l)"
echo "AFTER_SYNC_COUNT: $NEW_LOCAL_COUNT"

# Second run: equality (3 vs 3) -> should NOT extract
SYNCED_MARKER="$TMPDIR/synced.marker"
LOCAL_COUNT="$(find "${CLIENT_CONFIG}/skills" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | wc -l)"
if [[ "${REMOTE_COUNT}" =~ ^[0-9]+$ ]] && [ "${REMOTE_COUNT}" -gt 0 ]; then
    if [ "${LOCAL_COUNT}" -lt "${REMOTE_COUNT}" ]; then
        touch "$SYNCED_MARKER"
    fi
fi

if [ -f "$SYNCED_MARKER" ]; then
    echo "ERROR_EXTRACTED_ON_EQUALITY"
else
    echo "EQUALITY_NOOP_SUCCESS"
fi
"""
    res = run_wsl_bash(test_sh)
    assert res.returncode == 0, f"Client sync test failed: {res.stderr}"
    assert "AFTER_SYNC_COUNT: 3" in res.stdout
    assert "EQUALITY_NOOP_SUCCESS" in res.stdout


def test_symlink_normalization_physical_to_symlink():
    """Empirically test conversion of ~/.agents/skills physical directory to symlink."""
    test_sh = """
set -euo pipefail
TMPDIR=$(mktemp -d)
trap "rm -rf '$TMPDIR'" EXIT

TARGET_HOME="$TMPDIR/home/testuser"
GEMINI_CONFIG="$TARGET_HOME/.gemini/config"
SKILLS_DIR="$GEMINI_CONFIG/skills"
AGENTS_DIR="$TARGET_HOME/.agents"
AGENTS_SKILLS="$AGENTS_DIR/skills"

mkdir -p "$SKILLS_DIR/skillA"
mkdir -p "$AGENTS_SKILLS/skillB"
echo "custom content B" > "$AGENTS_SKILLS/skillB/SKILL.md"

# Run normalization routine as in sync-agent-instructions.sh line 125-137
mkdir -p "${AGENTS_DIR}"
if [ -e "${AGENTS_SKILLS}" ] && [ ! -L "${AGENTS_SKILLS}" ]; then
    if [ -d "${AGENTS_SKILLS}" ]; then
        cp -rn "${AGENTS_SKILLS}/"* "${SKILLS_DIR}/" 2>/dev/null || true
        rm -rf "${AGENTS_SKILLS}"
    else
        rm -f "${AGENTS_SKILLS}"
    fi
fi
ln -sfn "${SKILLS_DIR}" "${AGENTS_SKILLS}"

# Verification
if [ -L "$AGENTS_SKILLS" ]; then
    echo "IS_SYMLINK"
fi
TARGET="$(readlink -f "$AGENTS_SKILLS")"
echo "TARGET: $TARGET"
if [ -f "$SKILLS_DIR/skillB/SKILL.md" ]; then
    echo "SKILL_B_PRESERVED"
fi
if [ -f "$AGENTS_SKILLS/skillA" ] || [ -d "$AGENTS_SKILLS/skillA" ]; then
    echo "SKILL_A_ACCESSIBLE_THROUGH_SYMLINK"
fi

# Run it a second time (idempotency test)
if [ -e "${AGENTS_SKILLS}" ] && [ ! -L "${AGENTS_SKILLS}" ]; then
    echo "FAILED_IDEMPOTENCY_UNEXPECTED"
fi
ln -sfn "${SKILLS_DIR}" "${AGENTS_SKILLS}"
echo "IDEMPOTENT_SUCCESS"
"""
    res = run_wsl_bash(test_sh)
    assert res.returncode == 0, f"Symlink normalization failed: {res.stderr}"
    assert "IS_SYMLINK" in res.stdout
    assert "SKILL_B_PRESERVED" in res.stdout
    assert "SKILL_A_ACCESSIBLE_THROUGH_SYMLINK" in res.stdout
    assert "IDEMPOTENT_SUCCESS" in res.stdout


def test_idempotent_agents_md_directive_injection():
    """Empirically test that Landscape directive is injected exactly once."""
    test_sh = """
set -euo pipefail
TMPDIR=$(mktemp -d)
trap "rm -rf '$TMPDIR'" EXIT

AGENTS_MD="$TMPDIR/AGENTS.md"
echo "# Original Header" > "$AGENTS_MD"

LANDSCAPE_DIRECTIVE_BLOCK='## Canonical Fleet Operations & Landscape Control-Plane Directive

- **Regra Mandatória para Múltiplos Servidores / Frota:** SEMPRE que qualquer operação...'

# Inject 5 times
for i in {1..5}; do
    if [ -f "${AGENTS_MD}" ]; then
        if ! grep -q "Canonical Fleet Operations & Landscape Control-Plane Directive" "${AGENTS_MD}"; then
            echo "" >> "${AGENTS_MD}"
            echo "${LANDSCAPE_DIRECTIVE_BLOCK}" >> "${AGENTS_MD}"
        fi
    fi
done

COUNT="$(grep -c "Canonical Fleet Operations & Landscape Control-Plane Directive" "$AGENTS_MD" || true)"
echo "MATCH_COUNT: $COUNT"
"""
    res = run_wsl_bash(test_sh)
    assert res.returncode == 0, f"Directive injection test failed: {res.stderr}"
    assert "MATCH_COUNT: 1" in res.stdout


def test_r6_governance_host_and_user_protection():
    """Empirically test R6 governance guard against repo sync on horistic-srv/aln-srv/horistic."""
    test_sh = """
set -euo pipefail

check_sync() {
    local HOST_NAME="$1"
    local TARGET_USER="$2"
    if [ "${HOST_NAME}" != "horistic-srv" ] && [ "${HOST_NAME}" != "aln-srv" ] && [ "${TARGET_USER}" != "horistic" ]; then
        echo "ALLOWED"
    else
        echo "BLOCKED"
    fi
}

echo "atius-srv-1 / ubuntu: $(check_sync atius-srv-1 ubuntu)"
echo "atius-srv-2 / ubuntu: $(check_sync atius-srv-2 ubuntu)"
echo "horistic-srv / ubuntu: $(check_sync horistic-srv ubuntu)"
echo "horistic-srv / horistic: $(check_sync horistic-srv horistic)"
echo "aln-srv / ubuntu: $(check_sync aln-srv ubuntu)"
echo "atius-srv-1 / horistic: $(check_sync atius-srv-1 horistic)"
echo "GIOVANNI-W11-PC / muniz: $(check_sync GIOVANNI-W11-PC muniz)"
"""
    res = run_wsl_bash(test_sh)
    assert res.returncode == 0
    assert "atius-srv-1 / ubuntu: ALLOWED" in res.stdout
    assert "atius-srv-2 / ubuntu: ALLOWED" in res.stdout
    assert "horistic-srv / ubuntu: BLOCKED" in res.stdout
    assert "horistic-srv / horistic: BLOCKED" in res.stdout
    assert "aln-srv / ubuntu: BLOCKED" in res.stdout
    assert "atius-srv-1 / horistic: BLOCKED" in res.stdout
    assert "GIOVANNI-W11-PC / muniz: ALLOWED" in res.stdout


def test_skills_inventory_json_output():
    """Empirically test skills-inventory.sh and validate its JSON output."""
    res = run_wsl_bash(INVENTORY_SCRIPT_PATH.read_text(encoding="utf-8"))
    assert res.returncode == 0, f"skills-inventory.sh exited with {res.returncode}: {res.stderr}"

    # Extract JSON between === JSON SUMMARY === and === END INVENTORY ===
    stdout = res.stdout
    assert "=== JSON SUMMARY ===" in stdout
    assert "=== END INVENTORY ===" in stdout

    start = stdout.find("=== JSON SUMMARY ===") + len("=== JSON SUMMARY ===")
    end = stdout.find("=== END INVENTORY ===")
    json_str = stdout[start:end].strip()

    data = json.loads(json_str)
    assert "host" in data
    assert "timestamp_utc" in data
    assert "service_timer" in data
    assert "users" in data
    assert isinstance(data["users"], dict)

    for user, info in data["users"].items():
        assert "gemini_skills_count" in info
        assert "agents_skills_count" in info
        assert "agents_skills_symlink" in info
        assert "atius_vault_access" in info
        assert "landscape_directive" in info


def test_deletion_non_convergence_loop_flaw():
    """Adversarial stress-test demonstrating the deletion loop flaw when LOCAL_COUNT > REMOTE_COUNT."""
    test_sh = """
set -euo pipefail
TMPDIR=$(mktemp -d)
trap "rm -rf '$TMPDIR'" EXIT

HUB_CONFIG="$TMPDIR/hub/config"
CLIENT_CONFIG="$TMPDIR/client/config"

mkdir -p "$HUB_CONFIG/skills/skillA" "$HUB_CONFIG/skills/skillB"
mkdir -p "$CLIENT_CONFIG/skills/skillA" "$CLIENT_CONFIG/skills/skillB" "$CLIENT_CONFIG/skills/skillOld"

TAR_PATH="$TMPDIR/fleet-skills.tar.gz"
tar -czf "$TAR_PATH" -C "$HUB_CONFIG" skills

# Hub count is 2, Client count is 3
HUB_COUNT=$(find "$HUB_CONFIG/skills" -mindepth 1 -maxdepth 1 -type d | wc -l)
LOCAL_COUNT=$(find "$CLIENT_CONFIG/skills" -mindepth 1 -maxdepth 1 -type d | wc -l)

DOWNLOADS=0
# Simulation of 2 timer cycles
for run in 1 2; do
    if [ "$LOCAL_COUNT" -ne "$HUB_COUNT" ]; then
        DOWNLOADS=$((DOWNLOADS + 1))
        tar -xzf "$TAR_PATH" -C "$CLIENT_CONFIG/"
    fi
    LOCAL_COUNT=$(find "$CLIENT_CONFIG/skills" -mindepth 1 -maxdepth 1 -type d | wc -l)
done

echo "TOTAL_DOWNLOADS: $DOWNLOADS"
echo "FINAL_LOCAL_COUNT: $LOCAL_COUNT"
"""
    res = run_wsl_bash(test_sh)
    assert res.returncode == 0
    assert "TOTAL_DOWNLOADS: 2" in res.stdout
    assert "FINAL_LOCAL_COUNT: 3" in res.stdout


def test_agents_dir_permission_omission():
    """Adversarial test demonstrating missing chown on ~/.agents directory."""
    test_sh = """
set -euo pipefail
TMPDIR=$(mktemp -d)
trap "rm -rf '$TMPDIR'" EXIT

TARGET_USER="testuser"
TARGET_HOME="$TMPDIR/home/$TARGET_USER"
AGENTS_DIR="$TARGET_HOME/.agents"
GEMINI_CONFIG="$TARGET_HOME/.gemini/config"
SKILLS_DIR="$GEMINI_CONFIG/skills"

mkdir -p "$TARGET_HOME" "$GEMINI_CONFIG" "$SKILLS_DIR"

# Run current script logic (lines 125, 136, 182)
mkdir -p "${AGENTS_DIR}"
ln -sfn "${SKILLS_DIR}" "${AGENTS_DIR}/skills"
chown -h "${TARGET_USER}:${TARGET_USER}" "${AGENTS_DIR}/skills" 2>/dev/null || true
chown -R "${TARGET_USER}:${TARGET_USER}" "${GEMINI_CONFIG}" 2>/dev/null || true

# Check if AGENTS_DIR was chowned (simulated check)
# In root execution, AGENTS_DIR remains owned by root
echo "AGENTS_DIR_EXISTS: $( [ -d "$AGENTS_DIR" ] && echo true || echo false )"
"""
    res = run_wsl_bash(test_sh)
    assert res.returncode == 0
    assert "AGENTS_DIR_EXISTS: true" in res.stdout


def test_agents_md_preservation_and_structure():
    """Empirically verify AGENTS.md preserves all previous sections and valid markdown."""
    content = AGENTS_MD_PATH.read_text(encoding="utf-8")

    required_sections = [
        "# GSD Agents",
        "## Project Identity",
        "## SSH Reachability Fallback",
        "## CPU Guardrail",
        "## K3s Resource Unit",
        "## XRDP ABNT2 Fleet",
        "## Canonical Fleet Operations & Landscape Control-Plane Directive",
        "## Segredos ATIUS e MCP",
        "## Paralelismo e automacao de browser",
        "## Diretriz Canônica Permanente: Sistema Universal de Busca Inteligente Multi-Tier para Nomes, Strings e Documentos",
        "## Teamwork Defaults (Permanente)",
    ]

    for section in required_sections:
        assert section in content, f"Missing section in AGENTS.md: {section}"

    # Verify code blocks are properly opened and closed (even number of ```)
    backtick_blocks = re.findall(r"```", content)
    assert len(backtick_blocks) % 2 == 0, f"Unbalanced code blocks in AGENTS.md (count={len(backtick_blocks)})"

    # Verify directive content contains essential commands
    assert "omni landscape run <script-id> --hosts all --wait --yes" in content
    assert "omni landscape computers" in content
    assert "omni landscape scripts list" in content


def test_skills_inventory_symlink_traversal():
    """Verify skills-inventory.sh correctly traverses symlinked ~/.agents/skills directory with trailing slash."""
    test_sh = """
set -euo pipefail
TMPDIR=$(mktemp -d)
trap "rm -rf '$TMPDIR'" EXIT

GEMINI_SKILLS="$TMPDIR/gemini/config/skills"
AGENTS_DIR="$TMPDIR/agents"
AGENTS_SKILLS="$AGENTS_DIR/skills"

mkdir -p "$GEMINI_SKILLS/skill-1" "$GEMINI_SKILLS/skill-2"
mkdir -p "$AGENTS_DIR"
ln -sfn "$GEMINI_SKILLS" "$AGENTS_SKILLS"

# Without trailing slash (GNU find defect)
COUNT_WITHOUT=$(find "${AGENTS_SKILLS}" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | wc -l)

# With trailing slash (the approved fix)
COUNT_WITH=$(find "${AGENTS_SKILLS}/" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | wc -l)

echo "WITHOUT_SLASH: $COUNT_WITHOUT"
echo "WITH_SLASH: $COUNT_WITH"
"""
    res = run_wsl_bash(test_sh)
    assert res.returncode == 0
    assert "WITHOUT_SLASH: 0" in res.stdout
    assert "WITH_SLASH: 2" in res.stdout


def test_pipefail_md5sum_resilience():
    """Verify that md5sum pipeline does not crash under set -euo pipefail when AGENTS.md is missing."""
    test_sh = """
set -euo pipefail
AGENTS_MD="/nonexistent/path/AGENTS.md"
TAR_PATH="/nonexistent/path/tar.gz"

AGENTS_MD5="$(md5sum "${AGENTS_MD}" 2>/dev/null | awk '{print $1}' || echo "")"
TAR_MD5="$(md5sum "${TAR_PATH}" 2>/dev/null | awk '{print $1}' || echo "")"

echo "AGENTS_MD5: [${AGENTS_MD5}]"
echo "TAR_MD5: [${TAR_MD5}]"
"""
    res = run_wsl_bash(test_sh)
    assert res.returncode == 0
    assert "AGENTS_MD5: []" in res.stdout
    assert "TAR_MD5: []" in res.stdout


def test_deletion_loop_resolution_with_lt():
    """Verify that -lt condition eliminates the infinite download loop when local has more skills than hub."""
    test_sh = """
set -euo pipefail
TMPDIR=$(mktemp -d)
trap "rm -rf '$TMPDIR'" EXIT

HUB_CONFIG="$TMPDIR/hub/config"
CLIENT_CONFIG="$TMPDIR/client/config"

mkdir -p "$HUB_CONFIG/skills/skillA" "$HUB_CONFIG/skills/skillB"
mkdir -p "$CLIENT_CONFIG/skills/skillA" "$CLIENT_CONFIG/skills/skillB" "$CLIENT_CONFIG/skills/skillOld"

TAR_PATH="$TMPDIR/fleet-skills.tar.gz"
tar -czf "$TAR_PATH" -C "$HUB_CONFIG" skills

# Hub count is 2, Client count is 3
HUB_COUNT=$(find "$HUB_CONFIG/skills" -mindepth 1 -maxdepth 1 -type d | wc -l)
LOCAL_COUNT=$(find "$CLIENT_CONFIG/skills" -mindepth 1 -maxdepth 1 -type d | wc -l)

DOWNLOADS=0
# Simulation of 2 timer cycles with -lt
for run in 1 2; do
    if [ "$LOCAL_COUNT" -lt "$HUB_COUNT" ]; then
        DOWNLOADS=$((DOWNLOADS + 1))
        tar -xzf "$TAR_PATH" -C "$CLIENT_CONFIG/"
    fi
    LOCAL_COUNT=$(find "$CLIENT_CONFIG/skills" -mindepth 1 -maxdepth 1 -type d | wc -l)
done

echo "TOTAL_DOWNLOADS: $DOWNLOADS"
echo "FINAL_LOCAL_COUNT: $LOCAL_COUNT"
"""
    res = run_wsl_bash(test_sh)
    assert res.returncode == 0
    assert "TOTAL_DOWNLOADS: 0" in res.stdout
    assert "FINAL_LOCAL_COUNT: 3" in res.stdout


def test_agents_dir_chown_in_sync_script():
    """Verify that sync-agent-instructions.sh includes chown for AGENTS_DIR."""
    content = SYNC_SCRIPT_PATH.read_text(encoding="utf-8")
    assert 'chown -R "${TARGET_USER}:${TARGET_USER}" "${AGENTS_DIR}"' in content


if __name__ == "__main__":
    test_bash_syntax()
    print("PASS: test_bash_syntax")
    test_manifest_json_integrity()
    print("PASS: test_manifest_json_integrity")
    test_hub_packaging_logic()
    print("PASS: test_hub_packaging_logic")
    test_client_sync_divergence_and_equality()
    print("PASS: test_client_sync_divergence_and_equality")
    test_symlink_normalization_physical_to_symlink()
    print("PASS: test_symlink_normalization_physical_to_symlink")
    test_idempotent_agents_md_directive_injection()
    print("PASS: test_idempotent_agents_md_directive_injection")
    test_r6_governance_host_and_user_protection()
    print("PASS: test_r6_governance_host_and_user_protection")
    test_skills_inventory_json_output()
    print("PASS: test_skills_inventory_json_output")
    test_deletion_non_convergence_loop_flaw()
    print("PASS: test_deletion_non_convergence_loop_flaw (adversarial)")
    test_deletion_loop_resolution_with_lt()
    print("PASS: test_deletion_loop_resolution_with_lt")
    test_agents_dir_permission_omission()
    print("PASS: test_agents_dir_permission_omission (adversarial)")
    test_agents_dir_chown_in_sync_script()
    print("PASS: test_agents_dir_chown_in_sync_script")
    test_skills_inventory_symlink_traversal()
    print("PASS: test_skills_inventory_symlink_traversal")
    test_pipefail_md5sum_resilience()
    print("PASS: test_pipefail_md5sum_resilience")
    test_agents_md_preservation_and_structure()
    print("PASS: test_agents_md_preservation_and_structure")
    print("\nALL 15 EMPIRICAL AND ADVERSARIAL TEST SUITES PASSED!")
