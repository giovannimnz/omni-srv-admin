# Roadmap: RustDesk Fleet Remote Access

## Overview

O milestone v1.9 entrega RustDesk self-hosted nos cinco computadores autorizados por uma sequência de oito gates observáveis: primeiro fixa contrato, threat model e isolamento do workstream; depois prova supply chain, capacity e recoverability; publica um primary mínimo; valida os canários Linux/Windows; instala os três servidores restantes de forma serial; executa a matriz exaustiva; ensaia resiliência e rollback; e somente então fecha UAT e documentação operacional. O caminho preferencial começou em `atius-srv-2`, mas os gates de capacity mantiveram `atius-srv-2` e `atius-srv-3` em `NO-GO`; após impact review e full-vector PASS, `horistic-srv` foi selecionado explicitamente, sem promoção silenciosa.

## Milestone Contract

- **Milestone:** v1.9 — RustDesk Fleet Remote Access
- **Phase span:** 51-58
- **Included clients:** `atius-srv-1`, `atius-srv-2`, `atius-srv-3`, `horistic-srv`, `GIOVANNI-W11-PC`
- **Excluded clients:** WSL e `GIOVANNI-S23`
- **Production transport:** direct-first; forced-relay somente em teste controlado ou fallback aprovado
- **Recovery invariant:** RustGuac, XRDP, AnyDesk, NoMachine e noVNC permanecem instalados; qualquer retirement pertence a outro milestone
- **Secret boundary:** private key e permanent passwords permanecem apenas no Vault/runtime efêmero; planning, Git, logs, Obsidian, GBrain e evidências guardam somente fingerprints/hashes redacted
- **Quality invariant:** cada phase deve produzir seu próprio gate automatizado e/ou live; `SUMMARY.md` ou declaração manual sem evidência não autorizam avanço
- **API boundary:** a API operacional custom da Atius é um deliverable separado do RustDesk OSS; ela não usa o campo `API Server` do client, não abre TCP 21114 e não reivindica device/account API, web console ou controles Pro

## Phases

- [x] **Phase 51: Contract, Threat Model and Workstream Isolation** - Congelar escopo, decisão OSS/Pro, ameaças, políticas e ownership do workstream antes de qualquer mutação de runtime. (completed 2026-07-20)
- [x] **Phase 52: Supply Chain, Capacity and Recoverable Placement** - Provar artefatos, capacity, Vault e restore antes de escolher e autorizar o primary. (completed 2026-07-23)
- [ ] **Phase 53: Primary Relay and Public Edge** - Disponibilizar `hbbs`/`hbbr` hardened, persistentes, observáveis e expostos somente pelas portas aprovadas. (blocked/in progress at 53-05D Wave 0; no live mutation)
- [ ] **Phase 54: Heterogeneous Canary — Horistic + Windows** - Provar Linux ARM64 e Windows x86-64, incluindo pre-login, UAC, direct e relay, antes do rollout.
- [ ] **Phase 55: Serialized Linux Fleet Rollout** - Instalar e validar `atius-srv-2` → `atius-srv-3` → `atius-srv-1`, um host por vez, preservando fallbacks.
- [ ] **Phase 56: Exhaustive Fleet, Transport and Security Matrix** - Executar 20 pares normais, cinco forced-relay e os negativos de autenticação, trust e permissões.
- [ ] **Phase 57: Standby, Resilience, Upgrade and Rollback** - Provar soak, failover/failback, upgrade/downgrade e rollback real sem split-brain ou perda de identidade.
- [ ] **Phase 58: Final UAT, Evidence and Operational Closeout** - Auditar requirement por requirement e fechar UAT, runbooks, Obsidian, GBrain e Graphify contra o runtime real.

## Dependency Chain

`51 → 52 → 53 → 54 → 55 → 56 → 57 → 58`

Cada dependência é um stop gate: uma phase em `BLOCKED`, `NO-GO` ou sem evidência obrigatória impede o início da seguinte. Fallbacks compartilhados devem permanecer instalados e receber regression smoke em toda phase que altera runtime.

## Phase Details

### Phase 51: Contract, Threat Model and Workstream Isolation

**Goal**: O operador possui um contrato testável e sem ambiguidade para escopo, edição GSD, OSS/Pro, direct/relay, secrets, permissions e preservação dos acessos existentes.
**Depends on**: Nothing (first phase in v1.9)
**Requirements**: SCP-02, SCP-03, SCP-05
**Risks**: Reivindicar recursos Pro no OSS; instalar em host excluído; mutar o workstream da Phase 48; expor secret em evidência; transformar forced-relay em default.
**Success Criteria** (what must be TRUE):

  1. O contrato enumera exatamente os cinco hosts incluídos, exclui WSL e `GIOVANNI-S23`, mantém direct-first e declara que todos os fallbacks compartilhados continuam instalados.
  2. A decisão OSS/Pro é explícita: OSS avança com aceite documentado das ausências de SSO, RBAC, MFA, API nativa central do RustDesk, policy central e auditoria humana; qualquer uma dessas exigências obrigatórias produz `NO-GO` e seleção Pro antes do runtime. A API operacional custom da Atius permanece separada e não é configurada como `API Server` do client.
  3. Threat model, permission profiles, papéis de public/private key, cinco passwords distintas e o ledger requirement-to-evidence existem sem valores secretos.
  4. O lifecycle GSD exige scope explícito `rustdesk-fleet`, writer único para arquivos compartilhados e prova de integridade da Phase 48 em cada transição.
  5. **Advance gate:** validators automatizados de escopo, IDs, ausência de secrets e isolamento do workstream, mais a revisão operacional do threat model, devem registrar PASS com artefatos atuais antes da Phase 52; summary-only não conta.

**Plans**: 3/3 plans complete

- [x] 51-01-PLAN.md
- [x] 51-02-PLAN.md
- [x] 51-03-PLAN.md

### Phase 52: Supply Chain, Capacity and Recoverable Placement

**Goal**: O operador pode autorizar um primary reproduzível somente depois de provar integridade dos artefatos, headroom, secret boundary e recuperação da identidade.
**Depends on**: Phase 51
**Requirements**: SCP-04, SRV-01, SRV-05, SRV-07
**Risks**: Imagem/tag mutável; arquitetura incorreta; `srv-2` cruzar o watchdog; promover `srv-3` silenciosamente; backup sem restore; private key/password em argv, stdout ou arquivo inseguro.
**Success Criteria** (what must be TRUE):

  1. Server `1.1.15` e clients `1.4.9` estão resolvidos por tag, commit, arquitetura e digest/checksum verificados, sem `latest` nem build nos hosts.
  2. `atius-srv-2` só é escolhido como primary com uso pre-deploy `<=78%`, inodes `<=80%`, projeção e medição post-deploy `<=80%` e headroom em bytes para imagem, dois backups e 30 dias de logs; qualquer fallback, inclusive `atius-srv-3` ou `horistic-srv`, exige capacity/security/recovery gate equivalente e replanejamento explícito dos papéis de DR.
  3. Vault é a autoridade comprovada para a private server key e cinco permanent passwords distintas; automação e evidence model demonstram hidratação efêmera sem revelar valores.
  4. Backup e restore reais, em ambiente isolado, reproduzem a mesma public-key fingerprint antes de edge ou clients de frota serem autorizados.
  5. **Advance gate:** verificadores automatizados de checksums/digests, capacity/inodes/reservas, secret scan e fingerprint, junto do restore live, devem passar antes da Phase 53; projeção, arquivo de backup ou summary-only sem restore não contam.

**Plans**: 10/10 plans complete — metadata-only closeout, hygiene seal and terminal Graphify gate PASS; Phase 53 remains independently gated

**Wave 1**

- [x] 52-01-PLAN.md — Congelar supply-chain pins e observações oficiais sem instalar ou admitir hosts.

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 52-02-PLAN.md — Codificar capacity/placement e materializar os budgets, retention e authority aprovados.

**Wave 3** *(blocked on Wave 2 completion)*

- [x] 52-03-PLAN.md — Executar o routing capacity read-only, zero-cleanup e persistir `NO-GO` atual por candidato.

**Wave 4** *(blocked on Wave 3 completion)*

- [x] 52-04-PLAN.md — Implementar Vault tmpfs/no-output e a state machine de backup/restore isolado.

**Wave 5** *(blocked on Wave 4 completion)*

- [x] 52-05-PLAN.md — Executar o full candidate gate, `capacity_finalize`, rollback e fallback até placement recuperável.

**Wave 6** *(blocked on Wave 5 completion)*

- [x] 52-06-PLAN.md — Renderizou report/ledger e topology review; o resultado atual permanece `BLOCKED/no-primary`, sem autorização para a Phase 53.

**Wave 7** *(blocked on Wave 6 completion; gap closure)*

- [x] 52-07-PLAN.md — Gate A, Gate B create-only, full gate live e closeout independente concluídos com PASS.

**Wave 8** *(blocked on Wave 7 completion; post-live source attestation)*

- [x] 52-08-PLAN.md — Attestation sucessora, dois reviews e boundary não-autorizador concluídos.

**Wave 9** *(blocked on Wave 8 completion; read-only currentness lanes)*

- [x] 52-09-PLAN.md — Intervalo Phase 53, projeção current e lanes JUnit segregadas registradas.

**Wave 10** *(completed; metadata-only closeout)*

- [x] 52-10-PLAN.md — Closeout/parity artifacts, value-free hygiene seal and terminal Graphify assertion PASS; no operational replay.

### Phase 53: Primary Relay and Public Edge

**Goal**: Os clients podem alcançar um primary RustDesk estável, hardened, recuperável e observável apenas pela superfície nativa mínima aprovada.
**Depends on**: Phase 52
**Requirements**: SRV-02, SRV-03, SRV-04, SRV-06, OPS-01
**Risks**: Rootful drift; `Network=host` expor portas extras; tradução externa divergir dos listeners nativos internos; rotação de identidade; logs sem limite; algum dos três records Cloudflare ficar proxied/AAAA/CNAME; CPU acima do guardrail; UDP validado apenas localmente; API operacional custom ser confundida com a API nativa Pro ou expor telemetria sem autenticação/redaction.
**Success Criteria** (what must be TRUE):

  1. `hbbs` e `hbbr` rodam como Quadlets Podman rootless digest-pinned, sem privilege/socket amplo, com estado gravável mínimo, logs bounded e limite combinado `<=0.8 CPU` e `<=1 GiB RAM`.
  2. `rustdesk.atius.com.br`, `rustdesk-id.atius.com.br` e `rustdesk-relay.atius.com.br` são A records DNS-only para `137.131.140.20`, sem proxy/AAAA/CNAME; probes realmente externos confirmam o public IP e os três hostnames em `34099/TCP`, `34100/TCP+UDP` e `34101/TCP`, traduzidos internamente para os listeners nativos inalterados `21115/TCP`, `21116/TCP+UDP` e `21117/TCP`, enquanto 21114-21119 e todo outro listener ficam fechados diretamente no edge público.
  3. Três restarts e um boot preservam fingerprint, identidade, dados, listeners e limites de recursos, sem crescimento de logs fora do contrato.
  4. Monitoring e uma API operacional custom da Atius, em hostname/serviço HTTPS separado e autenticado, expõem endpoints versionados/redacted de health, readiness, status e resumo de métricas para listeners, restarts, CPU, RAM, disk, log growth, direct/relay bytes e falhas. Ela não configura o `API Server` dos clients, não abre TCP 21114 e não reivindica recursos nativos Pro.
  5. **Advance gate:** testes automatizados de Quadlet/hardening/persistência, contrato/autenticação/redaction dos endpoints custom e probes live externos TCP+UDP, reboot e métricas devem passar antes da Phase 54; unit active, localhost scan ou summary-only não contam.

**Plans**: 12/22 current plan units complete (55%) + 1 retained superseded historical plan; 13 historical summaries remain. Physical inventory after this revision is 23 Phase 53 PLAN files, of which 22 are current.

- [x] 53-01-PLAN.md — Strict contracts, hermetic tests and resumable live-runner foundation.
- [x] 53-02-PLAN.md — Rootless digest-pinned `hbbs`/`hbbr`, persistent identity/state and bounded resources.
- [x] 53-03-PLAN.md — Separate authenticated/redacted Atius operational API and reversible Apache publication.
- [x] 53-04-PLAN.md — Effective host/OCI edge policy, DNS-last transaction and two-origin probe tooling.
- [x] 53-05A-PLAN.md — Candidate 1.1.16 provenance, fail-closed adapter factory, value-free journal and containment seam.
- [↪] 53-05-PLAN.md — Superseded by 53-05B; retained as the historical blocked contract.
- [x] 53-05B-PLAN.md — Canonical gap closure: hermetic production-bound adapters/contracts/evidence are closed; successor admission, fresh capacity and one ordered live transaction remain blocked.
- [x] 53-05C-PLAN.md — Explicit continuation for current admission/capacity-finalize, typed provider binding and one live-gated transaction; hermetic RuntimeProvider checkpoint is verified, while live execution remains blocked until owner-bound authority exists.
- [x] 53-05D-PLAN.md — Wave 7, depends on 05C: edge/backend hermético em nove arquivos, authority única traduzida, hbbs anunciando `rustdesk-relay.atius.com.br:34101`, installer canônico validando/materializando a forma runtime e capability split.
- [x] 53-05D2T-PLAN.md — Wave 8, depends on 05D: prova read-only PASS da topologia dual-VNIC `atius-srv-1` edge/forwarder → `horistic-srv` backend, com `10.31.1.31` não executável, OperationPlan stale rejeitado e `authorizes_live=false`.
- [x] 53-05D2A-PLAN.md — Wave 9, depends on 05D2T: reconciliação semântica cross-host de DNAT/forward, backend, OCI, DNS 3/3, probes externos, API operacional e validator; gate raiz `198 passed, 1 xfailed`.
- [x] 53-05D2B-PLAN.md — Wave 10, depends on 05D2A: runner completo, capability split, journals separados, migration handoff não executável e checker público de binding; gate raiz `205 passed, 1 xfailed` e apply negativo `exit 3` sem side effects.
- [x] 53-05D2C-PLAN.md — Wave 11, depends on 05D2B: SCP-01 convergiu para Phase 55/Pending; allowlist exata de 33 paths, current lane `902 passed, 9 deselected, 1 xfailed`, legacy lane `8 drift + 1 CLI/no-network` e seal final em `execution_source_commit=3ea1e581e62b8f0122ba69d11ebd86bacd61fa70`.
- [ ] 53-05D2Q-PLAN.md — Wave 12, depends on 05D2C: cria validator/teste reutilizáveis e sela o baseline value-free completo dos sete paths D2D sem registrar conteúdo nem alterá-los; source commit de três paths e direct summary child.
- [ ] 53-05D2R-PLAN.md — Wave 13, depends on 05D2Q: prova em smoke standalone a cadeia real `omni→systemd-run→flock→launcher/target`, o mesmo `omni-builds.slice`, a fronteira de FDs e o lifetime do lock; executa readers MCP/HTTPS/SSH bounded sem governor recursivo.
- [ ] 53-05D2V-PLAN.md — Wave 14, depends on 05D2R: produz source-only o contrato/policy fechado e a continuidade exata da chave/fingerprint Phase 52, prefix-transform byte-preserving de authorized_keys, forced dispatcher, reader derived, installer/rollback, validator strict-or-NO_GO e testes; zero install ou call live.
- [ ] 53-05D2S-PLAN.md — Wave 15, depends on 05D2V: produz apply manifest/factory, shared MCP e remote worker source-sealed enviado one-shot por stdin a `/usr/bin/sudo -n /usr/bin/python3 -I -`; cobre Cloudflare absent/create/delete-if-current e present/CAS/restore-if-current, mixed states e drift; exact-six source paths, inert antes de authority.
- [ ] 53-05D2D-PLAN.md — Wave 16, depends on 05D2S: exige igualdade do baseline Q como primeira ação, integra R/V/S, fecha `collect-and-plan`/`validate-generation`/`promote-generation`, deriva a allowlist exata dos summaries Q/R/V/S mais sete paths D e remove as quatro suposições numéricas.
- [ ] 53-05D2W-PLAN.md — Wave 17, depends on 05D2D: avalia anchors frozen, planeja a instalação ordenada/readback/rollback da rota Phase 52-continuity, coleta observação current value-free e decide somente `STRICT_EQUIVALENCE_PROVEN` ou `NO_GO`; sem equivalência estrita, nenhum downstream é executável.
- [ ] 53-05D2H-PLAN.md — Wave 18, depends on 05D2W e executável somente após decisão W autorizante: move somente os sete stale outputs canônicos para quarantine recuperável e declara flags honestas (`housekeeping_filesystem_mutation=true`, provider/network/live-runtime false).
- [ ] 53-05E-PLAN.md — Wave 19, depends on 05D2H: gera a bundle privada com todos os flags W/H, preserva rc3 em collection/promotion, aceita somente rc0 para checkpoint hash-bound e promove canonicamente em writer único; rc3 nunca pede approval/authority/provider e OperationPlan é o último marker rc0.
- [ ] 53-05F-PLAN.md — Wave 20, depends on 05E: em novo processo governor→launcher recolhe current topology/supply/capacity/Vault/host/OCI/Cloudflare/Apache e continuidade W, revalida plan/source/H/manifests/owner antes de import/factory/journal e então executa uma transação full com rollback/restore separados; drift exige novo plan+approval.
- [ ] 53-06-PLAN.md — BLOCKED, Wave 21, depends on 53-05F; a primeira task é o checkpoint preflight cujo checker rederiva bindings Q/R/V/S/D/W/H/E/F e fecha read-only com verifier/finalizer independentes.

### Phase 54: Heterogeneous Canary — Horistic + Windows

**Goal**: O operador prova, nos dois sistemas de maior risco, que RustDesk oferece controle remoto seguro e recuperável antes de tocar os demais clients.
**Depends on**: Phase 53
**Requirements**: CLI-01, CLI-02, CLI-04, CLI-06
**Risks**: LightDM funcionar apenas após login; UAC/secure desktop invisível; GUI-only drift; passwords vazarem pela CLI; canário quebrar um fallback; falso relay sem byte delta.
**Success Criteria** (what must be TRUE):

  1. `horistic-srv` instala o `.deb` ARM64 1.4.9 verificado e `GIOVANNI-W11-PC` instala o MSI x86-64 1.4.9 verificado, ambos com package/service/config/ID estáveis e rollback artifacts preservados.
  2. Horistic prova sessão LXDE/X11 ativa, lock, logout, reconnect, reboot e acesso no LightDM antes de login sem trocar display manager, habilitar autologin ou criar dummy display.
  3. Windows prova target correto, lock/logon screen, UAC secure desktop, console/RDP session, service recovery e reconnect após reboot.
  4. Os permission profiles least-privilege são aplicados e testados para keyboard/mouse, clipboard, file transfer, audio, terminal, TCP tunnel, restart, privacy mode e recording; direct-first e um forced-relay correlacionado por UI/log/bytes passam entre os canários, e os fallbacks existentes continuam acessíveis.
  5. **Advance gate:** suites automatizadas de package/config/service/security e os gates live headless de imagem, input, LightDM pre-login, UAC, direct/relay, reboot e fallback regression devem passar antes da Phase 55; ID/service state ou summary-only não contam.

**Plans**: 1/5 current plan units complete; summaries for 54-02, 54-03 and 54-04 are code-only-blocked and do not close those plans. All live execution remains blocked until Phase 53 independent PASS.
**UI hint**: yes

### Phase 55: Serialized Linux Fleet Rollout

**Goal**: Os cinco hosts ficam registrados como clients estáveis depois de um rollout Linux atribuído host a host, sem remover nenhuma rota de recuperação.
**Depends on**: Phase 54
**Requirements**: SCP-01, CLI-03, CLI-05, CLI-08, CLI-09
**Risks**: Instalação paralela esconder causa; ID duplicado; secret em processo/log; pre-login falhar em um servidor; RustDesk alterar LightDM ou fallback; instalar no WSL por engano.
**Success Criteria** (what must be TRUE):

  1. O rollout instala e valida estritamente `atius-srv-2` → `atius-srv-3` → `atius-srv-1`, nunca em paralelo, e só inicia o host seguinte após PASS completo e rollback point do anterior.
  2. Os três hosts usam `.deb` ARM64 1.4.9 verificado e, junto dos canários, totalizam cinco IDs únicos redacted, cinco passwords próprias hidratadas do Vault e package/service/config estáveis.
  3. Cada Linux prova LXDE/X11 ativo, lock, logout, reconnect, reboot e pre-login LightDM sem autologin, dummy display ou alteração do display manager.
  4. RustGuac, XRDP, AnyDesk, NoMachine e noVNC permanecem instalados e seus regression smokes passam após cada host, com rollback externo ao RustDesk disponível.
  5. **Advance gate:** o verificador automatizado de inventory/version/config/ID/secret hygiene e os gates live por host de input, reboot, pre-login e fallbacks devem passar antes da Phase 56; rollout parcial ou summary-only não contam.

**Plans**: TBD

### Phase 56: Exhaustive Fleet, Transport and Security Matrix

**Goal**: O operador possui prova íntegra de cada direção controller→target, de relay por target e de todas as negações de segurança exigidas.
**Depends on**: Phase 55
**Requirements**: CLI-07, VAL-01, VAL-02, VAL-03, VAL-04, VAL-05
**Risks**: Confundir pares não dirigidos; presumir transporte direct; relay provar só o servidor; aceitar screenshot sem identidade; capability proibida funcionar; conexão alcançar infra pública RustDesk.
**Success Criteria** (what must be TRUE):

  1. Os 20/20 pares dirigidos não-self passam em policy normal, e cada sessão registra controller, target, timestamp, screen, keyboard marker, mouse marker, target/session identity e transporte natural observado sem presumir direct.
  2. Cinco sessões adicionais forced-relay passam, exatamente uma recebida por cada target, com UI, pairing log e byte delta correlacionados no `hbbr`.
  3. Wrong password falha em 5/5 targets; wrong server key e nonexistent ID falham em profiles disposable Linux e Windows, sem contaminar a configuração gerenciada.
  4. Toda capability proibida por profile falha, nenhuma sessão contata servidores públicos RustDesk, e ausência de qualquer campo obrigatório gera `BLOCKED`, nunca PASS.
  5. **Advance gate:** o parser automatizado da expected matrix deve provar exatamente 20 normal + 5 forced-relay, todos os negativos e zero campos/pares ausentes, enquanto as sessões live provam cada marcador antes da Phase 57; amostra parcial, inferência de transporte ou summary-only não contam.

**Plans**: TBD
**UI hint**: yes

### Phase 57: Standby, Resilience, Upgrade and Rollback

**Goal**: O operador consegue sustentar sessões, atualizar, recuperar e inverter o serviço sem perder identidade, acesso ou os fallbacks existentes.
**Depends on**: Phase 56
**Requirements**: VAL-06, DR-01, DR-02, DR-03, DR-04
**Risks**: Split-brain; standby com chave divergente; failover só teórico; RTO não medido; rollback ser apenas documentação; soak esconder log/disk growth; downgrade perder password/config.
**Success Criteria** (what must be TRUE):

  1. Cada target completa 30 minutos de sessão, três reconnects e reboot; W11↔Horistic completa soak forced-relay de duas horas com interrupção controlada e métricas de resource/log growth dentro do contrato.
  2. Com `horistic-srv` como primary aprovado, nenhum host co-located é tratado como DR; o standby exige failure domain independente, capacity gate e restore da mesma identidade, permanecendo stopped/disabled fora do drill.
  3. Failover real entre `horistic-srv` e o standby aprovado, seguido de failback, converge DNS/ingress, preserva IDs/config, mede RTO alvo de 30 minutos e prova que nunca há dois primaries ativos.
  4. Upgrade e downgrade do server e dos clients canary, seguidos de rollback real no primary, em um Linux e no Windows, preservam identidade, config, password, direct/relay connectivity e acesso pelos fallbacks.
  5. **Advance gate:** validators automatizados de identidade, single-primary, versões, RTO e soak, mais os drills live timestamped de failover/failback, upgrade/downgrade e rollback, devem passar antes da Phase 58; backup existente, runbook ou summary-only não contam.

**Plans**: TBD

### Phase 58: Final UAT, Evidence and Operational Closeout

**Goal**: O milestone fecha com uma única verdade auditável que concorda com o runtime, preserva recovery paths e pode ser repetida por outro ciclo operacional.
**Depends on**: Phase 57
**Requirements**: VAL-07, OPS-02, OPS-03, OPS-04
**Risks**: Evidência conter secrets; docs divergirem do runtime; requisito marcado por herança; Graphify stale; Phase 48 alterada; checkpoints humanos omitidos; fallback removido silenciosamente.
**Success Criteria** (what must be TRUE):

  1. Evidências redacted e imutáveis incluem manifest, expected matrix, verdict, host/session JSON, logs sanitizados, socket summaries, screenshots headless e `SHA256SUMS`, e um validator rejeita missing fields, secrets e hashes divergentes.
  2. Inventory, port map, Cloudflare/OCI notes, module README e runbook concordam com versões, paths, portas, hosts, rollback, monitoring e provas live atuais; todos os fallbacks compartilhados continuam instalados e passam a regressão final.
  3. `VALIDATION.md`, `VERIFICATION.md` e `UAT.md` concordam requirement por requirement e o `$gsd-verify-work` executa o UAT final, incluindo checkpoints humanos de UAC, pre-login, ABNT2, multi-monitor e qualidade visual.
  4. Obsidian e GBrain foram consultados/atualizados antes, durante e depois, Graphify está fresh após planning/código/docs, e a integridade do workstream da Phase 48 é comprovada.
  5. **Closure gate:** audit automatizado 36/36 sem orphan/duplicate, evidence-integrity suite, live final UAT e fallback regression devem passar antes de declarar v1.9 shipped; nenhum summary-only PASS, waiver implícito ou evidência de phase anterior substitui o gate atual.

**Plans**: TBD

## Progress

**Execution Order:** Phases execute in numeric order: 51 → 52 → 53 → 54 → 55 → 56 → 57 → 58.

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 51. Contract, Threat Model and Workstream Isolation | 3/3 | Complete    | 2026-07-20 |
| 52. Supply Chain, Capacity and Recoverable Placement | 10/10 | Complete | 2026-07-23 |
| 53. Primary Relay and Public Edge | 12/22 current + 1 retained historical | Blocked/in progress before Q→R→V→S→D→W→H→E→F→06; the known frozen-anchor state is insufficient, only strict equivalence can authorize W, and no live mutation is authorized | - |
| 54. Heterogeneous Canary — Horistic + Windows | 1/5 current | Blocked by Phase 53; 54-02/03/04 summaries are code-only-blocked, not completion | - |
| 55. Serialized Linux Fleet Rollout | 0/TBD | Not started | - |
| 56. Exhaustive Fleet, Transport and Security Matrix | 0/TBD | Not started | - |
| 57. Standby, Resilience, Upgrade and Rollback | 0/TBD | Not started | - |
| 58. Final UAT, Evidence and Operational Closeout | 0/TBD | Not started | - |

---
*Roadmap created: 2026-07-19 from the approved three-round RustDesk research convergence*

## Planning Metrics Basis

- Physical inventory after adding 53-05D2V and 53-05D2W: 41 PLAN files.
- Current semantic denominator: 40 current plan units; `53-05-PLAN.md` is one retained superseded historical plan outside that denominator.
- Current semantic completion: 26/40 = 65%.
- Structural analyzer projection at revision time: 30 summaries / 41 physical PLAN files = 73%; this is inventory coverage, not operational completion.
- Phase 53 basis: 22 current plan units + 1 retained historical, with 12/22 current-complete and 13 historical summaries retained.
- Phase 54 basis: 1/5 current-complete; code-only-blocked summaries do not complete plans.
