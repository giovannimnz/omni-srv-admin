---
status: diagnosed
trigger: "Servidor atius-srv-1 usa 100% de CPU apesar do limite global de 20%; referencia Codex 019f5933-a94c-7070-ae6e-e3181357304d"
created: 2026-07-13
updated: 2026-07-13
---

## Symptoms

- expected: builds, rebuilds, compiles e indexadores pesados ficam agregados em no maximo 0.8 CPU num host de 4 vCPU.
- actual: o host atingiu aproximadamente 99% busy, load acima de 20 e PSI CPU acima de 80, enquanto o cgroup coletivo de builds ficou vazio.
- errors: nao ha erro de quota; o problema e a topologia concorrente de cgroups.
- timeline: observado durante a continuacao da sessao Codex 019f5933-a94c-7070-ae6e-e3181357304d em 2026-07-13.
- reproduction: executar build com varios processos enquanto atius-build-throttle.timer varre processos a cada 30 segundos.

## Current Focus

- hypothesis: confirmada; o scanner root move cada PID de build para um cgroup irmao com quota individual, destruindo o teto agregado, e cada execucao protegida agenda novos audits pesados sem deduplicacao, lock ou quota; cargas interactive/system/kubepods continuam fora do profile builds.
- test: comparar /proc/PID/cgroup, cpu.max do omni-builds.slice, cpu.max dos filhos atius-build-throttle e uso agregado via cpu.stat/mpstat.
- expecting: omni-builds.slice vazio; varios pid-* com 20000/100000; pai atius-build-throttle unlimited; CPU total proxima de 100%.
- next_action: revisar a causa raiz e propor plano de correcao sem aplicar mudancas nesta sessao.
- reasoning_checkpoint:
  hypothesis: "/usr/local/sbin/atius-build-throttle causa perda do teto agregado porque move cada processo para /atius-build-throttle/pid-PID e aplica 0.2 CPU individualmente sob um pai sem quota."
  confirming_evidence:
    - "omni-builds.slice tinha cpu.max=80000/100000, equivalente a 0.8 CPU, mas TasksCurrent=0."
    - "cc1 e dois graphify estavam em /atius-build-throttle/pid-* com cpu.max=20000/100000; o pai tinha cpu.max=max/100000."
    - "o scanner aplicava limites a 8-13 PIDs e a propria service root nao tinha CPUQuota."
    - "havia 14 timers omni-post-build-audit-* acumulados e dois resource-governor-audit.py simultaneos em app.slice sem quota."
    - "mpstat mediu cerca de 99% busy, load acima de 20 e PSI CPU avg10 acima de 80."
  falsification_test: "a hipotese seria falsa se todos os descendentes permanecessem em um unico cgroup com cpu.max=80000/100000 e a soma da arvore ultrapassasse 0.8 CPU."
  fix_rationale: "um unico cgroup agregado preserva o limite da arvore inteira; quotas por PID somam com a quantidade de processos e nao implementam 20% do host."
  blind_spots: "a captura e pontual; Electron/Codex, workloads Python, k3s, steal e swap tambem contribuem e precisam de politicas proprias, sem serem confundidos com builds."
- tdd_checkpoint:

## Evidence

- timestamp: 2026-07-13T01:20:27-03:00
  result: "atius-srv-1 tinha 4 vCPU, load 21.19/20.57/15.72 e varios consumidores simultaneos."
- timestamp: 2026-07-13T01:21:24-03:00
  result: "mpstat medio registrou 1.00% idle, 47.75% usr, 8.68% nice, 37.90% sys e 3.26% steal."
- timestamp: 2026-07-13T01:21:24-03:00
  result: "PSI CPU some avg10=81.57; cgroup coletivo omni-builds tinha cpu.max=80000/100000 e zero processos."
- timestamp: 2026-07-13T01:21:24-03:00
  result: "dois graphify estavam em cgroups separados pid-679952 e pid-861444, cada um com cpu.max=20000/100000 e pai atius-build-throttle sem quota."
- timestamp: 2026-07-13T01:21:41-03:00
  result: "Electron GPU orfao em omni-interactive consumiu 98% de um core; dois graphify consumiram cerca de 20% de um core cada."
- timestamp: 2026-07-13T01:22:00-03:00
  result: "/usr/local/sbin/atius-build-throttle linhas 67-74 criam um cgroup por PID e movem o processo; a service root tem CPUQuotaPerSecUSec=infinity."
- timestamp: 2026-07-13T01:27:00-03:00
  result: "list-units mostrou 14 timers omni-post-build-audit-* e dois audits ativos simultaneamente; srv1_ops.py agenda um novo audit para cada workload e resource-governor-audit.py nao possui flock/singleton."

## Eliminated

- hypothesis: "CPUQuota=80% significa 80% do host."
  reason: "no systemd, 80% representa 0.8 CPU; em quatro vCPUs equivale a 20% do host."
- hypothesis: "um unico cc1 da sessao explica 100% do host."
  reason: "o processo foi medido a aproximadamente 19.5% de um core e depois terminou; era apenas uma parcela da carga."
- hypothesis: "o cgroup coletivo omni-builds esta configurado com quota errada."
  reason: "cpu.max=80000/100000 estava correto; a falha e os processos serem retirados dele."

## Resolution

- root_cause: "Dois governadores conflitantes e fan-out de hygiene: o wrapper cria uma slice coletiva correta de 0.8 CPU, mas atius-build-throttle.timer move cada PID para cgroups irmaos de 0.2 CPU sob pai unlimited; alem disso, cada workload agenda outro audit pesado sem deduplicacao/lock/quota, gerando timers e audits concorrentes fora de builds. Cargas interactive/system/kubepods completam a saturacao."
- fix: "nao aplicado; diagnostico somente. A direcao e remover a movimentacao por PID, manter a arvore inteira em um cgroup agregado de 0.8 CPU, limitar/substituir o scanner root e tornar o audit singleton, deduplicado e governado."
- verification: "rollout recuperado, /proc/PID/cgroup, cpu.max em cada ancestral, mpstat, PSI, top, cpu.stat e systemd unit live."
- files_changed: ".planning/debug/resource-governor-host-cpu-saturation.md"
