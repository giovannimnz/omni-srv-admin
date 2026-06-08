# Resource Governor — ATIUS-SRV-1

## TL;DR

Recomendação base para o teu cenário:

- usar `cgroups v2` + `systemd-run` como camada primária
- usar flags nativas de `podman`/`docker`/compiladores como camada secundária
- registrar PSI, swap, disco, top consumers e hotspots de build em `~/.logs/resource-governor/`

Implementação versionada neste repo:

```text
modules/srv1-ops/configs/resource-governor.env
modules/srv1-ops/scripts/resource-governor-*.py
modules/srv1-ops/systemd/omni-*.slice
modules/srv1-ops/systemd/resource-governor-*.service
modules/srv1-ops/systemd/resource-governor-*.timer
```

## Por que esta abordagem

Scripts reativos que dão `stop/kill/pause` em processo pesado são ruins para build e compilador.

O kernel já resolve o problema no nível certo:

- `CPUQuota` / `CPUWeight`
- `MemoryHigh` / `MemoryMax` / `MemorySwapMax`
- `IOReadBandwidthMax` / `IOWriteBandwidthMax` / `IOWeight`
- agrupamento por `slice`

## Cenário atual do host — live probes

Coletado em 2026-06-07 durante a análise.

```text
Kernel: 6.8.0-1050-oracle
systemd: 249
cgroup fs: cgroup2fs
controllers: cpuset cpu io memory hugetlb pids rdma misc
```

```text
4 vCPU
23 GiB RAM
10 GiB swap
/ em 98% (4.8 GiB livres)
```

Sinais vivos observados:

- `swapfile` 100% usado
- `load average` já bateu `54.39 / 112.70`
- PSI alto em memória e I/O
- `dockerd` ~1.1 GiB RSS
- `next-server` ~2.1 GiB RSS
- múltiplos `rustc` em build de `codex-desktop-linux`
- `tsserver`/LSPs de Hermes e VSCode consumindo memória constante
- `rclone copy /home/ubuntu/GitHub ...` concorrendo com análise

Hotspots de artefatos detectados:

- `~/GitHub/forks/AionUi/node_modules` ≈ 4.74 GiB
- `~/GitHub/Programs/codex-desktop-linux/target` ≈ 3.04 GiB
- `~/GitHub/Programs/codex-desktop-linux/dist` ≈ 1.05 GiB
- `~/docker/Atius/router-ai-atius/web/default/node_modules` ≈ 2.23 GiB
- `~/docker/Atius/atius-router-docs/.next` ≈ 0.77 GiB
- `~/.local/share/containers/storage` ≈ 22 GiB
- Podman com 3 imagens dangling de ~3.1–3.2 GiB cada

## Perfis padrão

Valores iniciais conservadores. Host atual está apertado em CPU, swap e disco.

| Profile | Slice | Uso | CPU | Memória | I/O |
|---|---|---|---|---|---|
| `builds` | `omni-builds.slice` | `podman build`, `make`, `cargo`, `bun build`, `next build` | `200%` | `6G / 8G / swap 1G` | `60M read / 30M write` |
| `interactive` | `omni-interactive.slice` | `code`, `obsidian`, Electron/Codex Desktop quando necessário | `125%` | `4G / 6G / swap 512M` | `40M read / 20M write` |
| `transfers` | `omni-transfers.slice` | `rclone`, `rsync`, offload, backup | `100%` | `1G / 2G / swap 256M` | `70M read / 35M write` |

Fonte de verdade dos defaults:

```text
modules/srv1-ops/configs/resource-governor.env
```

## CLI

### Ver perfis e status

```bash
omni srv1-ops resources profiles
omni srv1-ops resources status
omni srv1-ops resources install
omni srv1-ops resources logs
omni srv1-ops resources watchdog
```

### Rodar workload dentro do profile

```bash
omni srv1-ops resources run builds -- make -j2
omni srv1-ops resources run builds -- cargo build --release
omni srv1-ops resources run builds -- podman build -t meu-app .
omni srv1-ops resources run interactive -- code /home/ubuntu/GitHub/forks/AionUi
omni srv1-ops resources run transfers -- rclone copy /home/ubuntu/GitHub remote:Backup/GitHub
```

### Gerar logs on-demand

```bash
omni srv1-ops resources snapshot
omni srv1-ops resources audit
```

## Docker vs Podman vs compiladores

### Podman

`podman` rootless + cgroups v2 + `systemd-run --user` encaixa muito bem.

Recomendação:

```bash
omni srv1-ops resources run builds -- podman build -t my-image .
```

Se quiser endurecer ainda mais:

```bash
podman build --cpus 2 --memory 6g --memory-swap 7g ...
```

### Docker run

`docker run` aceita limites nativos e deve usar sempre que o container for pesado:

```bash
docker run \
  --cpus 2 \
  --memory 6g \
  --memory-swap 7g \
  --device-read-bps /dev/sda:60mb \
  --device-write-bps /dev/sda:30mb \
  ...
```

### Docker build

Aqui está a limitação importante.

`docker build` roda dentro do `dockerd` root daemon. Então um `systemd-run --user` em volta do cliente **não** garante limite efetivo no builder.

O que fazer:

1. preferir `podman build` quando possível
2. para Docker, usar builder dedicado / system slice root-level / `--cgroup-parent` depois de instalar a slice no escopo correto
3. não assumir que `docker build` ficou protegido só porque foi chamado por uma shell limitada no user scope

## Observabilidade implementada

## Gatilho pós-workload

O wrapper `omni srv1-ops resources run ...` já pensa em garbage collection.

Regra atual:

- `profile=builds` agenda hygiene automaticamente
- perfis fora de `builds` também agendam se o comando parecer de risco (`docker`, `podman`, `make`, `cargo`, `bun`, `npm`, `pnpm`, `yarn`, `next`, `vite`, `playwright`, `pip`, `uv`, etc.)

Sequência agendada:

1. `cleanup-local.sh` com `CLEANUP_MODE=build-hygiene` após 5 min
2. snapshot leve após 15 min
3. audit de rechecagem após 35 min

Isto cobre não só Docker/Podman, mas também compiladores e instaladores que deixam cache/artifacts em disco.

### O que o `build-hygiene` faz

- limpa caches regeneráveis (`codex-update-manager`, `ms-playwright`, `go-build`, `copilot`, `node-gyp`, `codex-desktop`, além de npm/bun/pnpm/pip)
- roda `podman image prune -f` e `podman volume prune -f` (o `podman builder prune -f` não existe no podman 3.4.4 deste host)
- roda `docker image prune -f` e `docker builder prune -f`
- trim de logs locais
- **não** mexe em `/tmp` nem journal neste modo leve

### Snapshot leve

Script:

```text
modules/srv1-ops/scripts/resource-governor-snapshot.py
```

Captura:

- load average
- memória disponível
- swap usada
- disco `/`
- PSI `cpu/memory/io`
- top CPU
- top memória
- quantidade de containers Docker/Podman rodando
- alerts por threshold

Saída:

```text
~/.logs/resource-governor/snapshots.jsonl
~/.logs/resource-governor/latest.json
~/.logs/resource-governor/latest.txt
```

### Audit pesado diário

Script:

```text
modules/srv1-ops/scripts/resource-governor-audit.py
```

Captura:

- hotspots de `node_modules`, `.next`, `target`, `dist`, `.venv`, `data`
- fixed paths grandes (`~/.cache/codex-update-manager`, `~/.rustup`, `~/.local/share/containers/storage`)
- imagens Docker/Podman
- containers ativos
- top CPU/mem no momento do audit

Saída:

```text
~/.logs/resource-governor/audit-YYYY-MM-DD.json
~/.logs/resource-governor/audit-YYYY-MM-DD.txt
~/.logs/resource-governor/latest-audit.txt
```

## Timers versionados

```text
modules/srv1-ops/systemd/resource-governor-snapshot.service
modules/srv1-ops/systemd/resource-governor-snapshot.timer
modules/srv1-ops/systemd/resource-governor-audit.service
modules/srv1-ops/systemd/resource-governor-audit.timer
```

Padrão:

- snapshot: a cada 5 min
- audit: diário 02:40

## Slices versionadas

```text
modules/srv1-ops/systemd/omni-builds.slice
modules/srv1-ops/systemd/omni-interactive.slice
modules/srv1-ops/systemd/omni-transfers.slice
```

## Workaround: systemd 249 user instance bug

systemd 249 (user instance) **não escreve `CPUQuota` e `IO*BandwidthMax`**
nos arquivos cgroup v2, mesmo definidos nos `.slice` units e passados
via `-p` ao `systemd-run --scope`.

Problemas observados:

- `cpu.max` fica `max 100000` (unlimited) mesmo com `CPUQuota=200%`
- `io.max` fica vazio mesmo com `IOReadBandwidthMax=60M`
- `MemoryMax`, `MemoryHigh`, `TasksMax` funcionam normalmente
- Só as propriedades do `memory` e `pids` controllers são aplicadas

### Solução: `resource-governor-cgroup-init.sh`

Script que escreve os limites diretamente nos cgroup files:

- Ativa `cpu` + `io` no `subtree_control` do `omni.slice` pai
- Ativa `cpu io memory pids` no `subtree_control` de cada `omni-*.slice`
- Escreve `cpu.max`, `io.max` com os valores do config + runtime override

**`resource-governor-cgroup-init.service`** (oneshot) roda no boot via
`systemd --user`, ativado por `default.target`.

**Integração no watchdog:** quando muda o runtime override (conservative ↔ base),
o watchdog chama `cgroup-init` para aplicar os novos limites nos cgroups.

**Integração no `resources run`:** antes de executar o comando, chama
`cgroup-init` para garantir que os limites estão atualizados.

## Fase 1 — já implementado no repo

### Fase 1 — já implementado no repo

- docs
- profiles
- CLI wrapper
- snapshot logger
- daily audit logger
- versionamento das slices/timers

### Fase 2 — habilitar live no host

Ativação live recomendada:

```bash
omni srv1-ops resources install
```

E validar:

```bash
omni srv1-ops resources status
omni srv1-ops resources logs
systemctl --user list-timers --all | grep resource-governor
```

### Fase 3 — hardening específico de Docker

Se quiser proteção real para `docker build`, criar estratégia dedicada:

- builder `buildx` próprio
- slice root-level ou override de builder container
- ou migração operacional dos builds para Podman

## Watchdog contínuo

O watchdog roda por `resource-governor-watchdog.timer` a cada 2 minutos.

Ele faz 4 coisas:

1. garante snapshot fresco
2. aplica override conservador em `~/.config/omni/resource-governor.runtime.env`
3. dispara `cleanup-local.sh` em `CLEANUP_MODE=build-hygiene` quando thresholds críticos são cruzados
4. dispara audit extra sob pressão persistente

Thresholds atuais no config:

- `RG_WATCHDOG_DISK_CRITICAL_PCT=97`
- `RG_WATCHDOG_SWAP_CRITICAL_PCT=95`
- `RG_WATCHDOG_MEM_AVAILABLE_CRITICAL_MIB=1536`
- `RG_WATCHDOG_PSI_IO_FULL_CRITICAL_AVG10=2.0`
- `RG_WATCHDOG_PSI_MEMORY_FULL_CRITICAL_AVG10=0.5`

Recovery atual para remover override:

- disco `<=92%`
- swap `<=70%`
- memória disponível `>=4096 MiB`

## Primeiras melhorias que eu atacaria no host

1. limpar dangling images do Podman (~9+ GiB)
2. revisar por que `backup-srv1-daily.timer` ficou `n/a` no último run
3. parar de deixar `next dev`, Rust build e backup em paralelo no mesmo host apertado
4. limitar `make -j`/`cargo -j`/workers do Next manualmente quando não usar wrapper
5. avaliar se `dockerd` + `podman` simultâneos continuam necessários para todos os projetos
6. atacar o disco antes de qualquer build grande — 98% de uso é gargalo estrutural

## Validação mínima

```bash
PYTHONPATH=cli python3 -m omni srv1-ops resources profiles
PYTHONPATH=cli python3 -m omni srv1-ops resources status
PYTHONPATH=cli python3 -m omni srv1-ops resources snapshot
PYTHONPATH=cli python3 -m omni srv1-ops resources audit
```
