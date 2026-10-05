# Recovery de apps Podman no SRV-1 — 2026-09-05

## CloudBeaver — estado final

- Serviço: `container-cloudbeaver.service`.
- Runtime: rootless Podman.
- Imagem pinada: `docker.io/dbeaver/cloudbeaver:26.1.0`.
- Workspace persistente: `/home/ubuntu/GitHub/containers/cloudbeaver/workspace_recent`.
- Network: `srv1-podman-v2`.
- Listener host: `127.0.0.1:8978`.
- Edge canônico: `https://db.atius.com.br/` via Cloudflare e Apache.
- Monitor: `cloudbeaver-healthcheck.timer`, read-only, a cada cinco minutos.
- Acesso direto ao IP público `137.131.190.161:8978`: bloqueado pela ausência de bind público.

## Processo histórico reconciliado

`proc_c911d3f83c90` iniciou em `2026-09-05 00:57:20 BRT` e encerrou em `01:00:24 BRT`, exit `0`, após `183s`.

O processo:

1. puxou a imagem upstream ARM64 `26.1.0` sob o profile governado `transfers`;
2. iniciou `container-cloudbeaver.service`;
3. aguardou `HTTP 200` local;
4. confirmou a imagem, o mount persistente e o estado `running`;
5. confirmou `HTTP 200` em `https://db.atius.com.br/`;
6. executou soak de 30 segundos;
7. terminou com `CLOUDBEAVER_RECOVERY_OK`.

Classificação:

```text
operational-pass-not-review
subtype: superseded-by-current-hardened-runtime
```

O exit `0` é prova operacional histórica, não review independente. O runtime atual tem um contrato mais forte que o processo original.

## Drift encontrado durante a reconciliação

O recovery histórico restabeleceu o serviço, mas manteve `-p 8978:8978`. Probes de `atius-srv-3` e `atius-srv-4` alcançavam `http://137.131.190.161:8978/` com `HTTP 200`, bypassando Cloudflare e Apache.

Também havia drift de autoridade:

- inventário usava `~/containers/cloudbeaver`, versão `latest`, network antiga e hostname sem DNS;
- `cloudbeaver.atius.com.br` não existe no DNS público;
- `DbOmniFleet` ainda espelhava o contrato de junho;
- unit e compose live não tinham source canônico completo no repo;
- não havia monitor periódico específico.

## Correção aplicada

### Runtime

- Source canônico da unit: `modules/srv1-ops/systemd/container-cloudbeaver.service`.
- Source canônico do compose fallback: `modules/srv1-ops/configs/cloudbeaver-podman-compose.yml`.
- Bind corrigido para `127.0.0.1:8978:8978`.
- `SuccessExitStatus=143` normaliza o SIGTERM observado no stop do conmon.
- `RestartSec=15` evita loop agressivo.
- Unit e compose live ficaram byte-equal aos sources versionados.

### Monitor

- Script: `modules/srv1-ops/scripts/cloudbeaver-healthcheck.sh`.
- Units: `cloudbeaver-healthcheck.service` e `cloudbeaver-healthcheck.timer`.
- Checks: estado da unit, `ExecStart` carregado, imagem/mount/network/bind esperados, listener loopback único, `/status`, versão `26.1.0`, edge público e zero restarts.
- Sem restart ou remediação automática.
- O monitor evita `podman inspect` dentro da unit endurecida: Podman 3.4 falhou com `cannot clone: Operation not permitted` sob `NoNewPrivileges=true`.

### Autoridades

- `inventory/hosts/atius-srv-1.yaml` corrigido.
- `docs/CLOUDFLARE.md` e `docs/operations/ATIUS-FLEET-NETWORK-PORT-MAP.md` corrigidos para `db.atius.com.br`.
- Cloudflare API: um record `A`, proxied, TTL automático para `db.atius.com.br`; zero records para `cloudbeaver.atius.com.br`.
- `DbOmniFleet`: update transacional targeted apenas na row CloudBeaver e no elemento CloudBeaver de `inventory.host.apps`.
- Isolamento provado: `10` apps não-CloudBeaver, `4` forks e `5` policies sem mudança.

## False-starts e rollback

Três tentativas foram abortadas com rollback automático antes do cutover final:

1. o harness exigia `inactive`, mas a unit antiga terminava `failed` apesar de o container e listener terem sido removidos corretamente por SIGTERM `143`;
2. `systemctl reset-failed` de uma healthcheck ainda não carregada retornou erro;
3. o monitor inicial usava `podman inspect` sob `NoNewPrivileges=true` e falhou no re-exec/clone do Podman 3.4.

Cada rollback restaurou a unit anterior, `HTTP 200` local/público e zero restarts. O cutover final separou o core de segurança do monitor auxiliar: falha do monitor não pode reabrir o bind público.

## Backup

Diretório:

```text
/home/ubuntu/.backups/cloudbeaver-loopback-cutover-20260905T204000-0300
```

Contém:

- preimage da unit, compose, inspect e listener;
- snapshot hot do workspace;
- snapshot consistente com o serviço parado;
- sources pós-correção;
- preimage do registry;
- SQL targeted de apply e rollback;
- `SHA256SUMS`.

Restore test do snapshot consistente: `9` arquivos e `1` database candidate extraídos em diretório isolado. Manifest final: `21/21` entradas válidas.

## Validação

- Regressão TDD: `5 passed`.
- Suite Omni ampla: `156 passed, 2 failed`; os dois failures pertencem à lane
  dirty preexistente de backup/rclone e não sobrepõem nenhum path ou contrato
  CloudBeaver. Evidência e disposição em `full-suite-disposition.md`.
- Inventory validator: `14/14` hosts `ok`.
- Unit: `active/running`, `Result=success`, `ExecMainStatus=0`, `NRestarts=0`.
- Lifecycle da unit canônica: stop `inactive/dead`, `Result=success`,
  `ExecMainStatus=143`; start posterior com H2 preservado, zero restarts e
  novo tick natural do monitor `success`.
- Listener: apenas `127.0.0.1:8978`.
- Local `/status`: `200`, `health=ok`, versão `26.1.0.202606010855`.
- Público `db.atius.com.br`: `200`.
- Probes externos diretos de SRV-3 e SRV-4: curl `7/000`, TCP recusado; positive control em `443` chegou ao origin.
- Timer manual e natural: `Result=success`, exit `0`.
- Failed units: system `0`, user `0`.
- DbOmniFleet: targeted apply e readback `PASS`; rollback transaction test `PASS`.
- Checkpoint Graphify pré-seal: `14.473` nodes, `21.163` edges,
  `stale=false`, `commit_stale=false`; query exata pelo process ID retornou
  `22` nodes e `20` edges. O status pós-documentação fica no final seal externo
  para evitar um loop autorreferente de contagem. `graph.html` não foi
  regenerado porque o grafo excede o limite visual de `5.000` nodes; o HTML
  antigo não é usado como prova.
- GBrain: body canônico atualizado por import de uma única nota com
  `--no-embed`; `1/1` page, `6` chunks, timeline preservada e readback PASS.

## Rollback

### Aplicação/dados sem reabrir a porta pública

1. parar `container-cloudbeaver.service`;
2. restaurar `workspace_recent` a partir de `hot-data/workspace_recent.consistent.tgz`;
3. manter a unit canônica loopback-only;
4. iniciar o serviço;
5. rodar `modules/srv1-ops/scripts/cloudbeaver-healthcheck.sh`;
6. repetir probes externos e exigir `8978` bloqueada.

### Registry

Executar o SQL abaixo usando o mesmo env protegido do Fleet Control Plane:

```text
/home/ubuntu/.backups/cloudbeaver-loopback-cutover-20260905T204000-0300/registry/rollback-cloudbeaver-registry.sql
```

### Rollback integral da unit antiga

Os arquivos em `pre-live/` restauram o estado anterior, mas reabrem `8978` no IP público. Usar apenas como break-glass, seguido imediatamente por uma policy de firewall equivalente e novos probes externos.

## Evidência

```text
docs/operations/evidence/2026-09-05-proc-c911d3f83c90-cloudbeaver/
```

---

## Jenkins — `proc_37d55995c20b`

### Histórico imutável

- Start: `2026-09-05 01:01:21 BRT`.
- Exit: `01:02:37 BRT`, `76s`, status `1`.
- O pull de `docker.io/jenkins/jenkins:2.541.3-jdk17` concluiu com image ID
  `f2c150c0dbf9ed2fd6bac0232de268571971b5dc8c31cf794450382ef5b5c857`.
- O start falhou antes de criar container. A evidência contemporânea exata
  mostra cinco tentativas, `ExecMainStatus=125`, `NRestarts=5` e:
  `statfs /home/ubuntu/GitHub/atius: no such file or directory`.
- O mount stale foi repontado para
  `/home/ubuntu/GitHub/Atius-Capital/ats:/workspace/atius:ro`.
- O retry separado `proc_71bb416a205d` iniciou às `01:07:27`, encerrou às
  `01:08:23`, exit `0`, e terminou com `JENKINS_RECOVERY_OK`.

Classificação:

```text
failed-probe-fixed-current-tree
subtype: historical-missing-workspace-mount-fixed-before-successful-retry-current-runtime-hardened
```

O FAIL histórico não é reescrito. O retry e o runtime atual são provas
separadas.

### Hardening atual

- Source canônico: `modules/srv1-ops/systemd/container-jenkins.service`.
- Compose fallback: `modules/srv1-ops/configs/jenkins-podman-compose.yml`.
- Imagem: `docker.io/jenkins/jenkins:2.541.3-jdk17`.
- Network: `srv1-podman-v2`.
- Listeners:
  - `127.0.0.1:8085` — Apache local;
  - `10.11.1.11:8085` — web privado OCI/DRG;
  - `10.11.1.11:50000` — JNLP privado OCI/DRG.
- SRV-3/SRV-4 não alcançam `137.131.190.161:8085/50000`; positive control
  `443` passa. SRV-2/SRV-3/SRV-4 alcançam os dois ports privados.
- Edge `https://jenkins.atius.com.br/login`: `200` via record Cloudflare `A`,
  proxied, TTL automático.
- Monitor read-only: `jenkins-healthcheck.timer`, cinco minutos, sem restart.
- Lifecycle canônico: stop `Result=success/143`; start `Result=success/0`, zero
  restarts, mounts preservados e config hash estável.
- Focused TDD `5/5`; container contracts combinados `10/10`; full suite
  `161 passed, 2 failed`, ambos residuais preexistentes de backup/rclone sem
  overlap com Jenkins.

### Backup/restore

- Histórico: `/home/ubuntu/.backups/srv1-app-recovery-20260905T005017-0300`;
  archive original com `2.911` files e `config.xml` byte-equal ao live.
- Hardening: `/home/ubuntu/.backups/proc-37d55995c20b-pre-hardening-20260905T215218-0300`;
  snapshot consistente extraído em diretório isolado, `config.xml` byte-equal.
- Registry: apply targeted + rollback transaction test. Apenas `jenkins`,
  `jenkins-agent` e seus elementos em `inventory.host.apps` mudaram; `9`
  outros apps, `4` forks e `5` policies ficaram idênticos.

### Jenkins agent K3s — estado honesto

- Deployment `jenkins-agent` reporta `2/2 Ready`, mas não executa um agent JNLP:
  faz até 30 probes de reachability e entra em `sleep infinity`.
- Logs dos dois pods terminam em `Kubernetes plugin ... required for live JNLP
  registration`.
- Controller sem plugin `kubernetes` e sem diretório `nodes/`.
- Portanto: `placeholder-reachability-only`, `registration_status=not-registered`.
- A conectividade privada `10.11.1.11:8085/50000` está pronta, mas ativar agents
  reais exige um workstream separado com plugin, node/pod template, credencial
  governada e job smoke. Nenhuma dessas mutações foi feita nesta reconciliação.

### Evidência

```text
docs/operations/evidence/2026-09-05-proc-37d55995c20b-jenkins/
```

---

## Plane — `proc_8d7769a62d79`

### Histórico imutável

- `proc_8d7769a62d79`: `01:12:49–01:13:25 BRT`, `35s`, exit `1`.
- O start da stack concluiu e a página root já respondia `200`, mas o harness
  consultou `/api/v1/users/me/` durante migrations e recebeu `502`.
- O processo posterior `proc_783f0e243afc` acompanhou o migrator até
  `exited:0` às `01:23:39`; a API permaneceu `502` até `01:24:08`, mudou para
  `401` às `01:24:16` e encerrou exit `0` com `PLANE_READY_OK`.

Classificação:

```text
post-workload-harness-failure
subtype: api-readiness-probed-before-migrator-and-backend-ready
```

O exit histórico permanece `1`. O workload foi recuperado, mas o primeiro
harness não aguardava a barreira correta.

### Correções atuais

- Unit canônica: `modules/srv1-ops/systemd/plane-podman.service`.
- Compose canônico: `modules/srv1-ops/configs/plane-podman-compose.yaml`.
- `plane-stack-up.sh`: compose up, migrator `exited:0`, API `401`,
  root/setup/spaces `200`, `13` containers totais e `12` long-lived running.
- `TimeoutStartSec=2100` cobre o pior caso dos loops de migrator/API; update
  carregado via daemon-reload sem restart do runtime saudável.
- Binds: web `127.0.0.1:8080`, proxy `127.0.0.1:8090`, PostgreSQL
  `127.0.0.1:8747` + `10.11.1.11:8747` primary +
  `10.100.100.1:8747` reserve.
- SRV-3/SRV-4 não alcançam `137.131.190.161:8080/8090/8747`; SRV-2/3/4
  alcançam somente o DB privado em `10.11.1.11:8747` primary e
  `10.100.100.1:8747` reserve.
- Edge `plane.atius.com.br`: root/setup/spaces `200`, API anônima `401`.
- `.env` live corrigido de `0664` para `0600`; valores não documentados.
- MinIO `/data` migrado de volume anônimo vazio para `plane-app_minio_data`;
  o volume antigo foi removido após dois snapshots e prova `MountCount=0`.
- Healthcheck nativo do `space`, dependente de transient unit Podman, foi
  removido. `/spaces/` passou a ser validado por `plane-stack-up.sh` e pelo
  monitor read-only `plane-healthcheck.timer`.
- O timer usa somente unit/listeners/HTTP: `NoNewPrivileges=true` impede o
  re-exec do Podman rootless. Contagem, migrator, mounts e restarts são gates
  do startup/lifecycle.

### Dados, backup e rollback

- DB: `110` tabelas, `162` migrations, `0` users/workspaces/projects.
- Dump custom PostgreSQL com `1.460` TOC entries restaurado em DB temporária;
  resultado `110|162`.
- Onze volumes montados tiveram snapshots hot e consistent; archives foram
  extraídos em diretório isolado.
- Backup: `/home/ubuntu/.backups/proc-8d7769a62d79-plane-pre-hardening-20260905T230018-0300`.
- Rollback do registry: `registry/rollback-plane-registry.sql`.
- Restaurar o compose preimage reabre `8080/8090/8747`; usar apenas como
  break-glass. Rollback seguro de dados mantém os binds canônicos.

### Validação

- Readiness marker: `migrator=exited:0`, API `401`, root/setup/spaces `200`,
  `13/12` containers.
- Plane focused `4/4`; contracts CloudBeaver/Jenkins/Plane `14/14`.
- Full suite `165 passed, 2 failed`; residuals preexistentes backup/rclone sem
  overlap com Plane.
- Inventory `14/14`; failed units system/user `0/0`.
- Source/live e port-map repo/vault byte-equal.
- GBrain final readback PASS; página arquivada com credenciais antigas
  substituída por stub seguro no vault e no GBrain.
- Graphify fresh/current, queries t31 PASS; contagens em
  `evidence/2026-09-05-proc-8d7769a62d79-plane/graphify-final.json`.

### Evidência

```text
docs/operations/evidence/2026-09-05-proc-8d7769a62d79-plane/
```
