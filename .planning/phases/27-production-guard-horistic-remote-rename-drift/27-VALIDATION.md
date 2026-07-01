---
phase: 27
title: "Validation - Horistic Remote Apache, Rename Drift and Webhook Safety"
date: 2026-06-24
status: complete
requirements:
  - PRG-08
  - PRG-09
  - PRG-10
  - PRG-11
context_budget_target: "75k-95k tokens"
execution_model_target: "gpt-5.3-codex-spark"
---

# Phase 27 Validation

## Ordered Automated Battery

1. `python3 -m py_compile modules/srv1-ops/scripts/production_guard.py`
2. `! rg -n "requests\\.post|urllib.*POST|curl .*POST|method=.*POST" modules/srv1-ops/scripts/production_guard.py modules/srv1-ops/configs/production-guard.yaml docs/operations/production-guard.md`
3. `PYTHONPATH=cli pytest cli/omni/tests/test_srv1_production_guard.py -q -k "apache or remote or rename or drift or webhook"`
4. `PYTHONPATH=cli python3 -m omni srv1-ops production-guard status --json`
5. `PYTHONPATH=cli python3 -m omni srv1-ops production-guard doctor --json`
6. `ssh horistic@10.1.1.4 'hostname; systemctl is-enabled apache2; systemctl is-active apache2; systemctl show apache2 -p FragmentPath -p DropInPaths -p NeedDaemonReload; ss -tlnp | grep -E ":(80|443) "; apache2ctl -S'`
7. `curl -fsSI https://dashboard.horistic.com/login`
8. `curl -fsSI https://api.horistic.com/v1/health`
9. `curl -fsSI https://webhook.horistic.com/`
10. `node "$HOME/.Codex/get-shit-done/bin/gsd-tools.cjs" graphify status`
11. `$gsd-verify-work 27`

## Execution Result

- `python3 -m py_compile modules/srv1-ops/scripts/production_guard.py`
  - PASS
- `! rg -n "requests\\.post|urllib.*POST|curl .*POST|method=.*POST" modules/srv1-ops/scripts/production_guard.py modules/srv1-ops/configs/production-guard.yaml docs/operations/production-guard.md`
  - PASS
- `PYTHONPATH=cli pytest cli/omni/tests/test_srv1_production_guard.py -q -k "apache or remote or rename or drift or webhook"`
  - PASS
- `PYTHONPATH=cli python3 -m omni srv1-ops production-guard status --json`
  - RUN (overall: block) — novos checks executados; bloqueios atuais: `pm2_boot_unit`, parse de ecosystems, `containers`, `sshd`.
- `PYTHONPATH=cli python3 -m omni srv1-ops production-guard doctor --json`
  - RUN (overall: block) — novos checks executados; bloqueios atuais: `pm2_boot_unit`, parse de ecosystems, `containers`, `sshd`, `systemd_jobs`.
- `ssh horistic@10.1.1.4 'hostname; systemctl is-enabled apache2; systemctl is-active apache2; systemctl show apache2 -p FragmentPath -p DropInPaths -p NeedDaemonReload; ss -tlnp | grep -E ":(80|443) "; apache2ctl -S'`
  - PASS (read-only)
- `curl -fsSI https://dashboard.horistic.com/login`
  - PASS
- `curl -fsSI https://api.horistic.com/v1/health`
  - PASS
- `curl -fsSI https://webhook.horistic.com/`
  - PASS
- `node "$HOME/.Codex/get-shit-done/bin/gsd-tools.cjs" graphify status`
  - PASS
- `$gsd-verify-work 27`
  - PASS after 2026-06-26 revalidation. The phase already has `27-UAT.md`
    marked complete and `27-VERIFICATION.md` marked passed.

## Non-Negotiable Failures

- Nenhum.

## 2026-06-26 Revalidation

- `27-UAT.md` remains complete with 4/4 UAT scenarios passed.
- `27-VERIFICATION.md` remains passed.
- No open audit item was reported by `gsd-tools query audit-open --json`.
- Graphify was fresh before the revalidation pass.
