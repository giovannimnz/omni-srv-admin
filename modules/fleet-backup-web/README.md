# Atius Fleet Backup & Schedule Control Web Dashboard

Painel web centralizado para governança de backups de bancos de dados, integridade de snapshots e controle de agendamentos e rotinas da frota ATIUS.

---

## 1. Visão Geral

O módulo substitui exploradores genéricos de arquivos por um painel operacional especializado, exposto com segurança através do **Atius Admin Edge Gateway** e protegido pelo **ATS SSO**.

```text
  [ Navegador / Operador ]
             │
             │ HTTPS (Cookie ATS SSO auth-token)
             ▼
  [ Apache Proxy / Edge Gateway (127.0.0.1:8210) ]
             │
             │ storage.atius.io / backup.atius.io
             ▼
  [ omni-backup-web (127.0.0.1:8085) ]
             ├── Backend: FastAPI (uvicorn)
             ├── Filesystem: /mnt/gdrive/ATIUS-SRV/
             └── Engine: omni routine + Landscape Script ID 16
```

---

## 2. Funcionalidades Principais

1. **Fleet Database Backups Hub**:
   - Status em tempo real dos 4 nós (`atius-srv-1..4`).
   - Leitura direta de `manifest.json` e `SHA256SUMS`.
   - Download assíncrono de dumps de bancos de dados.
   - Disparo ad-hoc de backups via botão "Backup Agora" (Landscape Script ID: 16).
2. **Fleet Schedule & Routine Control**:
   - Visualização de timers systemd (`omni-db-backup.timer`, `omni-autoclean.timer`, `omni-fleet-runtime-sync.timer`, `rclone-fleet-queue.timer`).
   - Catálogo e disparo de rotinas do `RoutineEngine` com locks e contenção de CPU.
   - Visualizador de logs operacionais.
3. **Quotas VFS & Retenção**:
   - Monitoramento das cotas VFS (`3G`, `10G`, `5G`, `30G`).
   - Política de retenção estrita de 14 dias com purga automática.

---

## 3. Endpoints da API

- `GET /api/v1/health`: Sonda de integridade do serviço.
- `GET /api/v1/backups/summary`: Sumário consolidado de toda a frota.
- `GET /api/v1/backups/hosts/{host}`: Lista de snapshots cronológicos por host.
- `GET /api/v1/backups/hosts/{host}/{date}`: Detalhes e lista de dumps de uma data.
- `GET /api/v1/backups/download/{host}/{date}/{filename}`: Download seguro de dump.
- `POST /api/v1/backups/trigger`: Solicitação de backup imediato.
- `GET /api/v1/schedules/timers`: Lista de temporizadores ativos na frota.
- `GET /api/v1/schedules/routines`: Lista de rotinas cadastradas.
- `POST /api/v1/schedules/routines/{routine_id}/run`: Execução soberana de rotina.

---

## 4. Testes e Validação

```bash
pytest modules/fleet-backup-web/tests/test_backup_web_api.py -v
```
