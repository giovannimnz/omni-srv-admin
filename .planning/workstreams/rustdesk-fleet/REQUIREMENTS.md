# Requirements: RustDesk Fleet Remote Access

**Defined:** 2026-07-19
**Milestone:** v1.9
**Core Value:** Todos os cinco computadores autorizados podem ser acessados e controlar os demais por RustDesk self-hosted, com segurança, rollback e evidência completa, sem degradar os acessos existentes.

## v1.9 Requirements

### Scope and Architecture

- [x] **SCP-01**: O operador instala RustDesk exatamente em `atius-srv-1`, `atius-srv-2`, `atius-srv-3`, `horistic-srv` e `GIOVANNI-W11-PC`, excluindo WSL e `GIOVANNI-S23`.
- [x] **SCP-02**: O operador usa RustDesk Server OSS enquanto o escopo permanecer single-operator sem SSO, RBAC, MFA, API nativa central do RustDesk ou auditoria humana central; qualquer requisito desses promove um gate explícito para Pro. Uma API operacional custom da Atius, separada e sem se anunciar como `API Server` do client, não altera essa decisão.
- [x] **SCP-03**: O tráfego usa policy direct-first em produção e forced-relay somente em testes controlados ou fallback comprovado.
- [x] **SCP-04**: Server `1.1.15` e clients `1.4.9` ficam pinados por tag, commit, digest/checksum e arquitetura, sem `latest` ou build nos hosts.
- [x] **SCP-05**: Todo artefato e comando GSD do milestone é isolado em `rustdesk-fleet`, preservando a integridade do workstream da Phase 48 e serializando arquivos compartilhados.

### Server, Edge, and Secrets

- [x] **SRV-01**: O primary só é selecionado após usar no máximo 78% antes do deploy, no máximo 80% depois, inodes no máximo 80% e headroom em bytes suficiente para imagem, dois backups e 30 dias de logs; `horistic-srv` passou esse gate após `atius-srv-2/3` ficarem `NO-GO`.
- [ ] **SRV-02**: `hbbs` e `hbbr` rodam em Quadlets Podman rootless hardened, `Network=host`, sem privilege/socket amplo e com limite combinado de no máximo 0,8 CPU e 1 GiB RAM.
- [ ] **SRV-03**: O primary expõe somente TCP 21115-21117 e UDP 21116; TCP 21114/21118/21119 e qualquer listener não aprovado permanecem fechados em IPv4/IPv6 conforme a política definida.
- [ ] **SRV-04**: `rustdesk.atius.com.br` usa DNS-only e ingress OCI/host deny-first; probes realmente externos comprovam TCP e UDP antes do rollout.
- [x] **SRV-05**: A private server key e os cinco permanent passwords existem somente no Vault/runtime efêmero; clients recebem uma única public key pinada e artefatos guardam apenas fingerprints/hashes.
- [ ] **SRV-06**: Três restarts e um boot preservam a fingerprint, a identidade, os dados e os listeners do primary sem crescimento de logs ou recursos fora do contrato.
- [x] **SRV-07**: Backup e restore reais do estado do server preservam a mesma public key antes de publicar o edge e antes de instalar clients de frota.

### Managed Clients

- [ ] **CLI-01**: `horistic-srv` funciona como canary Ubuntu ARM64 usando o `.deb` 1.4.9 verificado e reporta package, service, config e RustDesk ID estáveis.
- [ ] **CLI-02**: `GIOVANNI-W11-PC` usa o MSI x86-64 1.4.9 verificado, com serviço automático e config persistente após reboot.
- [ ] **CLI-03**: Cada target possui RustDesk ID único, inventariado de forma redacted, e permanent password própria carregada do Vault sem stdout, argv, history ou arquivo persistente inseguro.
- [ ] **CLI-04**: A permission matrix least-privilege decide e testa keyboard/mouse, clipboard, file transfer, audio, terminal, TCP tunnel, restart, privacy mode e recording por profile.
- [ ] **CLI-05**: Cada Linux prova sessão LXDE/X11 ativa, lock/logout, reconnect e acesso antes de login após reboot sem alterar LightDM, habilitar autologin ou fabricar dummy display.
- [ ] **CLI-06**: O Windows prova target correto, lock/logon screen, UAC secure desktop, console/RDP session e reconnect após reboot.
- [ ] **CLI-07**: Cada host é testado como controller e como target com imagem, keyboard, mouse e marker de identidade reais.
- [ ] **CLI-08**: RustGuac, XRDP, AnyDesk, NoMachine e noVNC permanecem instalados e passam seus regression smokes até decisão futura separada.
- [ ] **CLI-09**: `atius-srv-1`, `atius-srv-2` e `atius-srv-3` usam o `.deb` ARM64 1.4.9 verificado e reportam package, service, config e RustDesk ID estáveis após rollout serial.

### Exhaustive Validation

- [ ] **VAL-01**: Os 20 pares dirigidos não-self passam em policy normal, registrando o transporte natural observado sem presumir direct.
- [ ] **VAL-02**: Cinco sessões adicionais forced-relay passam, uma recebida por cada target, com UI, pairing log e byte delta correlacionados no `hbbr`.
- [ ] **VAL-03**: Wrong password falha em 5/5 targets; wrong server key e nonexistent ID falham em profiles disposable Linux e Windows.
- [ ] **VAL-04**: Toda capability proibida pela permission matrix falha e nenhuma sessão contata servidores públicos RustDesk.
- [ ] **VAL-05**: Toda sessão aceita prova screen, keyboard marker, mouse, target/session identity e transporte; ausência de campo obrigatório resulta em BLOCKED, nunca PASS.
- [ ] **VAL-06**: Cada target passa 30 minutos de sessão, três reconnects e reboot; W11-Horistic passa soak forced-relay representativo de duas horas e interrupção controlada.
- [ ] **VAL-07**: Evidências redacted e imutáveis incluem manifest, expected matrix, verdict, host/session JSON, logs sanitizados, socket summaries, screenshots headless e SHA256SUMS.

### Resilience and Recovery

- [ ] **DR-01**: `atius-srv-3` só é chamado de cold standby após capacity gate, restore da mesma identidade e services stopped/disabled para impedir split-brain.
- [ ] **DR-02**: Failover real `srv-2 -> srv-3` e failback preservam IDs/config, convergem DNS/ingress com RTO alvo de 30 minutos e nunca deixam dois primaries ativos.
- [ ] **DR-03**: Upgrade e downgrade de server e clients canary preservam identidade, config, password e conectividade.
- [ ] **DR-04**: Rollback real passa no primary, em um Linux e no Windows antes do aceite final e mantém os fallbacks existentes acessíveis.

### Operations and Closeout

- [ ] **OPS-01**: Monitoring e uma API operacional custom da Atius expõem endpoints HTTPS versionados e redacted para health, readiness, status e resumo de métricas — listeners, restarts, CPU, RAM, disk, log growth, direct/relay bytes e falhas — sem secrets, sem simular a API nativa Pro e sem abrir/configurar TCP 21114 como `API Server` do RustDesk.
- [ ] **OPS-02**: Inventory, port map, Cloudflare/OCI notes, module README e runbook descrevem exatamente versões, paths, portas, hosts, rollback e provas live.
- [ ] **OPS-03**: Obsidian e GBrain são consultados/atualizados antes, durante e depois; Graphify fica fresh após mudanças de planning, código e docs.
- [ ] **OPS-04**: `VALIDATION.md`, `VERIFICATION.md` e `UAT.md` concordam requirement por requirement, incluindo checkpoints humanos de UAC, pre-login, ABNT2, multi-monitor e qualidade visual.

## Future Requirements

### Central Management

- **PRO-01**: Operadores distintos autenticam via Atius SSO/OIDC com RBAC e MFA no RustDesk Server Pro.
- **PRO-02**: Device management, policy central, API/web console nativas do RustDesk e audit trail atribuível a pessoa são avaliados após o baseline OSS; a API operacional custom da Atius não substitui essas capacidades Pro.

## Out of Scope

| Feature | Reason |
|---------|--------|
| RustDesk no WSL | Exclusão explícita do milestone. |
| RustDesk no `GIOVANNI-S23` | Exclusão explícita por enquanto. |
| Remover RustGuac, XRDP, AnyDesk, NoMachine ou noVNC | São fallbacks de recuperação; retirement exige decisão e milestone separados. |
| Active-active `hbbs` | O baseline usa primary mais cold standby para evitar split-brain de identidade. |
| Web client, console/API nativas do RustDesk e portas 21114/21118/21119 | Não pertencem ao baseline OSS native-only; endpoints operacionais custom da Atius usam serviço, autenticação e hostname separados. |
| Trocar LightDM por GDM, habilitar autologin ou criar virtual seat | Mudança disruptiva fora do canary; falha headless vira blocker ou fase separada. |
| Pro/custom client sem gate de licença | Só entra se os requisitos Pro forem declarados obrigatórios e autorizados. |

## Traceability

Cada requisito v1.9 mapeia para exatamente uma Phase 51-58. O status permanece Pending até o gate da phase produzir evidência automatizada/live atual; summary-only não altera status.

| Requirement | Phase | Status |
|-------------|-------|--------|
| SCP-01 | Phase 51 | Complete |
| SCP-02 | Phase 51 | Complete |
| SCP-03 | Phase 51 | Complete |
| SCP-04 | Phase 52 | Complete |
| SCP-05 | Phase 51 | Complete |
| SRV-01 | Phase 52 | Complete |
| SRV-02 | Phase 53 | Pending |
| SRV-03 | Phase 53 | Pending |
| SRV-04 | Phase 53 | Pending |
| SRV-05 | Phase 52 | Complete |
| SRV-06 | Phase 53 | Pending |
| SRV-07 | Phase 52 | Complete |
| CLI-01 | Phase 54 | Pending |
| CLI-02 | Phase 54 | Pending |
| CLI-03 | Phase 55 | Pending |
| CLI-04 | Phase 54 | Pending |
| CLI-05 | Phase 55 | Pending |
| CLI-06 | Phase 54 | Pending |
| CLI-07 | Phase 56 | Pending |
| CLI-08 | Phase 55 | Pending |
| CLI-09 | Phase 55 | Pending |
| VAL-01 | Phase 56 | Pending |
| VAL-02 | Phase 56 | Pending |
| VAL-03 | Phase 56 | Pending |
| VAL-04 | Phase 56 | Pending |
| VAL-05 | Phase 56 | Pending |
| VAL-06 | Phase 57 | Pending |
| VAL-07 | Phase 58 | Pending |
| DR-01 | Phase 57 | Pending |
| DR-02 | Phase 57 | Pending |
| DR-03 | Phase 57 | Pending |
| DR-04 | Phase 57 | Pending |
| OPS-01 | Phase 53 | Pending |
| OPS-02 | Phase 58 | Pending |
| OPS-03 | Phase 58 | Pending |
| OPS-04 | Phase 58 | Pending |

**Coverage:**

- v1.9 requirements: 36 total
- Mapped to phases: 36
- Unmapped: 0
- Duplicate mappings: 0
- Coverage tuple (total/mapped/unmapped): 36/36/0

---
*Requirements defined: 2026-07-19*
*Last updated: 2026-07-22 after Phase 52 live gate and independent closeout*
