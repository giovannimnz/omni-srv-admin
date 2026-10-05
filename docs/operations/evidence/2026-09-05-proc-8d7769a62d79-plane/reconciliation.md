# Reconciliação — `proc_8d7769a62d79`

## Classificação

```text
post-workload-harness-failure
subtype: api-readiness-probed-before-migrator-and-backend-ready
```

## Cadeia histórica

| Processo | Janela BRT | Exit | Disposição |
|---|---:|---:|---|
| `proc_8d7769a62d79` | 01:12:49–01:13:25 | 1 | workload iniciado; harness consultou API cedo |
| `proc_783f0e243afc` | 01:22:40–01:24:50 | 0 | readiness operacional PASS, não review |

O processo falho recebeu `200` na página root e, segundos depois, `502` em `/api/v1/users/me/`. Ele encerrou por `set -e` antes de validar setup, containers, migrator, volumes ou soak.

O processo posterior preserva a timeline real:

- migrations ainda rodavam até `01:23:36`;
- migrator terminou `exited:0` às `01:23:39`;
- API ficou `502` entre `01:23:40` e `01:24:08`;
- API virou `401`, setup permaneceu `200` e `PLANE_READY_OK` saiu às `01:24:16`.

O exit `1` original não vira PASS. A falha foi na barreira de readiness do harness, depois de o workload começar.

## Current-tree sibling drift adotado

A stack recuperada estava saudável, mas havia quatro drifts atuais:

1. `8080`, `8090` e PostgreSQL `8747` estavam publicados em `*`;
2. SRV-3 e SRV-4 alcançavam os três ports no IP público; `8090` respondia HTTP `200` direto;
3. MinIO `/data` usava volume anônimo, incompatível com lifecycle `down→up` durável;
4. healthcheck nativo do `space` dependia de transient units Podman. O callback ao user-manager falhou em `systemd/private`, deixando timer antigo contra container removido e o novo container sem timer.

Também havia drift de autoridade: Plane não existia no app inventory/DbOmniFleet e a unit/compose não tinham source canônico no módulo.

## Contrato atual

- Unit: `modules/srv1-ops/systemd/plane-podman.service`.
- Compose: `modules/srv1-ops/configs/plane-podman-compose.yaml`.
- Startup: `plane-stack-up.sh` espera migrator `exited:0`, API anônima `401`, root/setup/spaces `200`, `13` containers totais e `12` running.
- `TimeoutStartSec=2100` cobre os loops máximos de migrator + API com margem;
  foi aplicado por daemon-reload sem restart e sem mudar a InvocationID.
- Listeners:
  - `127.0.0.1:8080` — frontend fallback;
  - `127.0.0.1:8090` — proxy para Apache;
  - `127.0.0.1:8747` — PostgreSQL local;
  - `10.11.1.11:8747` — PostgreSQL OCI/DRG.
  - `10.100.100.1:8747` — PostgreSQL `wg100` reserve.
- Direct public `8080/8090/8747`: bloqueado.
- Private SRV-2/SRV-3/SRV-4: web/proxy bloqueados em OCI/DRG e `wg100`; DB
  `8747` preservado em ambos os planos privados.
- Cloudflare/Apache: `plane.atius.com.br` root/setup/spaces `200`; API anônima `401`.
- `.env`: `0600`; nenhum valor sensível registrado.
- MinIO `/data`: `plane-app_minio_data`; volume anônimo antigo vazio e não montado removido após snapshots hot/consistent.
- Monitor: `plane-healthcheck.timer`, read-only, 5min; inclui `/spaces/` e não usa Podman/systemctl para restart.
- O monitor usa unit/listeners/HTTP. Probe isolada demonstrou que
  `NoNewPrivileges=true` bloqueia o re-exec rootless Podman com `cannot clone`
  e `cannot re-exec process`; contagem/migrator/mounts ficam nos gates de
  startup e lifecycle, não no timer periódico.

## Dados

- PostgreSQL: `110` tabelas, `162` migrations.
- `users=0`, `workspaces=0`, `projects=0`.
- Dependências internas API → DB/Valkey/RabbitMQ/MinIO: TCP connected.
- Containers: `13` total, `12` running, migrator `exited:0`, zero restarts no current proof.

## Backup e restore

Backup:

```text
/home/ubuntu/.backups/proc-8d7769a62d79-plane-pre-hardening-20260905T230018-0300
```

Contém:

- unit/compose/env preimage e inspect completo;
- dump PostgreSQL custom, `1.460` TOC entries;
- restore real em database temporária: `110|162`;
- snapshots hot + consistent dos `11` volumes montados;
- archives extraídos em diretório isolado;
- transient healthcheck antigo e journal;
- sources pós-correção;
- preimage/apply/rollback targeted do DbOmniFleet;
- `SHA256SUMS`.

Rollback do compose preimage reabre os três ports públicos. Usar só como break-glass. Para rollback seguro, manter unit/compose canônicos e restaurar apenas os dados necessários.

## False-starts da reconciliação

- `pg_restore --list /dev/stdin` falhou porque custom archives precisam de input seekable; o dump começava com `PGDMP` e passou `pg_restore --list <file>` + restore real.
- O primeiro timeout versionado era `1200s`, menor que o teto acumulado dos
  loops de readiness. RED/GREEN ajustou para `2100s` antes do seal.
- Um shell agregado de remoção do volume anônimo foi bloqueado pelo parser antes de executar. O volume permaneceu presente; a remoção foi refeita por argv Python após readback do prestate e dos backups.
- O primeiro cutover encontrou o healthcheck transient órfão. O core seguro permaneceu ativo; o ID antigo foi parado/resetado e o healthcheck foi transferido para o monitor canônico antes do lifecycle final.

## DbOmniFleet

- `plane` não existia antes.
- Insert + mirror append targeted.
- Dry apply + rollback exato: PASS.
- Isolamento: `11` apps existentes, `4` forks e `5` policies inalterados.

## Validação

- Unit final: `active/exited`, `Result=success`, exit `0`; journal contém
  `PLANE_READY_OK migrator=exited:0 api=401 setup=200 root=200 spaces=200 all=13 running=12`.
- Monitor manual e tick natural: `success`.
- Plane focused: `4 passed`.
- CloudBeaver + Jenkins + Plane contracts: `14 passed`.
- Full suite: `165 passed, 2 failed`; os dois failures pertencem à lane dirty
  preexistente backup/rclone, sem overlap. Ver `full-suite-disposition.md`.
- Inventory validator: `14/14 ok`.
- Source/live unit, compose e health units: byte-equal.
- Port map repo/vault: byte-equal.
- Cloudflare: um record `A`, proxied, TTL automático.
- Failed units system/user: `0/0`.
- Secret scan do escopo compartilhável: PASS.
- GBrain: autoridade Plane, incident, daily e timeline final importados com
  readback; a página arquivada antiga foi substituída por stub seguro e caiu de
  sete para zero padrões sensíveis; nenhum write-through não-canônico.
- Graphify: rebuild foreground governado e fresh/current; queries encontram
  startup, monitor e o runbook t31. Contagens e warnings ficam no receipt
  `graphify-final.json` e no seal externo para evitar mutação autorreferente.
- `graph.html` não foi regenerado: o grafo excede o limite visual de `5.000`
  nodes; `graph.json` e `GRAPH_REPORT.md` são os artifacts atuais.

## Limites

- `proc_783f0e243afc` é prova operacional, não review independente.
- Probes externos são evidência observacional; os binds explícitos carregados e `ss` são a autoridade host-side.
- Nenhum commit/push.
