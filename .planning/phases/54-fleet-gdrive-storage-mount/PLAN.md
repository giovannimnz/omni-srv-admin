# Phase 54: Fleet Google Drive Storage Mount & Governance

## 1. Goal
Implementar montagem nativa e governada do Google Drive em `/mnt/gdrive` em toda a frota ATIUS (`atius-srv-1`, `atius-srv-2`, `atius-srv-3`, `atius-srv-4`, `horistic-srv`) utilizando:
1. Credenciais OAuth 2.0 dedicadas (`omni-storage`) providas exclusivamente via HashiCorp Vault em tmpfs (`/run/rclone/rclone.conf`, 0600).
2. Service systemd de sistema (`/etc/systemd/system/rclone-gdrive.service`) com quotas estritas de cache VFS por host para evitar esgotamento de disco (especialmente `atius-srv-1` limitado a 3G).
3. CLI unificada `omni gdrive [status|mount|unmount|health|list]`.
4. Script Landscape versionado (`gdrive-fleet-setup.sh`) no Landscape Control-Plane para rollouts e reconciliações simultâneas na frota.
5. Cobertura completa de testes TDD com pytest (`tests/test_fleet_gdrive.py`).
6. Análise de viabilidade e arquitetura para o frontend `storage.atius.io` vs `omni.atius.io/storage`.

## 2. Constraints & Security
- **Vault Token Materialization**: Estritamente em tmpfs (`/run/rclone/rclone.conf`). Proibido gravar credenciais em `/home/ubuntu`, `/etc` permanente, arquivos git ou logs.
- **CPU Quota**: CPU <= 20% host cap (`ionice -c best-effort -n 7`, `--transfers=2`, `--checkers=4`).
- **Cache Quotas per Host**:
  - `atius-srv-1`: 3G máx, max-age 6h (disco ~11G livre)
  - `atius-srv-2`: 10G máx, max-age 24h
  - `atius-srv-3`: 5G máx, max-age 12h
  - `atius-srv-4`: 30G máx, max-age 48h
  - `horistic-srv`: 10G máx, max-age 24h
  - Default: 4G máx
- **Mount Point**: `/mnt/gdrive` (mode 0755, `allow-other`, user `ubuntu`).
- **Remoção de Legados**: Desativar e mascarar quaisquer units de usuário antigas (`rclone-gdrive-mount.service`).

## 3. Waves of Execution
- **Wave 1 (TDD & Specifications)**: Criar testes unitários em `tests/test_fleet_gdrive.py`. Validar limites de cache, templates e CLI.
- **Wave 2 (Module Implementation)**: Implementar `modules/fleet-gdrive/` com scripts de hidratação, template systemd e setup script.
- **Wave 3 (CLI Integration)**: Implementar `cli/omni/gdrive.py` e registrar em `cli/omni/cli.py`.
- **Wave 4 (Landscape Integration & Fleet Rollout)**: Registrar `gdrive-fleet-setup` no `manifest.json`, sincronizar e executar via Landscape (`omni landscape run gdrive-fleet-setup --hosts all --wait --yes`).
- **Wave 5 (Verification & Documentation)**: Validar `/mnt/gdrive` em `atius-srv-1..4`, gerar runbook `docs/runbooks/gdrive-fleet-storage.md` e emitir relatório de viabilidade do frontend.
