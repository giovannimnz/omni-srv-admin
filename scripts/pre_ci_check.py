#!/usr/bin/env python3
"""
Canonical Pre-CI Verification Gates for omni-srv-admin
Enforces the 5 Canonical Gates before commit/push.
"""

import sys
import os
import ast
import subprocess
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

def log_gate(gate_num: int, title: str):
    print(f"\n========================================================")
    print(f" GATE {gate_num}: {title}")
    print(f"========================================================")

def run_cmd(cmd, cwd=REPO_ROOT, check=True):
    cmd_str = ' '.join(cmd) if isinstance(cmd, list) else cmd
    res = subprocess.run(cmd, cwd=cwd, shell=isinstance(cmd, str), capture_output=True, text=True)
    if check and res.returncode != 0:
        print(f"[ERROR] Command failed with exit code {res.returncode}")
        if res.stdout:
            print(f"[STDOUT]\n{res.stdout}")
        if res.stderr:
            print(f"[STDERR]\n{res.stderr}")
        return False, res.stdout, res.stderr
    return True, res.stdout, res.stderr

def gate_1_git_hygiene():
    log_gate(1, "Git Hygiene & Untracked Files Check")
    success, stdout, _ = run_cmd(["git", "status", "--porcelain"])
    if not success:
        return False
    
    dirty_lines = [line for line in stdout.splitlines() if line.strip()]
    dangerous = []
    for line in dirty_lines:
        file_path = line[3:].strip()
        if file_path.endswith((".key", ".pem", ".p12", ".tar.gz", ".env.local")):
            dangerous.append(file_path)
    
    if dangerous:
        print(f"[FAIL] Dangerous unignored files detected: {dangerous}")
        return False
    
    print(f"[PASS] Git hygiene verified. {len(dirty_lines)} modified/untracked files.")
    return True

def gate_2_python_syntax():
    log_gate(2, "Python Syntax & AST Compilation")
    py_files = list(REPO_ROOT.glob("cli/**/*.py")) + \
               list(REPO_ROOT.glob("modules/**/*.py")) + \
               list(REPO_ROOT.glob("scripts/**/*.py")) + \
               list(REPO_ROOT.glob("tests/**/*.py"))
    
    errors = []
    for py in py_files:
        try:
            with open(py, "rb") as f:
                ast.parse(f.read(), filename=str(py))
        except SyntaxError as e:
            errors.append((py, str(e)))
            print(f"[FAIL] Syntax error in {py}: {e}")
    
    if errors:
        print(f"[FAIL] {len(errors)} Python files failed AST parsing.")
        return False
    
    print(f"[PASS] {len(py_files)} Python files compiled successfully without syntax errors.")
    return True

def gate_3_shell_syntax():
    log_gate(3, "Shell Scripts Syntax Check (bash -n)")
    sh_files = [str(p) for p in REPO_ROOT.glob("scripts/**/*.sh")] + \
               [str(p) for p in REPO_ROOT.glob("modules/**/*.sh")] + \
               [str(p) for p in REPO_ROOT.glob("*.sh")]
    
    # Run bash -n in batch
    success, _, stderr = run_cmd(["bash", "-n"] + sh_files, check=False)
    if not success:
        print(f"[FAIL] Shell syntax check failed:\n{stderr}")
        return False
        
    print(f"[PASS] {len(sh_files)} Shell scripts passed 'bash -n' validation.")
    return True

def gate_4_manifest_and_inventory():
    log_gate(4, "Landscape Manifest & Scripts Integrity")
    manifest_path = REPO_ROOT / "modules" / "landscape-control-plane" / "scripts" / "manifest.json"
    if not manifest_path.exists():
        print(f"[FAIL] Manifest missing: {manifest_path}")
        return False
    
    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
    except Exception as e:
        print(f"[FAIL] Invalid JSON in manifest: {e}")
        return False
    
    scripts_dir = manifest_path.parent
    scripts_list = manifest.get("scripts", [])
    if isinstance(scripts_list, dict):
        scripts_iter = [(k, v.get("path")) for k, v in scripts_list.items()]
    else:
        scripts_iter = [(s.get("id"), s.get("path")) for s in scripts_list if isinstance(s, dict)]
        
    missing = []
    for script_id, rel_path in scripts_iter:
        if not rel_path:
            missing.append(f"{script_id} (no path defined)")
            continue
        full_path = scripts_dir / rel_path
        if not full_path.exists():
            missing.append(f"{script_id} -> {full_path}")
            
    if missing:
        print(f"[FAIL] Missing script files registered in manifest:\n" + "\n".join(missing))
        return False
        
    print(f"[PASS] Landscape manifest verified. {len(scripts_iter)} scripts intact.")
    return True

def gate_5_test_suite():
    log_gate(5, "Automated Test Suite (pytest via uv)")
    cmd = ["uv", "run", "--with", "pytest", "--with", "pyyaml", "pytest", "tests/test_fleet_runtimes_upgrade.py"]
    success, stdout, stderr = run_cmd(cmd, check=False)
    if not success:
        print(f"[FAIL] Test execution failed:\n{stdout}\n{stderr}")
        return False
    
    print(stdout.strip())
    print("[PASS] Test suite passed successfully.")
    return True

def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print("========================================================")
    print(" OMNI-SRV-ADMIN: 5 CANONICAL PRE-CI GATES")
    print("========================================================")
    
    gates = [
        gate_1_git_hygiene,
        gate_2_python_syntax,
        gate_3_shell_syntax,
        gate_4_manifest_and_inventory,
        gate_5_test_suite
    ]
    
    for i, gate in enumerate(gates, 1):
        if not gate():
            print(f"\n❌ [PRE-CI BLOCKED] Gate {i} failed. Fix issues before push.")
            sys.exit(1)
            
    print("\n========================================================")
    print("✅ [5/5 GATES APPROVED] Ready for Atomic Commit & Push!")
    print("========================================================")
    sys.exit(0)

if __name__ == "__main__":
    main()
