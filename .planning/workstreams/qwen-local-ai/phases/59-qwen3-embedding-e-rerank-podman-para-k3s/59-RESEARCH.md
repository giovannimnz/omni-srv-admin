# Phase 59: Qwen3 Embedding e Rerank Podman para k3s - Research

**Researched:** 2026-07-23
**Domain:** cutover GTE -> Qwen3 em ARM64/k3s, TEI/ONNX, router/governor Redis e migração Qdrant
**Confidence:** MEDIUM — contratos locais e artefatos estão verificados; autoridade Qdrant, sizing de memória, topologia live e resultados de aceitação permanecem deliberadamente `UNKNOWN`.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

### Modelo e runtime

- **D-01:** Qwen sera o titular ao final da fase. GTE permanece disponivel e imutavel como rollback ate o gate final de retirement.
- **D-02:** Qwen Embedding usara `janni-t/qwen3-embedding-0.6b-int8-tei-onnx`, revision `8fe0c238c7c48016d28e750413ca492024be3ddf`, no TEI com OrtBackend/ONNX Runtime. O INT8 esta incorporado no `model.onnx`.
- **D-03:** O contrato de pooling sera decidido por gate A/B entre `last-token` e `mean`, comparado ao oracle oficial FP16 `Qwen/Qwen3-Embedding-0.6B`. `last-token` e a preferencia normativa do modelo oficial; nenhum candidato sera promovido sem equivalencia funcional, instruction-aware e de ranking. A saida de producao sera 1024d normalizada.
- **D-04:** Qwen Reranker usara `onnx-community/Qwen3-Reranker-0.6B-ONNX`, revision `9995c50e2310679108a55f5ccd16ba8be9f17c20`, em servico HTTP ONNX dedicado. TEI nao sera usado para o reranker enquanto nao houver suporte oficial ao CausalLM yes/no.
- **D-05:** Os aliases de modelo serao `embedding-qwen3-0.6b-int8-1024-v1` e `reranker-qwen3-0.6b-int8-v1`. `embedding-gte-v1` e `reranker-gte-multilingual-v1` nunca serao silenciosamente remapeados para Qwen.
- **D-06:** Imagens, modelos, lockfiles e bases de build devem ser pinados por revision/digest e validados para `linux/arm64`; tags `latest` e revisions `main` bloqueiam promocao.

### Pipeline, governor e recursos

- **D-07:** O governor implementara no Redis existente uma maquina de estados persistente `QUEUED -> EMBEDDING -> VECTOR_SEARCH -> RERANK -> COMPLETED`, com terminais `FAILED`, `CANCELLED` e `EXPIRED`.
- **D-08:** Havera no maximo dois pipelines completos simultaneos. A lease permanece ocupada durante todo o ciclo, continuacoes tem prioridade sobre novos ciclos, e liberacao por sucesso, erro, cancelamento, TTL ou restart e idempotente. Chamadas standalone de embedding usam classe de admission separada.
- **D-09:** O estado final tera dois pods de embedding e dois pods de reranker. Cada pod normal tera `requests.cpu=500m` e `limits.cpu=500m`; quatro pods totalizam `2000m`.
- **D-10:** O rollout do reranker sera progressivo: um pod, warmup/sizing, depois dois pods. O estado final e fixo em 2+2; HPA 2-4 fica fora desta fase ate memoria e CPU reais demonstrarem headroom.
- **D-11:** Qwen usara namespace dedicado, sem `hostNetwork`, com quota, Pod Security, NetworkPolicy comprovadamente aplicada e Services/NodePorts acessiveis apenas pela rede privada do router.
- **D-12:** Wave 0 observa e registra o HPA GTE 2–4 sem mutação; Wave 2 altera o manifesto versionado, aplica e lê de volta source/live/recovery 2–2 antes de gerar o anchor. GTE fica em 1 embedding + 2 reranker = `1500m`, e a coexistência com Qwen `2000m` totaliza `3500m`. Jobs de build, reindex, oracle e soak não serão agendados no Horistic se consumirem o quinto slot; devem rodar em outro node ou runner externo, cada um limitado a `500m`.
- **D-13:** O governor e o Kubernetes sao controles complementares: a fila limita ciclos ativos; requests/limits, quota e memory requests determinam scheduling. Metrica ausente no Metrics API exige Prometheus/cgroup/container metrics, nunca bypass.
- **D-25:** Estado de segurança no Redis exige Redis Open Source `>=7.2`, AOF no primary e em pelo menos uma replica em failure domain independente. Cada escrita que libera admission, backend, alias mutation, slot ou avanço do soak deve ser seguida na mesma conexão por `WAITAOF 1 1 TIMEOUT`, com ambos os contadores confirmados antes do efeito externo. `WAIT`, `appendfsync everysec`, acknowledgement em memória ou `WAITAOF` dentro de Lua/MULTI não satisfazem o gate.

### Dimensao, indices e dados

- **D-14:** Qwen usara 1024 dimensoes para documentacao tecnica. GTE permanece 768d; padding, truncamento ou mistura entre os espacos vetoriais e proibido.
- **D-15:** A Wave 0 deve resolver a autoridade live do Qdrant, endpoint, versao, auth, storage, backups, aliases e collections antes de qualquer mutacao. `UNKNOWN` bloqueia.
- **D-16:** As collections fisicas Qwen serao `gbrain_qwen3_1024_v1`, `obsidian_qwen3_1024_v1` e `graphify_qwen3_1024_v1`, `Cosine`, com aliases estaveis por corpus. Collections GTE 768d permanecem imutaveis e recuperaveis.
- **D-17:** GTE e Qwen serao indexados a partir do mesmo corpus-fonte congelado, com chunking, logical IDs, high-water marks e checksums reproduziveis. Paridade e medida contra o corpus-fonte, nao contra a cobertura parcial existente.
- **D-26:** Qdrant separa control plane e data plane. Somente o alias arbiter possui credential/egress de aliases. Como o RBAC nativo do Qdrant não expressa todas as negações por operação, um data broker L7 separado, sem passthrough genérico, é o único portador da credential Qdrant de data management. Um issuer independente sem Qdrant access TokenReviews o projected ServiceAccount token e lê a cadeia live Pod UID→ownerReference→Job UID/resourceVersion→runner/image/nonce antes de assinar o certificado efêmero; o broker revalida token/certificado/attestation e expõe somente API privada mTLS de operações fixas. Firewall/NetworkPolicy permitem somente o runner congelado. Provisionamento, reindex, snapshot e replay usam credentials distintas, limitadas às três collections Qwen exatas; aliases/delete/GTE/admin são negados. O replay da Wave 8 roda em Job digest-pinned de 500m fora de Horistic e termina com revoke, exclusão por UID e TokenReview/broker/network negativos.

### Gates, cutover e rollback

- **D-18:** O reranker deve corrigir left padding, preservacao do suffix, truncation budget, fila limitada, TTL, cancelamento, redaction, shutdown e score single/batch antes do rollout. O envelope inicial e batch interno 1, contexto 512 e ate 20 documentos sequenciais.
- **D-19:** O gate de embedding cobre instruction somente na query, documentos sem instruction, 1024d, normalizacao, batch 1/4, cosine single/batch `>=0.9999`, oracle FP16 e ranking. Thresholds INT8-versus-FP16 sao congelados na Wave 0 antes de observar resultados.
- **D-20:** Qualidade usa corpus/qrels PT-BR tecnico e codigo congelados antes da execucao: Recall@20 e nDCG@10 do Qwen nao podem ser inferiores ao GTE alem da tolerancia predeclarada. Capacidade usa pelo menos cinco rounds warm-cache e CPU-seconds `<=1.05x` GTE.
- **D-21:** O cutover usa drain de admission, zero leases, pausa de writers, journal, CAS no banco do router e aliases Qdrant, readback independente e rollback compensatorio automatico em qualquer falha.
- **D-22:** O soak ocorre por no minimo 72 horas continuas com Qwen titular e GTE rollback-ready. Hard failures executam rollback automatico; a espera retorna `external_job_waiting` e reata ao UID original sem redispatch.
- **D-23:** A retirada do GTE exige soak PASS e drill produtivo Qwen -> GTE -> Qwen, com smokes em ambos, restore/replay, zero perda/duplicacao e snapshots retidos. So entao GTE e escalado a zero/removido.
- **D-24:** Cada wave termina em `59-WAVE-N-GATE.json` fail-closed. O gate exige hashes, prestate/poststate por readback, invariantes `PASS|FAIL`, receipts, aliases, leases, rollback target e `next_wave_allowed`; `UNKNOWN`, evidencia ausente ou metrica indisponivel nunca viram PASS.
- **D-27:** Graphify terá uma única autoridade de mutação: um publisher UDS root-owned de operações fixas (`publish-qwen`, `restore-gte`, `restore-qwen`, `heartbeat-current`). Publish/restore validam peer, journal, source realpath/hash e destinos exatos antes de temp-write/fsync/rename/parent-fsync/readback; `heartbeat-current` verifica os hashes fixos e executa apenas `utimensat`. O timer no-argv é client do publisher e não possui `ReadWritePaths` nem write permission sobre o serving tree. Usuário normal, executor, heartbeat client, hooks, sweeps e watchdog não podem alterar bytes diretamente.
- **D-28:** O reranker só pode ser construído a partir do lock graph transitivo integralmente auditado e instalado com `npm ci --ignore-scripts`. Origem mutável, integrity ausente, lifecycle child observado ou runtime CPU/offline incapaz de iniciar sem install scripts bloqueia e exige replanejamento.
- **D-29:** Heartbeat stale durante indisponibilidade do alias arbiter tenta apenas restart bounded da mesma identidade ativa e replay durável. Cold handoff exige journal replicado sem `INFLIGHT` ambíguo, alias-map exato e esta ordem: revogar a geração antiga, bloquear egress/socket/token do host antigo, provar negative probe, só então emitir nova geração e iniciar standby. Partition heal/rejoin do active antigo deve continuar negado. Estado limpo compensa automaticamente para GTE; ambiguidade mantém admission/writers drenados em `BLOCK`.

### the agent's Discretion

- Definir nomes finais de Deployments, Services, PVCs, Jobs e portas, preservando os aliases e collections locked.
- Escolher o limite de memoria final depois do warmup, sem alterar os `500m` de CPU ou admitir quatro rerankers.
- Escolher a implementacao exata do endpoint orquestrador no router, desde que a lease Redis cubra o ciclo completo e chamadas standalone permaneçam separadas.
- Manter nomes legados de scripts `qwen-canary-*` apenas se o nome nao alterar a semantica de cutover; novos manifests e namespace devem refletir producao.

### Deferred Ideas (OUT OF SCOPE)

- HPA para Qwen; o envelope 2–5 da Phase 59 é fixo/degradado/surge e não autoscaling.
- Qwen Reranker FP16 como fallback automatico.
- Qwen Reranker dentro do TEI sem suporte oficial.
- Contexto operacional de 32K ou batch interno maior que 1 antes de sizing.
- Remocao de snapshots/collections GTE no mesmo momento do retirement dos pods.

**Proveniência do bloco:** decisões, discretion e deferred ideas foram copiados integralmente do `59-CONTEXT.md`; são constraints autorizadas, não hipóteses desta pesquisa. [VERIFIED: `.planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-CONTEXT.md`]
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|---|---|---|
| QAI-01 | Qwen titular; GTE rollback-ready até retirement | Arquitetura de cutover, soak, drill e retirement fail-closed. [VERIFIED: `REQUIREMENTS.md`] |
| QAI-02 | ARM64, `500m` por pod, sem `hostNetwork`, alcance privado | Stack pinado, rollout 2+2, quota, Pod Security e validação de rede. [VERIFIED: `REQUIREMENTS.md`] |
| QAI-03 | No máximo dois pipelines completos com lease idempotente | State machine Redis persistente, CAS, TTL, cancel e restart recovery. [VERIFIED: `REQUIREMENTS.md`] |
| QAI-04 | Qdrant 1024d/Cosine separado de GTE 768d | Dual index, collections físicas locked, assinatura e Wave 0 de autoridade. [VERIFIED: `REQUIREMENTS.md`] |
| QAI-05 | Smokes funcionais, concorrência, cutover e rollback | Validation Architecture por wave e mapa de evidências. [VERIFIED: `REQUIREMENTS.md`] |
| QAI-06 | Avaliação pareada sem regressão acima dos limites congelados | Pooling A/B contra oracle, qrels congelados e cinco rounds warm-cache. [VERIFIED: `REQUIREMENTS.md`] |
| QAI-07 | Soak contínuo >=72h com auto-rollback | Job externo ao Horistic, UID original, hard-failure policy e evidência contínua. [VERIFIED: `REQUIREMENTS.md`] |
| QAI-08 | Rollback e restore/replay antes do retirement | Journal, CAS, compensação, drill Qwen->GTE->Qwen e snapshots retidos. [VERIFIED: `REQUIREMENTS.md`] |
</phase_requirements>

## Summary

A fase deve ser planejada como cutover controlado, não como canary com GTE titular permanente. Qwen entra em collections, aliases e rotas explicitamente separados, passa por validação funcional/qualidade/capacidade, torna-se titular na Wave 6, permanece titular durante soak contínuo de 72h e só depois do drill Qwen -> GTE -> Qwen autoriza o retirement do GTE. [VERIFIED: `59-CONTEXT.md`, `ROADMAP.md`, `STATE.md`]

O principal risco funcional é pooling drift. O modelo Qwen oficial usa instruction apenas na query, documentos sem instruction, last-token pooling, normalização L2 e até 1024 dimensões; o artifact INT8 locked `janni-t` declara mean pooling. Portanto `last-token` e `mean` devem ser comparados contra o oracle FP16 oficial na revision locked antes de escolher o contrato de produção. O benchmark Podman anterior com mean é evidência preliminar de execução/CPU, não gate de equivalência ou qualidade. [CITED: https://huggingface.co/Qwen/Qwen3-Embedding-0.6B] [CITED: https://huggingface.co/janni-t/qwen3-embedding-0.6b-int8-tei-onnx/commit/8fe0c238c7c48016d28e750413ca492024be3ddf] [VERIFIED: `scripts/embeddings-bench/results-2026-07-22-gte-qwen.md`]

O cutover atravessa duas autoridades independentes: banco do router para routing/model aliases e Qdrant para aliases de collections; Redis mantém a state machine e leases. Não existe atomicidade distribuída implícita entre esses sistemas. Use drain + zero leases + pausa de writers + journal durável + CAS/readback por autoridade e rollback compensatório automático. A localização, versão, auth, storage, backups, aliases e collections live do Qdrant estão `UNKNOWN` e bloqueiam qualquer mutação até a Wave 0 resolver a autoridade. [VERIFIED: `59-CONTEXT.md`] [CITED: https://qdrant.tech/documentation/manage-data/collections/] [CITED: https://redis.io/docs/latest/develop/using-commands/transactions/]

**Primary recommendation:** estruturar nove waves fail-closed: autoridade/freeze; artefatos/oracle/hardening; âncora GTE; rollout Qwen 2+2; pipeline Redis/router; dual index/eval; cutover; soak 72h; drill/retirement. Nenhuma wave consome resultado da seguinte e nenhum `UNKNOWN` pode ser convertido em PASS. [VERIFIED: `ROADMAP.md`, `59-CONTEXT.md`]

### Official-source refresh — 2026-07-23

- O card oficial Qwen continua declarando o modelo de embedding como `0.6B`, contexto 32K, dimensão nativa máxima 1024, MRL e instruction-aware; portanto 1024 é output nativo, não padding de 768. [CITED: https://huggingface.co/Qwen/Qwen3-Embedding-0.6B] [CITED: https://huggingface.co/Qwen/Qwen3-Embedding-0.6B-GGUF]
- A matriz oficial TEI 1.9 publica imagem CPU ARM64 e lista GTE/XLM-R classifiers como rerankers suportados, mas não Qwen3 CausalLM yes/no; isso sustenta TEI+ONNX para embedding e ONNX dedicado para reranking. [CITED: https://huggingface.co/docs/text-embeddings-inference/supported_models]
- A documentação ONNX Runtime define quantização de pesos/ativações em 8 bits e `CPUExecutionProvider` como provider CPU; a fase exige readback do provider real e não infere CPU-only apenas pela ausência de GPU. [CITED: https://onnxruntime.ai/docs/how-to/quantization.html] [CITED: https://huggingface.co/docs/optimum/v1.3.0/en/onnxruntime/modeling_ort]
- Qdrant confirma que as ações de aliases em uma única request são atômicas, mas não publica expected-generation CAS; por isso o plano usa hash exato do alias-map mais lock/fencing externo, não uma geração Qdrant fictícia. [CITED: https://qdrant.tech/documentation/manage-data/collections/]
- K3s documenta private registry/air-gap image loading; a execução deve escolher e provar uma dessas autoridades content-addressed antes do rollout, sem depender de cache local ou download do modelo em startup. [CITED: https://docs.k3s.io/installation/airgap]
- Redis Streams são append-only e adequados a replay/auditoria, enquanto Pub/Sub não preserva histórico; o soak usa stream persistente/fenced e watchdog independente. [CITED: https://redis.io/docs/latest/develop/data-types/] [CITED: https://redis.io/docs/latest/develop/use-cases/streaming/]
- `WAITAOF` existe desde Redis 7.2 e confirma fsync de todas as writes anteriores da mesma conexão no AOF local e/ou de replicas; timeout ainda retorna contadores que precisam ser comparados com o nível requerido. Dentro de Lua/MULTI ele não bloqueia. Portanto cada epoch de segurança usa write atomica e depois `WAITAOF 1 1 TIMEOUT` na mesma conexão, fora do script/transaction, antes do efeito externo. [CITED: https://redis.io/docs/latest/commands/waitaof/] A política `appendfsync everysec` isolada admite perda de aproximadamente um segundo e não substitui esse acknowledgement. [CITED: https://redis.io/docs/latest/operate/oss_and_stack/management/persistence/]
- O npm documenta que `--ignore-scripts` impede scripts de `package.json` durante install, embora o script explicitamente solicitado por `npm test` continue permitido sem pre/post hooks. O plano audita todo o lock graph, executa `npm ci --ignore-scripts`, observa zero lifecycle child e exige startup CPU/offline a partir dessa árvore; se isso não funcionar, a fase bloqueia em vez de liberar scripts implicitamente. [CITED: https://docs.npmjs.com/cli/v11/commands/npm-ci/]
- Qdrant oferece API key global e JWT RBAC, mas suas access classes não expressam todas as negações por operação exigidas aqui. A arquitetura não deve fingir que `manage` ou `rw` são least privilege suficiente: alias control-plane fica no alias arbiter, enquanto um data broker L7 separado segura a credential nativa e expõe somente create/configure, upsert/read e snapshot/read allowlisted para credentials temporárias distintas, sempre nas três collections Qwen. [CITED: https://qdrant.tech/documentation/operations/security/]

### Provenance Legend

- `[VERIFIED: ...]` — confirmado nesta sessão por leitura do repo, API/HEAD autoritativo ou seam de registry/legitimacy.
- `[CITED: URL]` — apoiado por documentação oficial primária.
- `[ASSUMED]` — recomendação de engenharia ainda sem prova local; exige confirmação antes de lock.
- `[UNKNOWN: ...]` — estado live ou decisão numérica deliberadamente não resolvida; bloqueia quando indicado.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|---|---|---|---|
| Auth, API pública e aliases de modelo | API / Backend — router | Router DB | O router é a borda pública; seu banco é a autoridade de routing e precisa de CAS/readback. [VERIFIED: `docs/operations/local-ai-embeddings.md`, `59-CONTEXT.md`] |
| Pipeline state machine e duas leases | API / Backend — governor | Redis | Redis já é o estado persistente locked; a lease cobre todo o ciclo. [VERIFIED: `59-CONTEXT.md`] |
| Embedding INT8 1024d | k3s inference worker | TEI Service privado | TEI/OrtBackend serve o artifact locked em dois pods. [VERIFIED: `59-CONTEXT.md`] |
| Vector search e dual index | Database / Storage — Qdrant | Writers por corpus | Qdrant serve collections/aliases; o corpus-fonte, IDs e high-water marks medem paridade. [VERIFIED: `59-CONTEXT.md`] |
| Rerank CausalLM INT8 | k3s inference worker | Router adapter | Serviço ONNX dedicado implementa prompt e logits yes/no; TEI não é o runtime deste CausalLM. [CITED: https://huggingface.co/Qwen/Qwen3-Reranker-0.6B] [CITED: https://huggingface.co/docs/text-embeddings-inference/supported_models] |
| Scheduling, quota e network isolation | k3s control plane | CNI/firewall | Kubernetes governa recursos e endpoints; NetworkPolicy só vale se houver enforcement comprovado. [CITED: https://kubernetes.io/docs/concepts/configuration/manage-resources-containers/] [CITED: https://kubernetes.io/docs/concepts/services-networking/network-policies/] |
| Cutover, journal e compensação | Router cutover coordinator | Router DB + Qdrant + Redis | Coordena autoridades sem alegar transação global; cada passo tem receipt, CAS e inverse operation. [VERIFIED: `59-CONTEXT.md`] |
| Soak e retirement | Runner externo | k3s/router/Qdrant observability | O Job não disputa CPU no Horistic e só autoriza retirement após 72h + drill. [VERIFIED: `59-CONTEXT.md`] |

## Project Constraints (from AGENTS.md)

- Usar PT-BR com Giovanni e manter termos técnicos comuns em English. [VERIFIED: `AGENTS.md`]
- Cada pod k3s normal deve declarar `requests.cpu=500m` e `limits.cpu=500m`; pods multi-container dividem o total sem ultrapassar `500m`. [VERIFIED: `AGENTS.md`]
- Builds, compiles, container builds, broad indexers e suites pesadas devem usar o profile `builds`, limitado a 20% da CPU total; se não houver contenção verificável, parar. [VERIFIED: `AGENTS.md`, `modules/srv1-ops/configs/resource-governor.env`]
- Vault é a fonte autoritativa de secrets; valores não entram em Git, `.planning`, logs, chat, Obsidian ou GBrain. [VERIFIED: `AGENTS.md`]
- Preservar worktrees sujos e mudanças concorrentes; router owner checkout exige inventário e writer serialization. [VERIFIED: `AGENTS.md`, `59-CONTEXT.md`]
- Graphify deve estar fresh antes de planejamento e ser consultado antes de escolher paths; nesta pesquisa estava fresh, sem resultados para os termos da fase. [VERIFIED: `AGENTS.md`, Graphify status/query 2026-07-23]
- Browser automation, se necessária em execução futura, deve ser headless e reter evidência. [VERIFIED: `AGENTS.md`]
- Esta pesquisa não autoriza build, teste ou operação live; somente `59-RESEARCH.md` pode ser alterado. [VERIFIED: instrução do operador em 2026-07-23]

## Standard Stack

### Core

| Component | Version / immutable identity | Purpose | Directive |
|---|---|---|---|
| TEI CPU ARM64 | `1.9.3`; `ghcr.io/huggingface/text-embeddings-inference@sha256:16c0a827cf79d5dc9b9ec1b0b5df7ffd165726f9bdf1daa9d4f7a355dd842f7e` | Embedding OrtBackend/ONNX em ARM64 | Usar o digest exato; tags `latest` bloqueiam promoção. [VERIFIED: `k8s/ebeddings-local/tei-gte-reranker.yaml`, `inventory/hosts/horistic-srv.yaml`] [CITED: https://github.com/huggingface/text-embeddings-inference/releases/tag/v1.9.3] |
| Qwen embedding INT8 | `janni-t/qwen3-embedding-0.6b-int8-tei-onnx@8fe0c238c7c48016d28e750413ca492024be3ddf`; `model.onnx` 599,154,560 bytes; SHA-256 `bd775071a80a1dde99a18d1a7083bf388a5ad4ce9db6d81806f25c4d6102ff08` | Candidate 1024d | Verificar bytes antes do startup; pooling vem do gate A/B, não do card comunitário sozinho. [VERIFIED: Hugging Face model API/HEAD] |
| Qwen embedding oracle FP16 | `Qwen/Qwen3-Embedding-0.6B@97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3` | Referência normativa de pooling/instruction/ranking | Executar fora do Horistic; last-token + query instruction + documents sem instruction + L2 + 1024d. [VERIFIED: Hugging Face model API] [CITED: https://huggingface.co/Qwen/Qwen3-Embedding-0.6B] |
| Qwen reranker INT8 | `onnx-community/Qwen3-Reranker-0.6B-ONNX@9995c50e2310679108a55f5ccd16ba8be9f17c20`; `onnx/model_quantized.onnx` 1,219,344,796 bytes; SHA-256 `c9428382bb48bb31e01a6034647c86d6270761781735cafbf6d5cb4a396d0450` | Dedicated CausalLM yes/no reranker | Embed/pin no image ou fetch checksumado; nunca usar `main`. [VERIFIED: Hugging Face model API/HEAD] |
| `@huggingface/transformers` | `4.2.0`, registry modified 2026-04-22 | Tokenizer, AutoModelForCausalLM e ORT binding do serviço Node | Pin exato + lockfile; sem runtime package download. [VERIFIED: npm registry + package-legitimacy seam + official ONNX model card] |
| k3s | inventário `v1.35.5+k3s1`, ARM64 worker | Deployments, Services, quota, policies, probes | Revalidar versão/topologia na Wave 0; o inventário não substitui readback live. [VERIFIED: `inventory/hosts/horistic-srv.yaml`] [UNKNOWN: estado live não consultado por ordem do operador] |
| Redis existente | versão/topologia `UNKNOWN`; mínimo aceito `>=7.2` | Pipeline state machine, queue, TTL, leases, arbiter journal e soak stream | Wave 0 deve provar AOF no primary e replica em failure domain independente, mesma-conexão `WAITAOF 1 1`, ownership e failover sem registrar secrets. Qualquer topologia menor bloqueia. [VERIFIED: `59-CONTEXT.md`] [CITED: https://redis.io/docs/latest/commands/waitaof/] [UNKNOWN: versão/topologia live] |
| Qdrant | autoridade/versão/topologia `UNKNOWN` | Collections 1024d, aliases, snapshots e busca top-20 | Qualquer mutação é bloqueada até Wave 0 resolver endpoint, auth, storage, backups, aliases e collections. [VERIFIED: `59-CONTEXT.md`] [UNKNOWN: autoridade live] |

### Supporting

| Component | Purpose | When to Use |
|---|---|---|
| Router DB | Autoridade de routing/channel/model alias | CAS precondition + backup + independent readback no cutover. [VERIFIED: `59-CONTEXT.md`] |
| `ResourceQuota` + `LimitRange` | Teto agregado e defaults do namespace | Em todos os manifests Qwen; não substitui allocatable nem governor. [CITED: https://kubernetes.io/docs/concepts/policy/resource-quotas/] |
| Pod Security `restricted` controls | Non-root, sem privilege escalation, seccomp e capabilities mínimas | Antes do primeiro rollout; exceptions precisam de evidência e scope mínimo. [CITED: https://kubernetes.io/docs/concepts/security/pod-security-standards/] |
| NetworkPolicy + firewall/NodePort private path | Impedir bypass do router/governor | Só marcar PASS após probe positivo do router e negativo de origem não autorizada/pública. [CITED: https://kubernetes.io/docs/concepts/services-networking/network-policies/] |
| Prometheus/cgroup/container metrics | CPU, RSS, queue, TTL, restart e latency | Obrigatório porque Metrics API está ausente; indisponibilidade vira FAIL/UNKNOWN. [VERIFIED: `59-CONTEXT.md`] |
| Qdrant atomic alias actions | Switch de collection por corpus | Dentro do Qdrant; exportar aliases separadamente porque snapshots não os incluem. [CITED: https://qdrant.tech/documentation/manage-data/collections/] [CITED: https://qdrant.tech/documentation/snapshots/] |

### Alternatives Considered

| Instead of | Alternative | Disposition |
|---|---|---|
| TEI embedding locked | ONNX service paralelo | Fora de escopo por D-02. [VERIFIED: `59-CONTEXT.md`] |
| Dedicated reranker ONNX | TEI Qwen reranker | Fora de escopo: lista oficial TEI 1.9 não inclui Qwen3 CausalLM entre rerankers suportados. [CITED: https://huggingface.co/docs/text-embeddings-inference/supported_models] |
| Fixed 2 rerankers | HPA 2-4 | Deferred; Metrics API ausente e sizing ainda não existe. [VERIFIED: `59-CONTEXT.md`] |
| 1024d collections separadas | Reusar/pad GTE 768d | Proibido por D-14. [VERIFIED: `59-CONTEXT.md`] |

**Installation for the dedicated service (plan-time command, not executed in research):**

```bash
npm install --save-exact @huggingface/transformers@4.2.0
npm ci --ignore-scripts
```

[VERIFIED: `services/qwen-reranker-onnx/package.json`, npm registry]

## Package Legitimacy Audit

| Package | Registry | Publish/Downloads | Source Repo | Postinstall | Verdict | Disposition |
|---|---|---|---|---|---|---|
| `@huggingface/transformers@4.2.0` | npm | modified 2026-04-22; 1,710,997 downloads/week at audit | `github.com/huggingface/transformers.js` | direct package: none; transitive graph not yet proven | CONDITIONAL | Exact pin alone is insufficient. Wave 1 audits every transitive node/origin/integrity/lifecycle/native artifact, installs with `npm ci --ignore-scripts`, proves zero lifecycle child and CPU/offline startup. [VERIFIED: npm registry + package-legitimacy seam + official model card] [CITED: https://docs.npmjs.com/cli/v11/commands/npm-ci/] |

**Packages removed due to SLOP:** none. [VERIFIED: package-legitimacy seam]
**Packages flagged SUS:** none. [VERIFIED: package-legitimacy seam]

## Architecture Patterns

### System Architecture Diagram

```text
Authenticated client / corpus writer
                |
                v
router-ai-atius /v1
  auth + model allowlist + Router DB authority
                |
                +--> embedding-only admission (separate class)
                |
                +--> Redis acquire pipeline_id (global max = 2)
                        state=QUEUED, TTL, journal pointer
                              |
                              v
                 Qwen TEI Service (2 x 500m)
                 instruction on query only
                 selected pooling + L2 + 1024d
                              |
                              v
                 Qdrant stable corpus alias
                 -> *_qwen3_1024_v1 (top-20)
                              |
                              v
                 Qwen ONNX Reranker Service
                 rollout 1 -> 2 pods, each 500m
                 batch=1, context=512, <=20 docs sequential
                              |
                              v
                 terminal Redis CAS + response

Dual-index writers:
  frozen corpus/source -> GTE 768d physical index
                       -> Qwen 1024d physical index
                       -> durable journal/high-water/checksum

Cutover coordinator:
  drain admission -> zero leases -> pause writers -> flush/replay journal
  -> Router DB CAS -> Qdrant atomic alias actions -> independent readback
  -> resume writers/admission
  any failure -> inverse Qdrant actions + Router DB compensating CAS + readback

GTE runtime and 768d collections remain immutable/rollback-ready through
Qwen titular cutover + 72h soak + productive Qwen->GTE->Qwen drill.
```

[VERIFIED: `59-CONTEXT.md`, `ROADMAP.md`]

### Recommended Project Structure

```text
k8s/qwen-production/
├── namespace-resources.yaml
├── tei-qwen3-embedding.yaml
├── qwen3-reranker.yaml
├── services.yaml
├── network-policy.yaml
└── kustomization.yaml

services/qwen-reranker-onnx/
├── server.mjs
├── server.test.mjs
├── package.json
├── package-lock.json
└── Containerfile

scripts/embeddings-bench/
├── qwen-cutover-inventory.py
├── qwen-pooling-oracle.py
├── qwen-functional-smoke.py
├── qdrant-qwen-cutover.py
├── evaluate-rag-quality.py
├── qwen-cutover.py
└── qwen-soak.py
```

Nomes `qwen-canary-*` podem permanecer apenas em scripts legados se o conteúdo e gates não preservarem semântica de canary/GTE titular; manifests e namespace novos devem refletir produção. [VERIFIED: `59-CONTEXT.md`] O nome exato do namespace é discretion e deve ser congelado na Wave 0, sem reutilizar `qwen-canary` como default implícito. [ASSUMED]

### Identity and Alias Contract

| Identity surface | GTE rollback identity | Qwen production identity | Rule |
|---|---|---|---|
| Embedding model alias | `embedding-gte-v1` | `embedding-qwen3-0.6b-int8-1024-v1` | São identidades distintas; nunca remapear o nome GTE para o backend Qwen. [VERIFIED: `59-CONTEXT.md`] |
| Reranker model alias | `reranker-gte-multilingual-v1` | `reranker-qwen3-0.6b-int8-v1` | São identidades distintas; router converte o contrato público para `/rerank` privado. [VERIFIED: `59-CONTEXT.md`, `docs/operations/local-ai-embeddings.md`] |
| Physical Qdrant collections | GTE 768d atuais, nomes live `UNKNOWN` | `gbrain_qwen3_1024_v1`, `obsidian_qwen3_1024_v1`, `graphify_qwen3_1024_v1` | Nunca compartilhar/pad vector space; Qwen usa 1024d/Cosine. [VERIFIED: `59-CONTEXT.md`] [UNKNOWN: physical GTE names live] |
| Stable corpus aliases | mapa live `UNKNOWN` | mesmos aliases de corpus apontando para Qwen após cutover | Wave 0 exporta nomes/mapeamentos; o cutover troca target, não inventa alias. [VERIFIED: `59-CONTEXT.md`] [UNKNOWN: alias map live] |

### Pattern 1: Embedding contract selected by oracle

Defina dois candidatos sobre o mesmo artifact INT8: `last-token` e `mean`. Compare ambos ao oracle FP16 `97b0c614...` com o mesmo corpus, tokenizer revision, max length, query instruction, documentos sem instruction, 1024d e normalização L2. [VERIFIED: `59-CONTEXT.md`] [CITED: https://huggingface.co/Qwen/Qwen3-Embedding-0.6B]

O gate deve separar quatro classes: shape/norm; single-vs-batch cosine `>=0.9999`; equivalência INT8-vs-FP16 sob thresholds congelados; ranking/retrieval. O pooling vencedor torna-se parte da assinatura imutável e qualquer mudança exige nova collection/reindex. [VERIFIED: `59-CONTEXT.md`] [ASSUMED: estrutura de assinatura]

### Pattern 2: Persistent pipeline state machine

Use Redis para `QUEUED -> EMBEDDING -> VECTOR_SEARCH -> RERANK -> COMPLETED`, com `FAILED|CANCELLED|EXPIRED` terminais. Cada transition inclui `pipeline_id`, expected state/version, timestamps, deadline, aliases, corpus e journal offset; CAS rejeita transition stale. [VERIFIED: `59-CONTEXT.md`] [CITED: https://redis.io/docs/latest/develop/using-commands/transactions/]

Invariantes obrigatórios:

- no máximo dois pipelines não terminais globalmente; continuations precedem novos ciclos; [VERIFIED: `59-CONTEXT.md`]
- lease permanece ocupada durante vector search e rerank; [VERIFIED: `59-CONTEXT.md`]
- sucesso, erro, cancel, expiry e restart convergem por terminal transition idempotente; [VERIFIED: `59-CONTEXT.md`]
- TTL é deadline de negócio, não apenas desaparecimento silencioso da key; um sweeper registra `EXPIRED`/receipt antes da limpeza; [ASSUMED]
- embedding standalone usa namespace/limiter separado e não consome os dois pipeline slots. [VERIFIED: `59-CONTEXT.md`]

Redis transactions não oferecem rollback; falha após `EXEC` exige idempotência/compensação. `WATCH` + `MULTI/EXEC` oferece CAS otimista e expiry também pode invalidar a watched key. [CITED: https://redis.io/docs/latest/develop/using-commands/transactions/] [CITED: https://redis.io/docs/latest/commands/expire/]

Para qualquer transition que autorize um efeito externo, a escrita atômica deve terminar e então, na mesma conexão, executar `WAITAOF 1 1 TIMEOUT`; somente retorno local `>=1` e replicas `>=1` torna o epoch acionável. O comando deve ficar fora de Lua/MULTI, porque nesse contexto não bloqueia, e a promoção após failover só pode consumir um offset que a replica promovida confirmou ter fsynced. Fixtures cobrem perda do processo, primary e failure domain independente antes/depois do acknowledgement. [CITED: https://redis.io/docs/latest/commands/waitaof/]

### Pattern 3: Correct dedicated reranker

O protótipo atual usa padding default, trunca o prompt completo, lê sempre `sequenceLength-1`, mantém Promise queue ilimitada, aceita `/v1/rerank`, não propaga cancel/TTL e não faz graceful drain; ele precisa ser hardened antes do rollout. [VERIFIED: `services/qwen-reranker-onnx/server.mjs`]

Contrato obrigatório:

- `padding_side=left`; score nos logits da última posição que contém o suffix; [CITED: https://huggingface.co/Qwen/Qwen3-Reranker-0.6B]
- tokenizar body sem padding, reservar `prefix_tokens + suffix_tokens`, aplicar truncation budget ao body e anexar o suffix depois; [CITED: https://huggingface.co/Qwen/Qwen3-Reranker-0.6B]
- calcular probabilidade estável sobre logits `yes`/`no`; [CITED: https://huggingface.co/Qwen/Qwen3-Reranker-0.6B]
- envelope inicial fixo: batch interno 1, contexto total 512 e até 20 documentos processados sequencialmente; [VERIFIED: `59-CONTEXT.md`]
- fila explícita limitada; recomendação inicial de no máximo um item aguardando por pod, com concurrency 1 e `429` quando cheia; [ASSUMED]
- deadline/TTL e disconnect abortam item queued; inferência não cancelável deve descartar resposta e liberar estado exatamente uma vez; [ASSUMED]
- logs/metrics contêm IDs opacos, counts, timing, outcome e resource usage, nunca query/document/raw logits; [VERIFIED: `AGENTS.md`] [ASSUMED: schema]
- shutdown: readiness false, stop admission, bounded drain, cancel queued, flush metrics e exit. [ASSUMED]

### Pattern 4: Dual index with journal and high-water marks

Use o mesmo corpus-fonte congelado, chunking version, logical IDs e checksums para GTE 768d e Qwen 1024d. Cada write recebe sequence/idempotency key; o journal registra target GTE, target Qwen, status por target e high-water mark. Paridade é `source_count/checksum/high_water`, não igualdade com índice legado possivelmente incompleto. [VERIFIED: `59-CONTEXT.md`]

Antes do cutover, pause writers, espere zero in-flight writes, replay até ambos os targets atingirem o mesmo high-water, verifique zero gaps/duplicates e só então altere routing/aliases. Depois, retome writers na rota Qwen e mantenha o journal até concluir soak/drill. [VERIFIED: `59-CONTEXT.md`]

### Pattern 5: Journaled multi-authority cutover

O switch de aliases Qdrant é atômico dentro de uma chamada multi-action, mas não é atômico junto com Router DB. Modele o cutover como saga curta com prestate hash, expected DB version, alias export, ordered steps, receipts e inverse operations. [CITED: https://qdrant.tech/documentation/manage-data/collections/] [VERIFIED: `59-CONTEXT.md`]

Ordem prescritiva:

1. drain de nova admission e readback; [VERIFIED: `59-CONTEXT.md`]
2. zero leases e zero writers; [VERIFIED: `59-CONTEXT.md`]
3. journal/high-water reconciliado; [VERIFIED: `59-CONTEXT.md`]
4. backup/export do Router DB e aliases Qdrant; [VERIFIED: `59-CONTEXT.md`]
5. CAS do Router DB para aliases Qwen; [VERIFIED: `59-CONTEXT.md`]
6. multi-action aliases Qdrant por corpus; [CITED: https://qdrant.tech/documentation/manage-data/collections/]
7. readback independente dos dois sistemas + smokes; [VERIFIED: `59-CONTEXT.md`]
8. resume writers/admission; qualquer falha executa inverse actions, CAS compensatório e novo readback. [VERIFIED: `59-CONTEXT.md`]

Aliases Qdrant são sempre enviados pelo único arbiter. Em heartbeat stale com o arbiter indisponível, rollback primeiro reinicia de forma bounded a mesma identidade ativa e reproduz apenas journal duravelmente reconhecido. Cold handoff só é permitido depois de provar zero `INFLIGHT` ambíguo e reconciliar o alias-map exato; estado limpo executa compensação automática para GTE, e ambiguidade mantém admission/writers drenados em `BLOCK`. [VERIFIED: `59-CONTEXT.md`] [CITED: https://qdrant.tech/documentation/manage-data/collections/]

### Anti-Patterns to Avoid

- **Canary sem cutover:** contradiz autorização e deixa GTE titular; Qwen deve tornar-se titular na Wave 6. [VERIFIED: `STATE.md`, `ROADMAP.md`]
- **Remap silencioso de alias GTE:** quebra identidade e rollback; aliases Qwen e GTE permanecem distintos. [VERIFIED: `59-CONTEXT.md`]
- **Mean por conveniência:** card comunitário não substitui oracle oficial; pooling vem do A/B. [CITED: https://huggingface.co/janni-t/qwen3-embedding-0.6b-int8-tei-onnx/commit/8fe0c238c7c48016d28e750413ca492024be3ddf] [CITED: https://huggingface.co/Qwen/Qwen3-Embedding-0.6B]
- **“Atomic cutover” sem journal:** Qdrant e Router DB não compartilham transaction; compensação/readback são obrigatórios. [VERIFIED: `59-CONTEXT.md`]
- **HPA sem Metrics API:** resource HPA depende de `metrics.k8s.io`; nesta fase use replicas fixas 2+2. [CITED: https://kubernetes.io/docs/concepts/workloads/autoscaling/horizontal-pod-autoscale/] [VERIFIED: `59-CONTEXT.md`]
- **Job no Horistic durante 2+2:** GTE atual 1500m + Qwen final 2000m = 3500m; um Job 500m consumiria o allocatable declarado de 4000m sem headroom operacional. [VERIFIED: manifests GTE + `59-CONTEXT.md`]

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---|---|---|---|
| Embedding inference | Segundo servidor ONNX | TEI 1.9.3 OrtBackend + artifact locked | Runtime e pins já estão decididos. [VERIFIED: `59-CONTEXT.md`] |
| Reranker em TEI | Conversão fictícia para classifier | Dedicated ONNX CausalLM service | Modelo oficial pontua logits yes/no e TEI não lista Qwen3 entre rerankers. [CITED: https://huggingface.co/Qwen/Qwen3-Reranker-0.6B] [CITED: https://huggingface.co/docs/text-embeddings-inference/supported_models] |
| Vector DB | ANN/index custom | Qdrant collections + aliases | Schema fixa dimensão/métrica e alias switch é atômico no Qdrant. [CITED: https://qdrant.tech/documentation/manage-data/collections/] |
| Global lock | Mutex in-process | Redis CAS/state machine | Restart/múltiplas réplicas não preservam mutex local. [VERIFIED: `59-CONTEXT.md`] |
| Distributed transaction | “All-or-nothing” ad hoc | Journal + CAS + compensating rollback | Redis não faz transaction rollback e Qdrant/DB são autoridades independentes. [CITED: https://redis.io/docs/latest/develop/using-commands/transactions/] |
| Autoscaling | HPA sem métricas | Replicas fixas 2+2 | HPA está deferred e Metrics API ausente. [VERIFIED: `59-CONTEXT.md`] |
| Secret distribution | Inline env/YAML | Vault hydration + K8s Secret references | Project contract proíbe persistir valores. [VERIFIED: `AGENTS.md`] |

**Key insight:** complexidade desta fase está em identidade e transição de estado — pooling, vector space, authority, leases, writer journal e rollback — não em criar mais runtimes. [VERIFIED: síntese de `59-CONTEXT.md` e código local]

## Runtime State Inventory

| Category | Items Found | Action Required |
|---|---|---|
| Stored data | Router DB contém channels/routing e é autoridade; Redis existente será autoridade da pipeline; Qdrant contém índices/aliases, mas endpoint/version/auth/storage/collections live estão `UNKNOWN`. [VERIFIED: `59-CONTEXT.md`] [UNKNOWN: Qdrant live] | Backup + CAS do Router DB; schema/migration Redis; inventário read-only Qdrant; dual reindex 1024d; export de aliases e snapshots antes de mutar. Data migration e code edit são tarefas separadas. |
| Live service config | k3s manifests versionam GTE 1 embedding + 2 reranker; HPA GTE 2-4 existe no repo; router channel config vive no DB; Graphify repo config ainda aponta `embedding-gte-v1`/768. [VERIFIED: manifests, `.planning/config.json`] | Wave 0 faz readback live 2–4 sem mutar; Wave 2 altera/aplica/lê source, live e recovery 2–2 antes do anchor; Graphify/GBrain/Obsidian mudam somente no cutover/drill conforme wave. |
| OS-registered state | Inventário registra Horistic ARM64/k3s agent; objetos k3s live, PM2/Podman/router registrations e NodePorts atuais não foram consultados. [VERIFIED: `inventory/hosts/horistic-srv.yaml`] [UNKNOWN: registrations live] | Inventariar Deployments/HPA/Services/NodePorts/node labels/taints e router process manager sem mutação; selecionar branch de rede aplicável. |
| Secrets/env vars | Vault é autoridade; nomes/paths exatos de Qdrant, Redis, router e Hugging Face credentials necessários pela fase não foram inventariados. [VERIFIED: `AGENTS.md`] [UNKNOWN: env/key names live] | Wave 0 registra somente profile/path/variable names, nunca valores; provar hydration e least privilege antes de rollout. |
| Build artifacts / installed packages | Artifact cache Podman do benchmark foi preservado; images, registry manifests, lockfile do reranker e model files finais ainda não são artefatos promovíveis. [VERIFIED: benchmark e package.json] | Rebuild/fetch reproduzível sob profile `builds`, verify ARM64/digests/hashes, gerar SBOM/lockfile; não reutilizar cache como evidência de supply chain. |

**Canonical migration question:** depois de editar o repo, Router DB, Redis, aliases/collections Qdrant, objects k3s, Graphify config, writer checkpoints, image registry e caches ainda podem carregar GTE ou o alias antigo; cada item exige readback explícito. [VERIFIED: síntese dos authorities locked]

## Common Pitfalls

### Pitfall 1: Pooling passes shape but fails semantics

**What goes wrong:** mean e last-token retornam 1024 floats normalizados, mas produzem vector spaces/ranking diferentes. [CITED: official Qwen card + janni artifact card]

**How to avoid:** A/B contra oracle FP16 locked, corpus/qrels congelados e assinatura incluindo pooling. [VERIFIED: `59-CONTEXT.md`]

**Warning signs:** shape/norm PASS com ranking/oracle FAIL ou threshold alterado após ver resultados. [ASSUMED]

### Pitfall 2: Suffix lost by truncation

**What goes wrong:** tokenizar prompt completo com `truncation:true` pode remover o suffix que posiciona o logit yes/no; o protótipo faz exatamente isso. [VERIFIED: `server.mjs`]

**How to avoid:** reservar budget para prefix/suffix, truncar apenas o body e anexar suffix depois; left-pad o batch. [CITED: https://huggingface.co/Qwen/Qwen3-Reranker-0.6B]

**Warning signs:** single/batch score diverge, score lê pad token ou long documents colapsam ranking. [ASSUMED]

### Pitfall 3: Queue duplicated in every layer

**What goes wrong:** router Redis e backend unbounded queue acumulam trabalhos já expirados/cancelados. [VERIFIED: `server.mjs`, `59-CONTEXT.md`]

**How to avoid:** Redis é a backlog authority; backend tem concurrency 1, queue curta, TTL/cancel e overload rejection. [ASSUMED]

**Warning signs:** queue depth backend cresce com leases Redis estáveis ou requests continuam após disconnect. [ASSUMED]

### Pitfall 4: False atomic cutover

**What goes wrong:** Router DB muda e Qdrant falha, deixando modelo/collection incompatíveis. [VERIFIED: `59-CONTEXT.md`]

**How to avoid:** drain, journal, expected versions, ordered receipts, readback e compensation automática. [VERIFIED: `59-CONTEXT.md`]

**Warning signs:** script usa updates sequenciais sem prestate hash/inverse operation. [ASSUMED]

### Pitfall 5: Snapshot treated as alias backup

**What goes wrong:** Qdrant collection snapshot não inclui aliases. [CITED: https://qdrant.tech/documentation/snapshots/]

**How to avoid:** export/version/hash aliases separadamente e exercitar restore + alias recreation. [CITED: https://qdrant.tech/documentation/snapshots/]

**Warning signs:** rollback artifact contém `.snapshot`, mas nenhum alias map. [ASSUMED]

### Pitfall 6: Metrics unavailable becomes PASS

**What goes wrong:** `kubectl top`/Metrics API ausente e gate ignora CPU/RSS. [VERIFIED: `59-CONTEXT.md`]

**How to avoid:** Prometheus/cgroup/container metrics com provenance; ausência é FAIL/UNKNOWN. [VERIFIED: `59-CONTEXT.md`]

**Warning signs:** HPA current metrics `<unknown>` ou evidence JSON sem source/timestamps. [ASSUMED]

### Pitfall 7: Retirement before productive drill

**What goes wrong:** GTE é removido após soak, mas rollback nunca foi exercitado com writers/restore/replay. [VERIFIED: `59-CONTEXT.md`]

**How to avoid:** drill Qwen->GTE->Qwen, smokes em ambos, zero loss/duplicate, snapshots retidos; só então scale-to-zero/remove. [VERIFIED: `59-CONTEXT.md`]

**Warning signs:** retirement gate depende apenas de uptime/latency. [ASSUMED]

## Code Examples

### Attention-aware last-token + L2

```python
# Adapted from the official Qwen3 Embedding model card.
def qwen_embedding(hidden, attention_mask):
    if attention_mask[:, -1].all():
        pooled = hidden[:, -1]
    else:
        last = attention_mask.sum(axis=1) - 1
        pooled = hidden[range(len(last)), last]
    return l2_normalize(pooled, axis=1)
```

[CITED: https://huggingface.co/Qwen/Qwen3-Embedding-0.6B]

### Suffix-preserving reranker tokenization

```javascript
// Adapted from the official Qwen3 Reranker recipe.
const bodyBudget = maxLength - prefixIds.length - suffixIds.length;
const bodyIds = tokenizer.encode(body, {
  add_special_tokens: false,
  truncation: true,
  max_length: bodyBudget,
});
const inputIds = [...prefixIds, ...bodyIds, ...suffixIds];
// Pad the batch on the left, then read yes/no logits at the final position.
```

[CITED: https://huggingface.co/Qwen/Qwen3-Reranker-0.6B]

### Redis transition CAS

```text
WATCH pipeline:{id}
read state, version, deadline
reject if terminal | stale version | expired
MULTI
HSET pipeline:{id} state=<next> version=<version+1> updated_at=<now>
ZADD active-pipelines <deadline> <id>
EXEC
retry only on null EXEC; terminal release is idempotent
```

[CITED: https://redis.io/docs/latest/develop/using-commands/transactions/] [ASSUMED: exact key schema]

### Compensating cutover journal

```json
{
  "cutover_id": "opaque-id",
  "prestate_hash": "sha256:...",
  "router_db": {"expected_version": 17, "before": "gte", "after": "qwen"},
  "qdrant_aliases": {"before_hash": "sha256:...", "after_hash": "sha256:..."},
  "steps": [],
  "rollback_steps": [],
  "status": "PREPARED"
}
```

[ASSUMED: schema] [VERIFIED: required behavior from `59-CONTEXT.md`]

## State of the Art

| Old/local approach | Phase 59 target | Impact |
|---|---|---|
| GTE embedding 768d/CLS, 1 pod; GTE reranker 2 pods with HPA object | Qwen embedding 1024d selected by oracle, 2 pods; Qwen reranker fixed 2 pods after 1->2 rollout | Runtime Qwen final = 2000m; incumbent current = 1500m; HPA Qwen absent. [VERIFIED: manifests + `59-CONTEXT.md`] |
| Qwen Podman mean benchmark | k3s production cutover with last-token-vs-mean gate | Benchmark antigo não seleciona pooling nem prova retrieval quality. [VERIFIED: benchmark + `59-CONTEXT.md`] |
| Per-call governor behavior | Redis persistent cycle-wide state machine with two slots | Lease cobre embedding, vector search e rerank, inclusive restart/TTL/cancel. [VERIFIED: `59-CONTEXT.md`] |
| Canary/GTE titular | Qwen titular na Wave 6, GTE rollback-ready até Wave 8 | Semântica antiga está invalidada. [VERIFIED: `STATE.md`, `ROADMAP.md`] |
| Alias switch isolado | DB CAS + Qdrant atomic aliases + journal/compensation | Evita declarar transação distribuída inexistente. [VERIFIED: `59-CONTEXT.md`] |

**Deprecated/outdated:**

- Recomendações anteriores de manter o titular inalterado, usar target canary e registrar promoção como não executada contradizem o contexto reconciliado e não devem aparecer nos novos planos. [VERIFIED: diff semântico entre RESEARCH anterior e `59-CONTEXT.md`/`STATE.md`]
- HPA para Qwen permanece deferred; não criar HPA desabilitado como “preparação”. O máximo cinco da Phase 59 é surge serializado e quota-bound. [VERIFIED: `59-CONTEXT.md`]

## Execution Contract Assumptions

| # | Contract choice | Owner / wave | Evidence and release gate | Fail-closed criterion |
|---|---|---|---|---|
| A1 | Namespace de produção não usa naming canary. | Plan 59-04 / Wave 3 | rendered manifests, server dry-run, `59-QWEN-ROLLOUT.json`, Gate 3 | Any canary-only or non-production identity blocks rollout. |
| A2 | Reranker starts with concurrency 1 and bounded queue. | Plan 59-02 Task 2 / Wave 1; sized in Wave 3 | reranker fixtures, `59-RERANKER-HARDENING.json`, one-pod metrics, Gates 1/3 | Queue/concurrency not bounded or metrics unavailable blocks scale to pod 2. |
| A3 | TTL writes a terminal receipt before key cleanup, and every safety epoch is fsynced locally plus on one independent replica before an external effect. | Plan 59-05 Task 2 / Wave 4 | race/restart/primary-host-loss fixtures, same-connection `WAITAOF 1 1` readback, `59-ROUTER-LIFECYCLE.json`, Gate 4 | Missing/double terminal, short acknowledgement, wrong connection or promotion from an unacknowledged offset blocks activation. |
| A4 | Journal carries sequence/idempotency/target status. | Plans 59-06/07 / Waves 5–6 | PREPARED/committed `59-CUTOVER-JOURNAL.json`, fault fixtures, Gates 5/6 | Missing ordered or inverse operation blocks cutover. |
| A5 | Cutover schema may add inventoried fields without weakening compensation. | Plan 59-07 / Wave 6 | current authority generations, all-boundary fault evidence, Gate 6 | Any authority not generation-bound/read back/compensable blocks mutation. |
| A6 | Operational logs contain opaque IDs/counts/timings only. | Plans 59-02/05 / Waves 1/4 | redaction fixtures and active-log scan in Gates 1/4 | Query/document/prompt/token/raw-log finding blocks release. |

## Open Questions (RESOLVED BY EXECUTION CONTRACT)

Runtime values may legitimately be `UNKNOWN` before their owning task executes. They are not planning uncertainty: every value below has an owner, evidence artifact, release gate and explicit blocking rule.

1. **Qdrant live authority**

   Owner: Plan 59-01 Task 2, Wave 0. Evidence: `59-AUTHORITY-INVENTORY.json` and `59-GTE-PRESTATE.json`, independently read back and sealed by `59-WAVE-0-GATE.json`. Required fields: endpoint, version, auth mode, storage, backup/snapshot capability, topology, aliases, GTE collections and writer ownership. Fail closed: any missing, stale, conflicting or `UNKNOWN` field blocks all Qdrant mutation and Wave 1.

2. **INT8 pooling winner**

   Owner: Plan 59-02 Task 1, Wave 1. Evidence: Wave 0 frozen thresholds, `59-ARTIFACT-LOCK.json`, blinded `59-POOLING-ORACLE.json` and Gate 1. Last-token remains the normative preference; mean may win only when last-token fails and mean passes every frozen functional/instruction/ranking criterion. Fail closed: neither/both ambiguous, post-observation threshold drift or missing FP16 evidence blocks rollout.

3. **Reranker memory requests/limits**

   Owner: Plan 59-04 Task 3, Wave 3. Evidence: one-pod warmup startup/steady/peak RSS, OOM/restart/throttling provenance in `59-QWEN-ROLLOUT.json`, then Gate 3. CPU stays fixed at 500m. Fail closed: no Prometheus and no cgroup/container fallback, non-finite metrics, OOM or unbounded headroom blocks the second reranker pod.

4. **Redis topology/persistence and Router DB schema/CAS**

   Owner: Plan 59-01 Task 2 discovers read-only values in Wave 0; Plan 59-05 Tasks 1–3 binds implementation to the isolated owner worktree in Wave 4. Evidence: Redis Open Source `>=7.2`, AOF primary+independent replica, same-connection `WAITAOF 1 1`, process/primary/host-loss receipts, `59-AUTHORITY-INVENTORY.json`, `59-ROUTER-OWNER-INVENTORY.json`, Router DB backup/CAS/readback, `59-ROUTER-LIFECYCLE.json`, Gates 0/4. Fail closed: unknown or insufficient failover/persistence/fsync/schema/backup path, short acknowledgement, owner-worktree drift or non-compensable DB mutation blocks activation.

5. **INT8-versus-FP16 and Qwen-versus-GTE tolerances**

   Owner: Plan 59-01 Task 3, Wave 0. Evidence: pre-observation `59-BASELINE-CONTRACT.json` and `59-EVAL-FREEZE.json` bound to corpus/qrels hashes and Gate 0; consumed by oracle and Wave 5 reports. Fail closed: absent numeric tolerance/formula/sample/slice policy, `acceptance_results_observed` not false at freeze time, or any later threshold modification blocks acceptance and cutover.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|---|---|---|---|---|
| Horistic ARM64 k3s worker | Qwen runtime | Versioned inventory says yes | `v1.35.5+k3s1` | None; live readback required. [VERIFIED: inventory] [UNKNOWN: live] |
| TEI ARM64 image | Embedding | Digest present in repo | 1.9.3 / locked digest | None; registry/platform proof required before apply. [VERIFIED: manifests/inventory] |
| Router DB | Routing CAS | Context says existing authority | `UNKNOWN` | None; Wave 0 blocks. [VERIFIED: context] [UNKNOWN: schema/live] |
| Redis | Pipeline/arbiter/soak safety state | Context says existing | `UNKNOWN`; must be `>=7.2` with AOF primary+independent replica | No in-memory, `WAIT`-only or `appendfsync everysec`-only fallback. [VERIFIED: context] [CITED: https://redis.io/docs/latest/commands/waitaof/] [UNKNOWN: live] |
| Qdrant | Vector search/cutover | `UNKNOWN` | `UNKNOWN` | None; Wave 0 blocks. [UNKNOWN: authority live] |
| Metrics API | HPA/resource evidence | Absent | — | Prometheus/cgroup/container metrics. [VERIFIED: context] |
| External runner/non-Horistic node | build/reindex/oracle/soak Jobs | `UNKNOWN` | — | Planner must allocate before each Job. [UNKNOWN: execution environment] |
| Vault hydration | Qdrant/router/Redis/HF auth | Project standard exists | profiles/vars task-specific `UNKNOWN` | None for secrets. [VERIFIED: `AGENTS.md`] [UNKNOWN: task profiles] |

**Missing dependencies with no fallback:** resolved Qdrant authority, Router DB schema/CAS path, Redis topology/persistence and external Job placement are execution blockers until Wave 0. [UNKNOWN: Wave 0]

**Missing dependencies with fallback:** Metrics API is absent; use Prometheus/cgroup/container evidence, never bypass. [VERIFIED: `59-CONTEXT.md`]

## Validation Architecture

### Test Framework

| Property | Value |
|---|---|
| Framework | Python `unittest`/CLI harness, Node built-in test runner, focused Go tests, static manifest validation. [VERIFIED: repo patterns + router guard docs] |
| Config file | No single config; Wave 0 must create/freeze fixtures and schemas. [VERIFIED: current repo inventory] |
| Quick run command | Focused unit/static command per changed component; exact commands belong in plans after owner-host inventory. [UNKNOWN: final paths] |
| Full suite command | `bash scripts/gsd-wave-regression.sh` plus wave-specific acceptance command under CPU guardrail. [VERIFIED: `.planning/config.json`, `AGENTS.md`] |

### Validation by Wave

| Wave | Must prove before next wave | Mandatory evidence |
|---|---|---|
| 0 — authority/freeze | Network branch, Qdrant authority, Router DB/Redis topology, GTE prestate/rollback, external Job placement, corpus/qrels, threshold contract frozen before acceptance results. [VERIFIED: roadmap/context] | `59-AUTHORITY-INVENTORY.json`, `59-GTE-PRESTATE.json`, `59-BASELINE-CONTRACT.json`, `59-EVAL-FREEZE.json`, hashes and `59-WAVE-0-GATE.json`. |
| 1 — artifacts/oracle/hardening | TEI/model/image pins ARM64; model byte hashes; last-token-vs-mean harness; reranker left padding/suffix/budget/queue/TTL/cancel/redaction/shutdown tests. [VERIFIED: context + official cards] | `59-ARTIFACT-LOCK.json`, `59-POOLING-ORACLE-CONTRACT.json`, `59-RERANKER-CONTRACT.json`, SBOM/lockfile digests, Wave 1 gate. |
| 2 — GTE rollback anchor | Current GTE 1+2 at 1500m captured; observed HPA 2–4 transitioned to source/live/recovery 2–2 before anchor; snapshots/alias export/restore commands and smokes ready. [VERIFIED: manifests/context] | `59-GTE-ROLLBACK-ANCHOR.json`, versioned/live/recovery HPA 2–2 receipts, DB backup receipt, Qdrant snapshot receipts + separate alias map, Wave 2 gate. |
| 3 — Qwen rollout | 2 embedding pods + reranker 1->2, each 500m; no HPA; no hostNetwork; private reachability; memory sizing; no Job on Horistic. [VERIFIED: context] | Rendered manifest hash, image IDs/platform, pod resource readback, one-pod warmup, final 2+2 rollout, network positive/negative probes, Wave 3 gate. |
| 4 — Redis/router | Persistent states, global two slots, continuation priority, exact-once terminals, restart recovery, standalone class, distinct aliases and public/native contracts. [VERIFIED: context] | Unit/race tests, Redis transition trace, router DB migration/readback, `59-ROUTER-LIFECYCLE.json`, Wave 4 gate. |
| 5 — dual index/eval | Same frozen source/chunks/IDs; Qwen collections 1024d/Cosine; high-water/checksums; pooling winner; functional smokes; >=5 warm rounds; Recall@20/nDCG@10 and CPU ratio gates. [VERIFIED: context] | Qdrant schema/count/alias export, `59-DUAL-INDEX-EVIDENCE.json`, `59-FUNCTIONAL-SMOKE.json`, `59-QUALITY-CAPACITY-EVAL.json`, Wave 5 gate. |
| 6 — cutover | Drain, zero leases/writers, reconciled journal, Router DB CAS, Qdrant aliases, independent readback, Qwen titular smoke; automatic compensation on injected failure. [VERIFIED: context] | `59-CUTOVER-JOURNAL.json`, pre/post authority dumps, receipts, fault-injection compensation evidence, Wave 6 gate. |
| 7 — soak | Same Qwen titular state for >=72 continuous hours; original Job UID reattached, no redispatch; hard failures auto-rollback; Metrics API absence covered. [VERIFIED: context] | async manifest/status, original UID, continuous samples/events, `59-SOAK-EVIDENCE.json`, Wave 7 gate. |
| 8 — drill/retirement | Qwen->GTE->Qwen smokes, restore/replay, zero loss/duplicate, snapshots retained, Graphify/GBrain/Obsidian 1024 readbacks; then GTE scale-to-zero/remove. [VERIFIED: context/roadmap] | `59-ROLLBACK-DRILL.json`, `59-DUAL-INDEX-RECONCILIATION.json`, knowledge readbacks, `59-RETIREMENT-EVIDENCE.json`, Wave 8 gate. |

### Frozen Threshold Contract

Wave 0 must record numeric values and formulas for: INT8-vs-FP16 vector similarity; oracle ranking agreement; Recall@20/nDCG@10 tolerances globally and per PT-BR/code slice; norm tolerance; p50/p95/error/queue limits; memory ceiling; hard-failure conditions; rollback RTO; no-loss/no-duplicate definitions. Only single/batch cosine `>=0.9999`, five warm rounds minimum, CPU ratio `<=1.05`, max two pipelines, batch 1/context 512/max 20 docs and soak >=72h are already locked numerically. [VERIFIED: `59-CONTEXT.md`] Todos os demais números são `UNKNOWN` até o freeze e não podem ser escolhidos depois de ver a acceptance run. [UNKNOWN: Wave 0]

O freeze deve conter `frozen_at`, corpus/qrels hashes, code/tool/image/model hashes, `acceptance_results_observed=false`, source of each threshold e immutable artifact hash. O benchmark 2026-07-22 deve ser marcado `historical_non_gating=true`. [ASSUMED: schema] [VERIFIED: benchmark exists and context requires pre-observation freeze]

### Phase Requirements -> Test Map

| Req ID | Behavior | Test Type | Automated command shape | File Exists? |
|---|---|---|---|---|
| QAI-01 | Cutover Qwen + rollback-ready GTE + retirement | integration/drill | `qwen-cutover.py verify-journal` + `verify-retirement` | No — Wave 0/6/8 |
| QAI-02 | ARM64, 500m, private 2+2 | static/component | manifest verifier + pod/platform/network readback | No — Wave 1/3 |
| QAI-03 | Two persistent pipelines | unit/integration | focused Go state-machine tests + restart/cancel/TTL smoke | No — Wave 1/4 |
| QAI-04 | Qdrant 1024d separate/reproducible | migration/integration | Qdrant preflight + dual-index verifier | No — Wave 0/5 |
| QAI-05 | Functional smokes | component/e2e | `qwen-functional-smoke.py --require-all` | No — Wave 1/5/6 |
| QAI-06 | Paired quality/capacity | evaluation | `evaluate-rag-quality.py verify --freeze ...` | No — Wave 0/5 |
| QAI-07 | 72h titular soak | async/e2e | `qwen-soak.py verify --min-hours 72 --original-uid` | No — Wave 7 |
| QAI-08 | Restore/replay and productive drill | e2e/drill | `qwen-cutover.py verify-drill --no-loss --no-duplicate` | No — Wave 8 |

### Sampling Rate

- **Per task commit:** static/schema + focused unit test under 30s when possible; heavy commands use `builds`. [VERIFIED: `AGENTS.md`] [ASSUMED: timing target]
- **Per wave merge:** full wave verifier and gate JSON readback; absent evidence is FAIL. [VERIFIED: `59-CONTEXT.md`]
- **Capacity:** at least five warm-cache rounds on matched corpus, report all rounds/variance, never only best. [VERIFIED: `59-CONTEXT.md`]
- **Soak:** continuous >=72h; exact sampling interval is `UNKNOWN` until Wave 0 sizes storage/observability. [VERIFIED: `59-CONTEXT.md`] [UNKNOWN: interval]
- **Phase gate:** Wave 8 drill/retirement evidence PASS and no unresolved `UNKNOWN`. [VERIFIED: `59-CONTEXT.md`]

### Wave 0 Gaps

- [ ] read-only Qdrant authority/version/auth/storage/aliases/collections/snapshot inventory;
- [ ] Router DB schema/version/CAS and Redis topology/persistence inventory;
- [ ] immutable artifact/threshold/eval JSON schemas;
- [ ] FP16 oracle + pooling A/B harness and frozen PT-BR/code corpus/qrels;
- [ ] reranker unit harness for left padding, suffix, budget, batch equivalence, queue, TTL, cancel, redaction and shutdown;
- [ ] dual-index journal/replay/parity verifier;
- [ ] cutover journal/CAS/compensation verifier;
- [ ] external-runner assignment for build/reindex/oracle/soak;
- [ ] 72h async UID reattach and no-redispatch verifier.

[VERIFIED: gap analysis against current repo and `59-CONTEXT.md`]

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---|---|---|
| V2 Authentication | yes at router; no direct public worker | Preserve router Bearer auth; backends private-only. [VERIFIED: `docs/operations/local-ai-embeddings.md`] |
| V3 Session Management | pipeline lifecycle analogous, not user session | Opaque pipeline IDs, deadline, idempotent terminal state, no auth data in IDs. [ASSUMED] |
| V4 Access Control | yes | Model/corpus allowlists, RBAC, private NodePorts, negative reachability probes. [CITED: https://devguide.owasp.org/en/03-requirements/05-asvs/] |
| V5 Validation/Sanitization | yes | Byte/doc/token/context/top_n bounds; UTF-8/types; finite vectors/scores. [CITED: https://devguide.owasp.org/en/03-requirements/05-asvs/] |
| V6 Cryptography | yes for integrity/secrets | SHA-256/digests, Vault; never custom crypto. [VERIFIED: `AGENTS.md`] |
| V7 Error Handling/Logging | yes | Typed errors, redacted structured logs, no query/document/token/vector. [CITED: https://devguide.owasp.org/en/03-requirements/05-asvs/] |
| V8 Data Protection | yes | Aggregate evidence, retention/access policy, no raw corpus in artifacts. [VERIFIED: `AGENTS.md`] |
| V10 Malicious Code | yes | Exact pins, legitimacy gate, lockfile, SBOM, no runtime install/download except controlled checksum flow. [VERIFIED: package audit + context] |
| V13 API/Web Service | yes | Size/rate/admission limits, TTL/cancel, private backend, router-owned public contract. [CITED: https://devguide.owasp.org/en/03-requirements/05-asvs/] |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---|---|---|
| Direct NodePort bypasses governor | Elevation/DoS | NetworkPolicy enforcement proof + firewall/private path + negative public probe. [CITED: Kubernetes NetworkPolicy docs] |
| Oversized query/docs exhaust tokenizer/model | DoS | Pre-token byte/doc caps, 512-token total budget, max 20 sequential docs, bounded queue. [VERIFIED: `59-CONTEXT.md`] |
| Lease leak or acknowledged state lost after process/primary/host failure | DoS/Tampering | Redis CAS, same-connection `WAITAOF 1 1`, independent AOF replica, deadline/sweeper, cancel propagation and exact-once terminal receipt. [VERIFIED: `59-CONTEXT.md`] [CITED: https://redis.io/docs/latest/commands/waitaof/] |
| Model/image drift | Tampering | Exact revisions, image digest, file SHA-256, lockfile/SBOM and startup identity readback. [VERIFIED: `59-CONTEXT.md`] |
| 768/1024 cross-write | Tampering | Distinct aliases/collections + signature validation + schema size 1024. [VERIFIED: `59-CONTEXT.md`] |
| Partial multi-authority cutover | Tampering/Availability | Journal, expected versions, independent readbacks and automatic compensation. [VERIFIED: `59-CONTEXT.md`] |
| Sensitive corpus in logs/evidence | Information Disclosure | IDs/counts/aggregates only; redaction tests; Vault/no-secret policy. [VERIFIED: `AGENTS.md`] |
| Temporary Qdrant job can mutate aliases/GTE/delete or impersonate another Job | Elevation/Tampering/Spoofing | A no-passthrough L7 broker holds the only native data credential/egress; Jobs have none. Issuer bootstrap uses pinned server TLS, nonce and CSR PoP before live owner attestation. Replay uses an explicitly delivered digest-pinned 500m anti-Horistic image and AOF-confirmed journal. The srv1 finalizer has no Kubernetes credential/egress; a separate temporary 500m cleanup-authority Job runs on an independent failure domain with kubelet-renewed projected token bound to the discovered API audience, fixed admission/RBAC, UID/resourceVersion delete preconditions and terminal self-RoleBinding revoke. Executor/srv1/authority-Pod death therefore still converges exact cleanup and negative direct-API/TokenReview/authority/broker/network probes. [VERIFIED: `59-CONTEXT.md`] [CITED: https://qdrant.tech/documentation/operations/security/] |
| Graphify heartbeat becomes a second privileged writer | Elevation/Tampering | The root-owned peer-authenticated publisher is the sole serving mutator and accepts only `publish-qwen`, `restore-gte`, `restore-qwen` and `heartbeat-current`. The no-argv heartbeat client has no filesystem write permission or `ReadWritePaths`; it can only request the fixed publisher operation, which verifies hashes and performs `utimensat`. Byte-write attempts by that client and all other non-publisher identities must fail. [VERIFIED: local GSD reader and Phase 59 contract] |
| Old alias-arbiter host regains authority after cold handoff | Spoofing/Elevation/Tampering | Revoke the old generation, block old-host egress/socket/token and prove old-host plus partition-heal/rejoin negative operations before issuing a new generation or starting standby. Any reordered, missing or ambiguous step remains drained in `BLOCK`. [VERIFIED: `59-CONTEXT.md`] |
| npm transitive install lifecycle executes unreviewed code | Tampering/Elevation | Full lock-graph origin/integrity/lifecycle audit, `npm ci --ignore-scripts`, zero lifecycle children and CPU/offline startup proof. [CITED: https://docs.npmjs.com/cli/v11/commands/npm-ci/] |

## Final Local-Authority Corrections — 2026-07-23

- GTE active desired state is two direct-apply files,
  `k8s/ebeddings-local/tei-gte.yaml` and `tei-gte-reranker.yaml`; there is no
  incumbent `kustomization.yaml`. Retirement must move/delete those real source
  paths and update direct runbook commands. [VERIFIED: repo reads]
- Canonical GSD Graphify `status/query` opens
  `.planning/graphs/graph.json` directly. A side generation pointer would not
  affect real readers. Wave 6 installs a root-owned fixed-operation publisher as
  the sole byte writer, stops the global auto-update service/hook, quiesces
  readers and publishes the canonical generation durably. Wave 8 can request
  only the publisher's fixed restore operations over prebuilt archives. Both
  waves verify with the actual GSD command, while the executor remains
  read-only. [VERIFIED:
  `/mnt/c/Users/muniz/.codex/gsd-core/bin/lib/graphify.cjs`,
  `modules/srv1-ops/systemd/gsd-graphify-auto-update.service`]
- A Redis fencing token cannot enforce Qdrant by itself. Wave 4 must provision
  one durable alias arbiter with the only write credential/network path,
  revoke bypass writers and journal unknown sent requests as INFLIGHT. Lease
  expiry alone never authorizes a successor. [INFERRED from Qdrant alias API
  limits and local authority review]
- The GSD async core treats `completed-unverified` as a human-confirmation
  boundary. Autonomous continuation therefore needs a mode-bound signed
  resumer plus one idempotent same-root Codex/GSD resume handoff; the fallback
  must retain the core human boundary. [VERIFIED: installed GSD workflows]
- Kubernetes Deployment `maxSurge` is an explicit upper bound on extra rollout
  pods, ResourceQuota rejects namespace consumption above `pods`,
  `requests.cpu` and `limits.cpu`, and PDB protects only voluntary disruptions.
  Therefore a low-CPU `2–5` design is best represented as four permanent model
  pods, one serialized post-GTE rollout surge and PDB `minAvailable: 1` per
  service—not HPA. ResourceQuota is the sixth-pod backstop, while the rollout
  coordinator prevents both Deployments from deliberately surging together.
  [VERIFIED: official Kubernetes Deployment, ResourceQuota and PDB docs]
- During GTE coexistence the measured allocation is already 3500m
  (`1500m GTE + 2000m Qwen`) on 4 vCPU. A fifth 500m Qwen model pod would
  consume the entire nominal CPU budget and leave no explicit system reserve,
  so coexistence must cap Qwen at four. After GTE retirement, a fifth can be
  admitted only when live CPU plus largest-pod memory plus system-reserve
  headroom is independently proven. [INFERRED from repo resource contracts]

## Sources

### Primary — verified local/API

- `.planning/workstreams/qwen-local-ai/.../59-CONTEXT.md`, `REQUIREMENTS.md`, `ROADMAP.md`, `STATE.md` — locked cutover semantics, waves and requirements. [VERIFIED: repo reads]
- `k8s/ebeddings-local/tei-gte.yaml`, `tei-gte-reranker.yaml` — incumbent manifests, 1+2 pods, 1500m, HPA and TEI digest. [VERIFIED: repo reads]
- `services/qwen-reranker-onnx/server.mjs`, `package.json` — prototype gaps and explicit package. [VERIFIED: repo reads]
- `scripts/embeddings-bench/results-2026-07-22-gte-qwen.md`, `compare-embeddings.py` — historical non-gating mean/CPU evidence. [VERIFIED: repo reads]
- Hugging Face model API/HEAD at locked revisions — oracle revision and ONNX sizes/SHA-256. [VERIFIED: Hugging Face API/HEAD]
- npm registry + GSD package-legitimacy seam — direct `@huggingface/transformers@4.2.0` is pinned and has no direct postinstall; approval remains conditional on Wave 1 full transitive audit and ignored-script offline startup. [VERIFIED: npm registry + package-legitimacy seam]

### Official documentation — cited

- https://huggingface.co/Qwen/Qwen3-Embedding-0.6B — last-token, instruction, documents, L2, 1024d.
- https://huggingface.co/Qwen/Qwen3-Reranker-0.6B — left padding, suffix, truncation budget and yes/no score.
- https://huggingface.co/janni-t/qwen3-embedding-0.6b-int8-tei-onnx/commit/8fe0c238c7c48016d28e750413ca492024be3ddf — artifact declares mean pooling.
- https://huggingface.co/onnx-community/Qwen3-Reranker-0.6B-ONNX — dedicated ONNX/Transformers.js CausalLM export.
- https://huggingface.co/docs/text-embeddings-inference/supported_models — Qwen3 embedding/ARM64 support and supported reranker list.
- https://github.com/huggingface/text-embeddings-inference/releases/tag/v1.9.3 — TEI release.
- https://onnxruntime.ai/docs/get-started/with-javascript/node.html — prebuilt Linux ARM64 CPU Node binding.
- https://qdrant.tech/documentation/manage-data/collections/ — dimension/metric, Cosine normalization and atomic aliases.
- https://qdrant.tech/documentation/snapshots/ — collection snapshots exclude aliases.
- https://redis.io/docs/latest/develop/using-commands/transactions/ — WATCH/MULTI/EXEC CAS and no rollback.
- https://redis.io/docs/latest/commands/expire/ — expiry/persistence semantics.
- https://redis.io/docs/latest/commands/waitaof/ — Redis 7.2+, same-connection local/replica AOF fsync acknowledgements and blocking limitations.
- https://redis.io/docs/latest/operate/oss_and_stack/management/persistence/ — AOF and `appendfsync` durability tradeoffs.
- https://docs.npmjs.com/cli/v11/commands/npm-ci/ — `--ignore-scripts`, dependency-origin controls and lifecycle policy.
- https://qdrant.tech/documentation/operations/security/ — API keys and JWT RBAC; the documented access classes are insufficient for this plan's per-operation deny matrix, therefore the L7 broker is mandatory.
- https://kubernetes.io/docs/concepts/configuration/manage-resources-containers/ — request/scheduling and limit/throttling.
- https://kubernetes.io/docs/concepts/workloads/autoscaling/horizontal-pod-autoscale/ — Metrics API requirement.
- https://kubernetes.io/docs/concepts/workloads/pods/probes/ — startup/readiness/liveness semantics.
- https://kubernetes.io/docs/concepts/policy/resource-quotas/ — aggregate namespace quota.
- https://kubernetes.io/docs/concepts/workloads/controllers/deployment/ — `maxSurge`, `maxUnavailable` and stalled rollout behavior.
- https://kubernetes.io/docs/tasks/run-application/configure-pdb/ — PDB availability semantics and voluntary-disruption limitation.
- https://kubernetes.io/docs/concepts/security/pod-security-standards/ — restricted controls.
- https://kubernetes.io/docs/concepts/services-networking/network-policies/ — enforcement dependency.
- https://devguide.owasp.org/en/03-requirements/05-asvs/ — applicable ASVS categories.

### Tertiary — assumed/unknown

- Exact namespace/ports, backend queue capacity, memory limits, Redis key schema, cutover JSON schema and observability sampling interval remain assumptions or Wave 0 decisions. [ASSUMED]
- Qdrant authority/version/topology, Router DB schema, Redis topology/persistence, live k3s state and external runner remain `UNKNOWN`. [UNKNOWN: Wave 0]

## Metadata

**Confidence breakdown:**

- Standard stack: HIGH para pins/hashes/package; MEDIUM para image-to-runtime mapping; LOW até ARM64 rollout readback. [VERIFIED: source assessment]
- Architecture: HIGH para boundaries/cutover sequence locked; MEDIUM para schemas sugeridos. [VERIFIED: source assessment]
- Pooling/quality: HIGH para conflito official-vs-artifact; LOW até A/B/oracle/qrels. [VERIFIED: source assessment]
- Resources: HIGH para CPU math 1500m -> coexistência 3500m -> Qwen steady 2000m/transient 2500m; LOW para memory sizing até Wave 3. [VERIFIED: source assessment]
- Data migration: MEDIUM para padrão dual-index/journal; LOW até Qdrant authority e writer topology. [VERIFIED: source assessment]
- Security: MEDIUM; controles são oficiais, enforcement live permanece não verificado. [VERIFIED: source assessment] [UNKNOWN: live enforcement]

**Research date:** 2026-07-23

**Valid until:** 2026-08-22 para contratos; estado live, registry manifests, aliases e capacities devem ser revalidados imediatamente antes de cada mutation wave.
