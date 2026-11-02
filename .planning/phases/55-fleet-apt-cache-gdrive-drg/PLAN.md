# Phase 55: Fleet Centralized APT Cache over GDrive & OCI DRG

## 1. Goal
Implementar arquitetura soberana de download único e distribuição centralizada de pacotes `.deb` na frota ATIUS (`atius-srv-1..4`, `aln-srv`, `horistic-srv`, `giovanni-w11-wsl`) utilizando:
1. Servidor de Cache `apt-cacher-ng` hospedado em `atius-srv-3` escutando na rota privada OCI DRG `10.13.1.13:3142`.
2. Persistência de Cache no Google Drive compartilhado (`/mnt/gdrive/apt-cache/`) garantindo capacidade ilimitada (5TB) e retenção permanente sem consumir o disco local dos servidores.
3. Configuração transparente nos clientes via drop-in `/etc/apt/apt.conf.d/01proxy` com fallback gracioso (timeout curto) caso o proxy esteja offline.
4. Eliminação definitiva da divergência temporal de hashes de pacotes (`Package data not yet synchronized with server`), garantindo que o Landscape Server e os nós clientes compartilhem a mesma árvore de pacotes.
5. Script Landscape Control-Plane (`fleet-apt-proxy-configure.sh`) registrado no `manifest.json` para rollout simultâneo e idempotente.
6. CPU Guardrail da ATIUS (<=20% CPU) e zero interrupções.

## 2. Constraints & Security
- **Rota Privada OCI DRG**: O tráfego de cache DEVE trafegar exclusivamente pela rede privada `10.13.1.13` (latência ~0.6ms, 10 Gbps, zero custo de egress).
- **Fallback Gracioso**: Se o servidor de cache estiver inacessível, o `apt` dos clientes NÃO pode falhar; deve conectar diretamente aos mirrors upstream.
- **Armazenamento no GDrive**: O cache deve residir em `/mnt/gdrive/apt-cache/` com permissões adequadas para o usuário `apt-cacher-ng`.
- **CPU Quota**: `CPUQuota=20%`, `Nice=19` via systemd drop-in em `apt-cacher-ng.service`.

## 3. Waves of Execution
- **Wave 1 (TDD & Specifications)**: Criar testes unitários em `tests/test_fleet_apt_cache.py` validando templates de configuração, portas, fallback e CLI helpers.
- **Wave 2 (Cache Server Provisioning)**: Instalar e configurar `apt-cacher-ng` em `atius-srv-3`, vinculando o cache ao `/mnt/gdrive/apt-cache/` e escutando em `10.13.1.13:3142`.
- **Wave 3 (Client Automation Script)**: Criar script versionado `modules/landscape-control-plane/scripts/fleet-apt-proxy-configure.sh` e registrar no `manifest.json`.
- **Wave 4 (Fleet Rollout via Landscape)**: Disparar execução simultânea na frota via `omni landscape run fleet-apt-proxy-configure --hosts all --wait --yes`.
- **Wave 5 (Empirical Verification)**: Testar download de pacotes no `atius-srv-1` e `atius-srv-2`, verificando `Cache Hit` e tráfego 100% interno via DRG.
- **Wave 6 (Memory & Documentation)**: Registrar fatos no GBrain, criar runbook no Obsidian e atualizar a skill canônica do cluster (`omni-routine` e `atius-fleet-landscape-ops`).
