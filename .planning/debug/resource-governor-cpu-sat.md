---
status: resolved
trigger: "Aplicar correcoes do incidente de saturacao de CPU causado por cgroups concorrentes e hygiene sem exclusao mutua."
created: 2026-07-13
updated: 2026-07-13
---

## Symptoms

- expected: toda arvore de build limitada de forma agregada a 0.8 CPU num host de 4 vCPU; hygiene singleton e bounded.
- actual: scanner legado move PIDs para cgroups individuais; cada build agenda novos audits sem deduplicacao; host satura.
- errors: nenhum erro funcional de quota; a topologia e o fan-out invalidam o teto agregado.
- timeline: diagnosticado em 2026-07-13, referencia Codex 019f5933-a94c-7070-ae6e-e3181357304d.
- reproduction: executar builds concorrentes/aninhados com atius-build-throttle.timer ativo e observar timers omni-post-build-audit acumularem.

## Current Focus

- hypothesis: confirmada; dois governadores conflitantes e hygiene sem semaforo/fila singleton causam escape e fan-out.
- test: validar membership da arvore, cpu.max agregado, ausencia de pid-* legacy, fila bounded e apenas um audit ativo.
- expecting: um unico omni-builds.slice com cpu.max=80000/100000; zero timer legacy; no maximo um job de cada hygiene pendente/ativo.
- next_action: acompanhar Prometheus apos o proximo Helm rollout e manter o scanner legado ausente.
- reasoning_checkpoint:
  hypothesis: "Mover cada PID para um cgroup proprio soma quotas; agendar audit por invocacao cria concorrencia sem limite."
  confirming_evidence:
    - "omni-builds.slice correto estava vazio enquanto processos apareciam em /atius-build-throttle/pid-* sob pai unlimited."
    - "14 timers post-build audit e dois audits simultaneos foram observados."
  falsification_test: "o fix falha se descendentes sairem da slice agregada, se houver mais de um audit ativo ou se a arvore superar 0.8 CPU."
  fix_rationale: "cgroup agregado limita a arvore; lock non-blocking e units estaveis colapsam eventos duplicados em fila bounded."
  blind_spots: "cargas interactive, k3s e system ficam fora do budget de builds e exigem monitoramento separado."
- tdd_checkpoint: "53 testes focados passaram; fan-out sintetico mediu 0.766 CPU agregado sob teto 0.8."

## Evidence

- timestamp: 2026-07-13T01:21:24-03:00
  result: "CPU aproximadamente 99% busy; PSI CPU avg10 acima de 80."
- timestamp: 2026-07-13T01:27:00-03:00
  result: "14 timers audit acumulados e dois audits simultaneos sem quota."
- timestamp: 2026-07-13T02:00:11-03:00
  result: "Duas solicitacoes live produziram tres timers estaveis; a segunda foi coalescida e zero units omni-post-build-* foram criados."
- timestamp: 2026-07-13T02:02:34-03:00
  result: "Fan-out de quatro processos mediu 0.766 CPU agregado; cpu.max permaneceu 80000 100000."
- timestamp: 2026-07-13T02:12:04-03:00
  result: "Audit pesado concluiu com success dentro de omni-builds.slice; lock e fail-closed validados."

## Eliminated

- hypothesis: "CPUQuota=80% esta incorreto."
  reason: "80% de um core equivale a 0.8 CPU, 20% do host de 4 vCPU."

## Resolution

- root_cause: "Scanner legacy por PID desfaz o cgroup agregado; hygiene por invocacao gera fan-out sem lock, deduplicacao ou quota."
- fix: "Scanner per-PID removido; patcher consolidado nas slices systemd; build semaphore capacity=1; hygiene queue coalescente com units estaveis; audit singleton/fail-closed; textfile metrics e alertas adicionados."
- verification: "legacy timer not-found/inactive; legacy cgroup absent; zero transient units; patcher sem escapes quentes; 53 testes; systemd verify sem erros dos units alterados; Graphify 8979 nodes fresh; audit live success."
- files_changed: "cli/omni/srv1_ops.py; cli/omni/tests/test_resource_governor.py; modules/srv1-ops/{configs,scripts,systemd}; kube-prometheus values/rules; docs/operations/resource-governor.md; modules/srv1-ops/README.md; Obsidian incident note."

## Prior Artifact

- `.planning/debug/resource-governor-host-cpu-saturation.md`
