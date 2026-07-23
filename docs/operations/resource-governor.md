# Resource Governor — ATIUS-SRV-1

## TL;DR

Recomendação base para o teu cenário:

- usar `cgroups v2` + `systemd-run` como camada primária
- usar flags nativas de `podman`/compiladores como camada secundária
- registrar PSI, swap, disco, top consumers e hotspots de build em `~/.logs/resource-governor/`

Implementação versionada neste repo:

```text
modules/srv1-ops/configs/resource-governor.env
modules/srv1-ops/scripts/resource-governor-*.py
modules/srv1-ops/systemd/omni-*.slice
modules/srv1-ops/systemd/resource-governor-*.service
modules/srv1-ops/systemd/resource-governor-*.timer
```

## Incidente 2026-07-13: por que 20% virou 100%

O limite canônico estava correto: em 4 vCPU, `omni-builds.slice` tinha
`cpu.max=80000 100000`, ou 0,8 CPU/20% do host. Dois mecanismos paralelos
furavam a gestão agregada:

- `atius-build-throttle.timer` movia cada PID para uma folha própria com 0,2
  CPU, mas deixava o cgroup pai ilimitado; N processos podiam consumir N×0,2 CPU
- cada build criava três units transient com timestamp, sem dedupe; chegaram a
  existir 477 units carregados e 29 timers pendentes, com audits recursivos

Correção canônica:

- existe apenas um cgroup agregado por profile, sempre as slices
  `omni-builds.slice`, `omni-interactive.slice` e `omni-transfers.slice`
- builds passam por um semáforo `flock` de capacidade 1 e continuam sob a quota
  coletiva enquanto esperam ou executam
- hygiene usa três timers estáveis e uma fila persistente/coalescente; novas
  solicitações incrementam contadores, mas não criam units nem adiam o batch
- cleanup, snapshot e audit usam o mesmo semáforo e a mesma
  `omni-builds.slice`; o audit possui ainda um lock non-blocking próprio
- o patcher migra processos descobertos para as slices systemd, não para
  cgroups plain paralelos
- o sweep automático `gsd-graphify-auto-update.service` nasce diretamente na
  `omni-builds.slice` e adquire o mesmo semaphore; o patcher deixa de ser a
  primeira linha de defesa para esse broad indexer

Migração segura (dry-run por padrão):

```bash
omni srv1-ops resources reconcile-legacy
omni srv1-ops resources reconcile-legacy --apply
```

O modo `--apply` cria backup em `~/.backups/`, desabilita/remove o scanner
legado, preserva processos ao migrá-los para a slice agregada e descarrega
somente units `omni-post-build-*` legados.

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
- `/home/ubuntu/GitHub/containers/router-ai-atius/docs/atius-router-docs/.next` ≈ 0.77 GiB
- `~/.local/share/containers/storage` ≈ 22 GiB
- Podman com 3 imagens dangling de ~3.1–3.2 GiB cada

## Perfis padrão

Valores iniciais conservadores. Host atual está apertado em CPU, swap e disco.

| Profile | Slice | Uso | CPU | Memória | I/O |
|---|---|---|---|---|---|
| `builds` | `omni-builds.slice` | `podman build`, `make`, `cargo`, `bun build`, `next build` | `20% do CPU total do host` | `6G / 8G / swap 1G` | `80M read / 40M write` |
| `interactive` | `omni-interactive.slice` | `code`, `obsidian`, Electron/Codex Desktop quando necessário | `125%` | `4G / 6G / swap 512M` | `60M read / 30M write` |
| `transfers` | `omni-transfers.slice` | `rclone`, `rsync`, offload, backup | `100%` | `1G / 2G / swap 256M` | `407M read / 90M write` |

Fonte de verdade dos defaults:

```text
modules/srv1-ops/configs/resource-governor.env
```

## CLI

### Ver perfis e status

```bash
omni srv1-ops resources profiles
omni srv1-ops resources status
omni srv1-ops resources queue
omni srv1-ops resources doctor
omni srv1-ops resources doctor --admission
omni srv1-ops resources reconcile-legacy
omni srv1-ops resources install --dry-run
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

## Podman, k3s e compiladores

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

### k3s

O cleanup de host nao executa prune no containerd do k3s e nao acessa
`/var/lib/rancher/k3s`. Garbage collection de imagens e snapshots do cluster
fica sob responsabilidade do kubelet/k3s e deve ser ajustado por politica do
cluster, nao por scripts Podman do usuario.

### Docker legado

Docker nao faz parte do cleanup atual da frota. Referencias remanescentes no
repo servem para inventario ou migracao de workloads antigos; novos builds e
containers usam Podman, com migracao gradual para k3s.

## Observabilidade implementada

## Gatilho pós-workload

O wrapper `omni srv1-ops resources run ...` já pensa em garbage collection.

Regra global 2026-07-06: todo build deve entrar no profile `builds` e ficar
limitado a 20% do CPU total do host. Em host com 4 vCPU, isso vira
`CPUQuota=80%` no cgroup (`cpu.max=80000 100000`). Em host com 8 vCPU, vira
`CPUQuota=160%`. O campo `RG_PROFILE_BUILDS_CPU_TOTAL_PCT=20` é a fonte de
verdade; `RG_PROFILE_BUILDS_CPU_QUOTA=20%` fica como fallback conservador para
instalações antigas.

Essa regra tambem deve estar presente em `~/.codex/AGENTS.md` e no
`AGENTS.md` do repo em `atius-srv-1`, `atius-srv-2`, `atius-srv-3` e
`horistic-srv`, para impedir agentes de IA de rodarem build cru fora do
profile `builds`.

Para tornar isso padrão em shells humanos e automações que chamam comandos
direto, instalar os wrappers:

```bash
modules/srv1-ops/scripts/install-build-cpu-guard.sh
```

Os wrappers cobrem `npm`, `pnpm`, `yarn`, `bun`, `npx`, `cargo`, `rustc`,
`gcc`, `g++`, `clang`, `make`, `ninja`, `cmake --build`, `go`, `node-gyp`,
`podman build`, `docker build`, `next`, `vite`, `webpack`, `turbo`, `nx`,
`tsc`, `tsup`, `rollup` e `esbuild`.

Os wrappers normalizam `XDG_RUNTIME_DIR=/run/user/<uid>` e
`DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/<uid>/bus` somente ao chamar
`systemctl/systemd-run --user`. Isso evita que buses de sessão Desktop/XRDP em
`/tmp` impeçam updates e builds antes de o workload iniciar.

Regra atual:

- `profile=builds` agenda hygiene automaticamente
- perfis fora de `builds` também agendam se o comando parecer de risco (`podman`, `make`, `cargo`, `bun`, `npm`, `pnpm`, `yarn`, `next`, `vite`, `playwright`, `pip`, `uv`, etc.)
- `RG_PROFILE_BUILDS_SERIALIZE=1` limita a uma execução ativa; concorrentes
  aguardam no lock por até `RG_PROFILE_BUILDS_QUEUE_TIMEOUT_SEC`

Sequência agendada:

1. `cleanup-local.sh` com `CLEANUP_MODE=build-hygiene` após 5 min
2. snapshot leve após 15 min
3. audit de rechecagem após 35 min

Isto cobre Podman, compiladores e instaladores que deixam cache/artifacts em disco.

Os nomes são fixos:

```text
resource-governor-post-build-cleanup.timer
resource-governor-post-build-snapshot.timer
resource-governor-post-build-audit.timer
```

Se já houver um batch pendente, a nova solicitação é coalescida. O estado e as
métricas ficam em:

```text
~/.local/state/omni/resource-governor-hygiene.json
~/.local/state/omni/textfile-collector/resource-governor.prom
```

### O que o `build-hygiene` faz

- limpa caches regeneráveis (`codex-update-manager`, `ms-playwright`, `go-build`, `copilot`, `node-gyp`, `codex-desktop`, além de npm/bun/pnpm/pip)
- roda `podman image prune -f` e `podman volume prune -f` (o `podman builder prune -f` não existe no podman 3.4.4 deste host)
- não chama Docker nem executa prune sobre containerd/k3s
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
- quantidade de containers Podman rodando
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
- imagens Podman
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

- `cpu.max` fica `max 100000` (unlimited) mesmo com `CPUQuota=<quota efetiva>`
- `io.max` fica vazio mesmo com `IOReadBandwidthMax=60M`
- `MemoryMax`, `MemoryHigh`, `TasksMax` funcionam normalmente
- Só as propriedades do `memory` e `pids` controllers são aplicadas

### Solução: `resource-governor-cgroup-init.sh`

Script que escreve os limites diretamente nos cgroup files:

- Ativa `cpu io memory pids` no `subtree_control` do `omni.slice` pai
- Ativa `cpu io memory pids` no `subtree_control` de cada `omni-*.slice`
- Escreve `cpu.max`, `cpu.weight`, `io.max`, `io.weight`, `memory.high`,
  `memory.max` e `memory.swap.max` com os valores do config + runtime override
- Atualiza `CPUQuota` da slice com `systemctl --user set-property --runtime`
  antes do workload. Isso impede a unit estática (`20%` de um core) de
  sobrescrever a quota calculada (`80%` em host de 4 vCPU) ao criar um scope.

**`resource-governor-cgroup-init.service`** (oneshot) roda no boot via
`systemd --user`, habilitado em `timers.target` para não depender de
`default.target` quando este estiver bloqueado por jobs antigos.

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
omni srv1-ops resources install --dry-run
omni srv1-ops resources install
```

E validar:

```bash
omni srv1-ops resources status
omni srv1-ops resources logs
systemctl --user list-timers --all | grep resource-governor
```

`resources install` copia os units versionados para `~/.config/systemd/user/`,
executa `daemon-reload`, habilita os timers do governor/inviolable e habilita
apenas os services críticos do governor (`cgroup-init`, `watchdog`, `patcher`).
Esse fluxo não para PM2, XRDP ou SSHD.

### Fase 3 — migracao gradual para k3s

Manter o resource governor nos builds Podman e tratar recursos dos workloads
k3s por requests/limits Kubernetes. O cleanup Podman nao deve ser reutilizado
para remover imagens, snapshots ou volumes do containerd.

## Watchdog contínuo

O watchdog principal roda como `resource-governor-watchdog.service` contínuo.
O timer versionado permanece habilitável para compatibilidade operacional, mas
os services críticos ficam ancorados em `timers.target`, não em `default.target`.

Ele faz 4 coisas:

1. garante snapshot fresco
2. aplica override conservador em `~/.config/omni/resource-governor.runtime.env`
3. solicita o service singleton de cleanup, contido na slice, quando thresholds críticos são cruzados
4. solicita o service singleton de audit sob pressão persistente

## Prometheus e alertas

O `prometheus-node-exporter` monta o textfile collector read-only. O bundle
`omni-rules.yaml` alerta para scanner per-PID legado ativo, units transient
legadas, falhas da fila, quota divergente, build escapando, batch preso e
métricas sem refresh.

## Doctor preventivo e admission gate

O doctor roda a cada dois minutos e consolida um veredito reproduzível:

```bash
omni srv1-ops resources doctor
omni srv1-ops resources doctor --json-output
omni srv1-ops resources doctor --admission
```

Artefatos live:

```text
~/.local/state/omni/resource-governor-doctor.json
~/.local/state/omni/textfile-collector/resource-governor-doctor.prom
resource-governor-doctor.service
resource-governor-doctor.timer
```

Os checks `critical` são invariantes estruturais: cgroup agregado presente,
`cpu.max` igual ao teto calculado por vCPU, scanner/cgroup/fan-out legados
ausentes e zero build-like quente sem teto equivalente escapando da slice.
Workloads fora de `omni-builds` com um ancestral `cpu.max` igual ou mais
restritivo são classificados como externamente contidos, não como escape.
Antes de qualquer
`resources run builds`, o CLI reaplica os limites e executa o doctor com
`--admission`; uma falha estrutural bloqueia o novo build.

Os checks `warning` observam idade da fila, último audit, PSI CPU e swap. Eles
geram alerta e orientam manutenção, mas não bloqueiam automaticamente: swap
alta sem `si/so` ou PSI memory pode ser memória fria, e bloquear todos os
builds nesse cenário criaria indisponibilidade sem reduzir a causa.

O marker `OMNI_BUILD_CPU_GUARD_ACTIVE=1` não autoriza bypass sozinho. O wrapper
só o aceita quando `/proc/self/cgroup` confirma ancestralidade em
`omni-builds`; isso impede variável herdada ou exportada manualmente de furar o
governor.

### Rotina preventiva

- contínua (2 min): doctor, métricas e alerts
- diária: audit contido/singleton e verificação de queue/stages
- semanal: `resources reconcile-legacy` em dry-run e revisão de escapes
- após reboot/update de systemd: `resources doctor --admission`, `status` e
  inspeção de `cpu.max`
- antes de mudança destrutiva: backup confirmado; `reconcile-legacy --apply`
  somente depois do dry-run

Resposta a alerta estrutural:

1. suspender novos builds; não matar processos automaticamente
2. salvar `resources doctor --json-output`, `status` e `queue --json-output`
3. rodar `resources reconcile-legacy` sem `--apply`
4. corrigir a causa, reinstalar units se necessário e repetir o admission gate
5. liberar builds apenas com `structural_ok=true`

`resource-governor-snapshot.timer` atualiza o textfile a cada cinco minutos,
mesmo quando não existem builds.

O node-exporter roda como UID `65534`; por isso somente o diretório de métricas
é `0755` e os `.prom` são `0644`. State JSON, locks e outros artefatos continuam
privados. `node_textfile_scrape_error` deve permanecer `0`.

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
PYTHONPATH=cli python3 -m omni srv1-ops resources queue
PYTHONPATH=cli python3 -m omni srv1-ops resources snapshot
PYTHONPATH=cli python3 -m omni srv1-ops resources audit
```

`resources status` mostra modo runtime, override ativo, repo/live units,
services/timers, jobs presos relevantes (`ats-pm2`, `horistic-pm2`,
`default.target`), refs PM2 legadas para `/home/ubuntu/ecosystem.atius.js`
(see `pm2-canonical.md` for the canonical replacement path),
properties de slices systemd e valores diretos de cgroups.
Também acusa scanner/cgroup legado, units transient, estado do semáforo, fila e
processos build-like quentes fora de `omni-builds.slice`.
