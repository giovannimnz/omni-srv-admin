# Reconciliação — `proc_37d55995c20b`

## Classificação

```text
failed-probe-fixed-current-tree
subtype: historical-missing-workspace-mount-fixed-before-successful-retry-current-runtime-hardened
```

## Cadeia histórica

| Processo | Janela BRT | Exit | Disposição |
|---|---:|---:|---|
| `proc_37d55995c20b` | 01:01:21–01:02:37 | 1 | FAIL histórico imutável |
| `proc_71bb416a205d` | 01:07:27–01:08:23 | 0 | retry operacional PASS, não review |

O pull do processo falho concluiu. O start seguinte executou cinco tentativas e falhou com `ExecMainStatus=125`, `NRestarts=5` e erro exato:

```text
statfs /home/ubuntu/GitHub/atius: no such file or directory
```

O `ExecStart` da época montava o path aposentado em `/workspace/atius:ro`. O container não foi criado; `8085` ficou fechado e o edge retornava `503`.

Antes do retry, a unit e o compose foram corrigidos para:

```text
/home/ubuntu/GitHub/Atius-Capital/ats:/workspace/atius:ro
docker.io/jenkins/jenkins:2.541.3-jdk17
```

O retry confirmou `config.xml`, workspace/package, local/público `200`, soak 30s e marker `JENKINS_RECOVERY_OK`.

## Current-tree sibling drift adotado

A reconciliação encontrou o controller saudável, mas `8085` e `50000` publicados em `*`. Probes de SRV-3 e SRV-4 alcançavam os dois ports pelo IP público.

Contrato atual:

- `127.0.0.1:8085` — Apache local;
- `10.11.1.11:8085` — Jenkins web privado OCI/DRG;
- `10.11.1.11:50000` — JNLP privado OCI/DRG;
- nenhum bind público direto.

O dual-bind para o mesmo container port foi validado antes em container efêmero e removido. Pós-cutover:

- public direct SRV-3/SRV-4: `8085` e `50000` recusados; curl `7/000`;
- positive control `443`: alcançável;
- private OCI/DRG SRV-2/SRV-3/SRV-4: `8085` e `50000` alcançáveis;
- `jenkins.atius.com.br/login`: `200`.

## Current proof

- Unit `active/running`, `Result=success`, zero restarts.
- Imagem `2.541.3-jdk17`, JENKINS_HOME RW, libltdl RO e ATS workspace RO.
- `config.xml` SHA-256 preservado.
- `0` jobs.
- TDD `5 passed`; inventory `14/14 ok`.
- Combined container contracts `10 passed`. Full suite governada:
  `161 passed, 2 failed`; ambos os failures pertencem à lane dirty
  preexistente de backup/rclone e não sobrepõem t29. Ver
  `full-suite-disposition.md`.
- Source/live unit, compose e health units byte-equal.
- Monitor read-only manual + natural tick `success`.
- Lifecycle stop `success/143`, start `success/0`.
- DbOmniFleet targeted isolation PASS: somente `jenkins` e `jenkins-agent`;
  `9` outros apps, `4` forks e `5` policies intactos.
- Failed units system/user `0/0`.

## Jenkins agents K3s

- `2/2 Ready` mede apenas pods placeholder.
- O command live faz reachability probe e depois `sleep infinity`.
- Logs declaram que o plugin Kubernetes ainda é necessário.
- Controller: plugin `kubernetes=absent`, `nodes_dir=absent`.
- Disposição: `placeholder-reachability-only / not-registered`.
- O port JNLP privado foi preservado para futura ativação, mas nenhum agent foi
  apresentado como conectado nesta reconciliação.

## False-start desta reconciliação

- O primeiro cutover criou um snapshot íntegro, mas o harness exigia `2.911` files. A árvore parada tinha `2.912`: Jenkins gravou um arquivo entre o archive histórico e o stop atual. O validator foi corrigido para comparar snapshot e árvore parada no mesmo instante. Rollback restaurou o serviço e endpoints antes da segunda tentativa.
- A segunda snapshot consistente comparou árvore parada e archive no mesmo
  instante e passou. O runtime retomou com novos arquivos internos normais do
  Jenkins sem alterar o hash de `config.xml`.
- O primeiro dry-run targeted de `jenkins-agent` abortou antes do COMMIT:
  o read model não trazia `observed_at/updated_at` e o SQL de rollback tentou
  gravar `NULL` em coluna `NOT NULL`. O DB permaneceu byte-semanticamente no
  preimage. O retry capturou a row raw por `to_jsonb`, provou apply + rollback
  exato na mesma transaction e só então fez o apply ativo.

## Backup e rollback

- Histórico: `/home/ubuntu/.backups/srv1-app-recovery-20260905T005017-0300`.
- Atual: `/home/ubuntu/.backups/proc-37d55995c20b-pre-hardening-20260905T215218-0300`.
- Registry rollback: `registry/rollback-jenkins-registry.sql`.
- Restaurar a unit antiga reabre `8085/50000` publicamente; break-glass somente.
- Rollback seguro de dados mantém a unit canônica e restaura apenas `jenkins_home.consistent.tgz`.

## Limites

- O FAIL histórico não vira GO.
- A conexão TCP externa observada brevemente em `50000` não foi atribuída; não é classificada como exploração confirmada.
- Probes externos são evidência observacional; a garantia primária é o bind explícito host-side em unit carregada e `ss`.
- Nenhum commit/push.

## Obsidian, GBrain e Graphify

- Obsidian: incident, daily note, worklog e session recap atualizados com
  `[[wiki-links]]`.
- GBrain: import targeted de uma nota, `1/1`, `6` chunks, `--no-embed`; body e
  timeline estruturada `id=202` tiveram readback separado. Nenhum write-through
  não-canônico foi criado.
- Graphify pre-final: `14.539` nodes, `21.224` edges, fresh/current; query exata
  `proc_37d55995c20b` retornou `55/51`, fallback pelo diretório `14/12`.
- O status definitivo pós-manifest fica no final seal externo para evitar um
  ciclo autorreferente de editar evidence depois do último rebuild.
