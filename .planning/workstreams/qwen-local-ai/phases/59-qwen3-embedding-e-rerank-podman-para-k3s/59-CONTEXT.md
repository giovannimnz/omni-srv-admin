# Phase 59: Qwen3 Embedding e Rerank Podman para k3s - Context

**Gathered:** 2026-07-23
**Reconciled:** 2026-07-23
**Status:** Ready for planning

<domain>
## Phase Boundary

Substituir a trilha GTE por Qwen3 no k3s ARM64, com Qwen3 Embedding 0.6B
INT8 via TEI/ONNX Runtime em 1024 dimensoes e Qwen3 Reranker 0.6B INT8 via
servico ONNX dedicado. A fase inclui os artefatos reproduziveis, o pipeline
persistente no governor, collections e aliases Qdrant, reindexacao, avaliacao,
cutover, soak, rollback drill e retirada controlada dos workloads GTE.

O cutover foi autorizado pelo operador em 2026-07-23. GTE permanece ativo
somente como incumbent e ancora de rollback ate Qwen passar readiness, smokes,
qualidade, capacidade, cutover, soak e drill. Vetores GTE 768d e Qwen 1024d
nunca compartilham collection nem alias de modelo.

A fase nao presume onde Qdrant roda, nao trata metricas ausentes como PASS e
nao executa build, compile ou suite pesada fora do profile `builds` limitado a
20% da CPU do host. O teto de 20% se aplica a build/compile/teste pesado, nao
aos quatro pods de runtime previamente orcados.
</domain>

<decisions>
## Implementation Decisions

### Modelo e runtime

- **D-01:** Qwen sera o titular ao final da fase. GTE permanece disponivel e imutavel como rollback ate o gate final de retirement.
- **D-02:** Qwen Embedding usara `janni-t/qwen3-embedding-0.6b-int8-tei-onnx`, revision `8fe0c238c7c48016d28e750413ca492024be3ddf`, no TEI com OrtBackend/ONNX Runtime. O INT8 esta incorporado no `model.onnx`.
- **D-03:** O contrato de pooling sera decidido por gate A/B entre `last-token` e `mean`, comparado ao oracle oficial FP16 `Qwen/Qwen3-Embedding-0.6B`. `last-token` e a preferencia normativa do modelo oficial; nenhum candidato sera promovido sem equivalencia funcional, instruction-aware e de ranking. A saida de producao sera 1024d normalizada.
- **D-04:** Qwen Reranker usara `onnx-community/Qwen3-Reranker-0.6B-ONNX`, revision `9995c50e2310679108a55f5ccd16ba8be9f17c20`, em servico HTTP ONNX dedicado. TEI nao sera usado para o reranker enquanto nao houver suporte oficial ao CausalLM yes/no.
- **D-05:** Os aliases de modelo serao `embedding-qwen3-0.6b-int8-1024-v1` e `reranker-qwen3-0.6b-int8-v1`. `embedding-gte-v1` e `reranker-gte-multilingual-v1` nunca serao silenciosamente remapeados para Qwen.
- **D-06:** Imagens, modelos, lockfiles e bases de build devem ser pinados por revision/digest e validados para `linux/arm64`; tags `latest` e revisions `main` bloqueiam promocao. Uma imagem Podman local não conta como entregue: registry autenticada ou import explícito no containerd do runner, seguido de pull/inspect independente pelo digest exato, é obrigatório.

### Pipeline, governor e recursos

- **D-07:** O governor implementara no Redis existente uma maquina de estados persistente `QUEUED -> EMBEDDING -> VECTOR_SEARCH -> RERANK -> COMPLETED`, com terminais `FAILED`, `CANCELLED` e `EXPIRED`.
- **D-08:** Havera no maximo dois pipelines completos simultaneos. A lease permanece ocupada durante todo o ciclo, continuacoes tem prioridade sobre novos ciclos, e liberacao por sucesso, erro, cancelamento, TTL ou restart e idempotente. Chamadas standalone de embedding usam classe de admission separada.
- **D-09:** O estado permanente tera dois pods de embedding e dois pods de reranker. Cada pod normal tera `requests.cpu=500m` e `limits.cpu=500m`; quatro pods totalizam `2000m`.
- **D-10:** O rollout do reranker sera progressivo: um pod, warmup/sizing, depois dois pods. O estado permanente e fixo em 2+2; HPA fica fora desta fase porque adicionaria CPU sem respeitar a fila central de dois pipelines.
- **D-11:** Qwen usara namespace dedicado, sem `hostNetwork`, com ResourceQuota, LimitRange, Pod Security, NetworkPolicy e PDB `minAvailable: 1` por serviço comprovadamente aplicados. Services/NodePorts serão acessíveis apenas pela rede privada do router.
- **D-12:** Wave 0 registra o HPA GTE observado em 2–4 sem mutar; Wave 2 altera source/live/recovery para 2–2, faz readback independente e só então gera o rollback anchor. Assim GTE permanece em 1 embedding + 2 reranker = `1500m`, permitindo coexistência com Qwen `2000m` em `3500m`. Jobs de build, reindex, oracle e soak não serão agendados no Horistic se consumirem o quinto slot; devem rodar em outro node ou runner externo, cada um limitado a `500m`.
- **D-13:** O governor e o Kubernetes sao controles complementares: a fila limita ciclos ativos; requests/limits, quota e memory requests determinam scheduling. Metrica ausente no Metrics API exige Prometheus/cgroup/container metrics, nunca bypass.
- **D-25:** Estado de segurança no Redis exige Redis Open Source `>=7.2`, AOF no primary e em pelo menos uma replica em failure domain independente. Cada escrita que libera admission, backend, alias mutation, slot ou avanço do soak deve ser seguida na mesma conexão por `WAITAOF 1 1 TIMEOUT`, com ambos os contadores confirmados antes do efeito externo. `WAIT`, `appendfsync everysec`, acknowledgement em memória ou `WAITAOF` dentro de Lua/MULTI não satisfazem o gate.

### Dimensao, indices e dados

- **D-14:** Qwen usara 1024 dimensoes para documentacao tecnica. GTE permanece 768d; padding, truncamento ou mistura entre os espacos vetoriais e proibido.
- **D-15:** A Wave 0 deve resolver a autoridade live do Qdrant, endpoint, versao, auth, storage, backups, aliases e collections antes de qualquer mutacao. `UNKNOWN` bloqueia.
- **D-16:** As collections fisicas Qwen serao `gbrain_qwen3_1024_v1`, `obsidian_qwen3_1024_v1` e `graphify_qwen3_1024_v1`, `Cosine`, com aliases estaveis por corpus. Collections GTE 768d permanecem imutaveis e recuperaveis.
- **D-17:** GTE e Qwen serao indexados a partir do mesmo corpus-fonte congelado, com chunking, logical IDs, high-water marks e checksums reproduziveis. Paridade e medida contra o corpus-fonte, nao contra a cobertura parcial existente.
- **D-26:** Qdrant separa control plane e data plane. Somente o alias arbiter possui credential/egress de aliases. Como o RBAC nativo do Qdrant não expressa todas as negações por operação, um data broker L7 separado, sem passthrough genérico, é o único portador da credential e do egress Qdrant de data management; Jobs/clients nunca têm acesso direto. Um issuer independente sem Qdrant access TokenReviews o projected ServiceAccount token e lê a cadeia live Pod UID→ownerReference→Job UID/resourceVersion→runner/image/nonce antes de assinar o certificado efêmero. O bootstrap inicial usa server-auth TLS com CA+SPKI pinados, nonce one-shot e CSR proof-of-possession; plaintext, replay, wrong-cert e token logging são negados. O broker revalida token/certificado/attestation e expõe somente API privada mTLS de operações fixas. Firewall/NetworkPolicy ficam restritos ao runner congelado. Provisionamento, reindex, snapshot e replay usam credentials distintas nas três collections Qwen exatas; aliases/delete/GTE/admin são negados. O replay da Wave 8 roda em um Job digest-pinned de 500m fora de Horistic. Como Kubernetes RBAC não restringe `delete` por label/UID, o finalizer não recebe kubeconfig/token nem egress ao API server. Namespace/admission exclusivos impedem workloads alheios e restringem a authority fixa. A audience de Kubernetes API é descoberta/fixada da configuração live do k3s na Wave 0. A Wave 5 congela um cleanup-authority Job digest-pinned de 500m, e a Wave 8 o executa fora de Horistic e num failure domain independente de srv1; seu projected token é renovado pelo kubelet após restart/outage maior que TTL, sem bootstrap/admin kubeconfig. O authority faz deletes UID/resourceVersion-preconditioned, journal terminal e self-revoke da própria RoleBinding antes de sair/TTL cleanup. Assim journal AOF-confirmed, issuer revoke, authority-mediated UID/resourceVersion deletion e probes negativos continuam crash-durable sem dar autoridade Kubernetes direta ao finalizer.

### Gates, cutover e rollback

- **D-18:** O reranker deve corrigir left padding, preservacao do suffix, truncation budget, fila limitada, TTL, cancelamento, redaction, shutdown e score single/batch antes do rollout. O envelope inicial e batch interno 1, contexto 512 e ate 20 documentos sequenciais.
- **D-19:** O gate de embedding cobre instruction somente na query, documentos sem instruction, 1024d, normalizacao, batch 1/4, cosine single/batch `>=0.9999`, oracle FP16 e ranking. Thresholds INT8-versus-FP16 sao congelados na Wave 0 antes de observar resultados.
- **D-20:** Qualidade usa corpus/qrels PT-BR tecnico e codigo congelados antes da execucao: Recall@20 e nDCG@10 do Qwen nao podem ser inferiores ao GTE alem da tolerancia predeclarada. Capacidade usa pelo menos cinco rounds warm-cache e CPU-seconds `<=1.05x` GTE.
- **D-21:** O cutover usa drain de admission, zero leases, pausa de writers, journal, CAS no banco do router e aliases Qdrant, readback independente e rollback compensatorio automatico em qualquer falha.
- **D-22:** O soak ocorre por no minimo 72 horas continuas com Qwen titular e GTE rollback-ready. Hard failures executam rollback automatico; a espera retorna `external_job_waiting` e reata ao UID original sem redispatch.
- **D-23:** A retirada do GTE exige soak PASS e drill produtivo Qwen -> GTE -> Qwen, com smokes em ambos, restore/replay, zero perda/duplicacao e snapshots retidos. So entao GTE e escalado a zero/removido.
- **D-24:** Cada wave termina em `59-WAVE-N-GATE.json` fail-closed. O gate exige hashes, prestate/poststate por readback, invariantes `PASS|FAIL`, receipts, aliases, leases, rollback target e `next_wave_allowed`; `UNKNOWN`, evidencia ausente ou metrica indisponivel nunca viram PASS.
- **D-27:** Graphify terá uma única autoridade de mutação: um publisher UDS root-owned de operações fixas (`publish-qwen`, `restore-gte`, `restore-qwen`, `heartbeat-current`) que valida peer, journal, source realpath/hash e destinos exatos. Publish/restore executam temp-write/fsync/rename/parent-fsync/readback; `heartbeat-current` verifica hashes e executa somente `utimensat` no alvo fixo. O timer no-argv é apenas um client sem qualquer write permission ou `ReadWritePaths` sobre os arquivos servidos. Nenhum componente oferece path/argv arbitrário; usuário normal, executor, heartbeat client, hooks, sweeps e watchdog falham provas de byte-write.
- **D-28:** O reranker só pode ser construído a partir do lock graph transitivo integralmente auditado e instalado com `npm ci --ignore-scripts`. Origem mutável, integrity ausente, lifecycle child observado ou runtime CPU/offline incapaz de iniciar sem install scripts bloqueia e exige replanejamento.
- **D-29:** Heartbeat stale durante indisponibilidade do alias arbiter tenta apenas restart bounded da mesma identidade ativa e replay durável. Cold handoff exige journal replicado sem `INFLIGHT` ambíguo, alias-map exato e esta ordem: revogar a geração antiga, bloquear egress/socket/token do host antigo, provar negative probe, só então emitir nova geração e iniciar standby. Partition heal/rejoin do active antigo deve continuar negado. Estado limpo compensa automaticamente para GTE; ambiguidade mantém admission/writers drenados em `BLOCK`.
- **D-30:** O envelope Qwen é `2–5` pods de modelo, mas não é autoscaling: desejado permanente `2 embedding + 2 reranker = 4 pods/2000m`; piso degradado `1+1 = 2 pods/1000m` somente durante falha, manutenção ou recuperação; máximo `5 pods/2500m` somente como surge serializado de rollout. Enquanto GTE coexistir, ResourceQuota Qwen limita `pods=4`, `requests.cpu=2000m` e `limits.cpu=2000m`, e ambos Deployments usam `maxSurge=0,maxUnavailable=1`. Após retirement GTE, somente se o readback provar pelo menos `500m` de CPU allocatable adicional, a memória medida do maior pod e a reserva congelada do sistema, o gate final troca atomicamente a quota para `pods=5`/`2500m` e os Deployments para `maxSurge=1,maxUnavailable=0`. O controlador executa rollout de embedding e reranker em série; a quota nega o sexto pod e um fault test tenta rollouts simultâneos. O quinto pod nunca aumenta os dois slots do governor, nunca é steady state e deve desaparecer ao final de cada rollout. Jobs de build/oracle/reindex/soak/replay continuam em namespace/runner separado e não contam nesse envelope.

### the agent's Discretion

- Definir nomes finais de Deployments, Services, PVCs, Jobs e portas, preservando os aliases e collections locked.
- Escolher o limite de memoria final depois do warmup, sem alterar os `500m` de CPU ou admitir quatro rerankers.
- Escolher a implementacao exata do endpoint orquestrador no router, desde que a lease Redis cubra o ciclo completo e chamadas standalone permaneçam separadas.
- Manter nomes legados de scripts `qwen-canary-*` apenas se o nome nao alterar a semantica de cutover; novos manifests e namespace devem refletir producao.
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Existing runtime and live authority

- `AGENTS.md` — CPU guardrail, unidade k3s e politica de SSH.
- `.planning/config.json` — Graphify ainda aponta para GTE/768 e deve ser migrado somente no gate final.
- `k8s/ebeddings-local/tei-gte.yaml` e `k8s/ebeddings-local/tei-gte-reranker.yaml` — incumbent e rollback atual.
- `inventory/hosts/horistic-srv.yaml` — host ARM64 e branch de rede.
- `docs/operations/local-ai-embeddings.md` — contrato publico e runbook.
- `services/qwen-reranker-onnx/server.mjs` e `package.json` — prototipo a endurecer.
- `scripts/embeddings-bench/results-2026-07-22-gte-qwen.md` — evidencia preliminar, nao gate de qualidade.
- `modules/fork-sync/projects/atius-router/UPSTREAM-SYNC-GUARDS.md` — paths protegidos do router/governor.
- `modules/srv1-ops/configs/resource-governor.env` — profile de build a 20%.

### Official runtime/model references

- `https://huggingface.co/Qwen/Qwen3-Embedding-0.6B` — 1024d, instruction e last-token oficiais.
- `https://huggingface.co/Qwen/Qwen3-Reranker-0.6B` — prompt/suffix e score yes/no oficiais.
- `https://huggingface.co/janni-t/qwen3-embedding-0.6b-int8-tei-onnx` — artefato embedding INT8.
- `https://huggingface.co/onnx-community/Qwen3-Reranker-0.6B-ONNX` — artefato reranker INT8.
- `https://github.com/huggingface/text-embeddings-inference` — TEI ARM64/ONNX/Qwen3.
- `https://github.com/huggingface/text-embeddings-inference/issues/643` — ausencia de suporte TEI ao Qwen3 Reranker.
- `https://onnxruntime.ai/docs/get-started/with-javascript/node.html` — ONNX Runtime Node ARM64.
- `https://qdrant.tech/documentation/concepts/collections/` — collections e aliases.
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- O harness Python existente ja mede embedding, CPU, RSS e consistencia, mas precisa de instruction-aware/oracle, qrels e gate fail-closed.
- O servidor reranker ja implementa o score yes/no, mas ainda tem padding/truncation, queue, observability e lifecycle incompletos.
- O router ja possui Redis e governor por request; a fase estende isso para lease de pipeline persistente.
- Os manifests GTE fornecem probes e topologia, mas usam pins mutaveis e nao constituem rollback imutavel sem freeze/export.

### Known live constraints

- Horistic possui 4 CPU allocatable. GTE usa atualmente 1500m; quatro pods Qwen adicionam 2000m. Durante coexistência não há quinto pod Qwen. Após retirement, o surge de 500m depende de readback de CPU, memória e reserva do sistema; nenhum Job adicional disputa esse envelope.
- O Metrics API nao esta disponivel; gates de recursos precisam de fonte alternativa.
- O banco de canais do router e autoridade de routing e exige backup, CAS, readback e rollback.
- A localizacao/autoridade Qdrant nao esta confirmada e deve ser descoberta na Wave 0.
- O checkout owner do router e dirty; execucao exige worktree/checkout limpo e prova de nao sobreposicao.
</code_context>

<specifics>
## Specific Ideas

- A prioridade e menor consumo de CPU sem sacrificar verdade funcional: INT8 so vence se passar o oracle FP16 e os qrels.
- O estado permanente e exatamente 2 pods de embedding + 2 pods de reranker, todos a 500m; `2–5` significa piso degradado 1+1 e pico transitório de um único surge, não HPA.
- O pipeline titular e sequencial: Embedding -> Qdrant top-K -> Reranker top-N.
- O cutover nao renomeia GTE para Qwen; aliases de modelo e collections permanecem explicitamente distintos.
- Graphify, GBrain e Obsidian devem migrar para 1024d com collections e high-water marks proprios.
</specifics>

<deferred>
## Deferred Ideas

- HPA para Qwen Embedding/Reranker; a Phase 59 usa envelope fixo e surge serializado.
- Qwen Reranker FP16 como fallback automatico.
- Qwen Reranker dentro do TEI sem suporte oficial.
- Contexto operacional de 32K ou batch interno maior que 1 antes de sizing.
- Remocao de snapshots/collections GTE no mesmo momento do retirement dos pods.
</deferred>

---

*Phase: 59-qwen3-embedding-e-rerank-podman-para-k3s*
*Context reconciled: 2026-07-23*
