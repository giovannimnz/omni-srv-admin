---
spike: 006
name: qwen-podman-rag-stack
type: rollout-plan
status: preflight
tags: [qwen3, embeddings, reranker, int8, onnx, podman, tei, qdrant, governor, arm64]
---

# Plano: Qwen3 RAG em Podman na OCI

## Objetivo

Testar e, somente após passar os gates, integrar uma trilha Qwen3 para RAG em
português, mantendo o GTE atual como baseline e fallback. A prioridade de
execução é menor consumo total de processador, com limites explícitos por
container; a restrição global de 20% aplica-se a build/compile, não a estes
serviços em runtime.

## Estado e correções já verificadas

- O host OCI alvo (`atius-srv-1`) é ARM64/aarch64, tem 4 CPUs, cerca de 23 GiB
  de RAM e Podman 4.9.3.
- `ghcr.io/huggingface/text-embeddings-inference:cpu-latest` não possui imagem
  Linux ARM64; usar a variante ARM64 pinada, atualmente `cpu-arm64-latest`, ou
  uma tag ARM64 versionada comprovadamente existente.
- `janni-t/qwen3-embedding-0.6b-int8-tei-onnx` existe, contém `model.onnx` de
  aproximadamente 599 MB e declara INT8/ONNX para TEI CPU.
- O artifact não traz `1_Pooling/config.json`; TEI precisa de
  `--pooling mean`. Sem essa flag o processo aborta no warm-up.
- O Qwen3-Embedding-0.6B tem contexto de 32K e saída nativa de até 1024
  dimensões. A dimensão padrão do artifact deve ser medida no endpoint; não
  assumir 768 nem misturar vetores 768 e 1024.
- `Qwen/Qwen3-Reranker-0.6B` é um modelo separado. A matriz oficial atual do
  TEI não o lista como reranker suportado.

## Arquitetura alvo

```text
cliente/RAG
   -> router-ai-atius + embeddinggovernor
   -> Qwen embedding INT8/ONNX em Podman/TEI ARM64
   -> coleção Qdrant qwen3_1024 (reindexação completa)
   -> top-K (20, limite governado)
   -> Qwen reranker INT8/ONNX em Podman + servidor compatível
   -> top-N (5-10) -> LLM
```

O GTE `embedding-gte-v1`/768 e o reranker GTE permanecem ativos e com aliases
separados durante todo o canary. A coleção Qwen terá nome, dimensão e
`embedding_model` próprios; não haverá padding, projeção ou mistura de índices.

## Runtime e artefatos

### Embedding

Canary primário:

- Modelo: `janni-t/qwen3-embedding-0.6b-int8-tei-onnx`.
- Runtime: `ghcr.io/huggingface/text-embeddings-inference:cpu-arm64-*` em
  Podman.
- Flags mínimas: `--pooling mean`, `--max-batch-tokens 512` no primeiro smoke,
  `--max-client-batch-size 4`, um tokenization worker.
- Produção: promover `--max-batch-tokens 1024` somente se os testes de contexto
  passarem; 512/1024 é teto operacional e implica truncar/rechunkar entradas
  maiores, apesar do contexto teórico de 32K.
- CPU: `--cpus=0.5`, `OMP_NUM_THREADS=1`, `RAYON_NUM_THREADS=1` e
  `ORT_THREAD_POOL_SIZE=1`.
- Alias proposto: `qwen3-embedding-0.6b-int8-v1`.

Fallback correto, caso o ONNX INT8 falhe semanticamente: Qwen oficial em TEI
FP16, ainda em Podman ARM64, aceitando aproximadamente o dobro do trabalho de
CPU do GTE segundo o spike 005; não promover por preferência nominal a INT8.

### Reranker

Canary primário, se o smoke confirmar o ranking:

- Base: `Qwen/Qwen3-Reranker-0.6B`.
- Artifact INT8: `onnx-community/Qwen3-Reranker-0.6B-ONNX`,
  `onnx/model_quantized.onnx`.
- Runtime: servidor próprio pequeno em Node/Transformers.js v4 + ONNX Runtime,
  empacotado e executado no Podman. Ele expõe `/rerank` no contrato nativo TEI
  (`query`, `texts`) para reutilizar o adapter já integrado ao router.
- A pontuação é a probabilidade normalizada do token `yes` contra `no`; o
  servidor deve manter o prompt Qwen e o limite de 20 documentos do governor.
- Alias proposto: `qwen3-reranker-0.6b-int8-v1`.

Fallback de compatibilidade: Qwen oficial FP16 via vLLM/Transformers, somente
se o ONNX INT8 falhar; vLLM CPU/ARM64 é uma opção condicional e mais pesada.

## Fases de implementação

1. **Preflight e pinagem**
   - Fixar revisões e SHA-256 de pesos, tokenizer e imagens.
   - Confirmar `aarch64`, Podman, espaço livre, portas privadas e firewall.
   - Manter cache em volumes Podman nomeados; não usar cópia temporária para
     modelo ou chave.

2. **Canary isolado**
   - Um container de embedding e um de reranker por vez, bind apenas na rede
     privada OCI.
   - Não publicar NodePort, Ingress, Cloudflare ou alias público.
   - Usar `0.5 CPU` por container e memory limit inicial de 4 GiB para o
     embedding; ajustar o reranker após medir o RSS real.

3. **Gates funcionais e de qualidade**
   - `/health`, `/embed`, `/rerank`, batch 1 e batch 4.
   - Dimensão efetiva 1024 e, se suportado pelo endpoint, teste explícito de
     768; comparar semântica, não apenas o tamanho do JSON.
   - Corpus PT-BR fixo: perguntas, documentos relevantes, irrelevantes,
     acentos, código e contexto longo.
   - Gate de consistência: cosine batch/single >= 0.99 e fingerprint estável;
     gate de ranking: documento correto em primeiro ou dentro do N definido.
   - Medir CPU-seconds por 1.000 tokens, p95, RSS e erro sob 0.5 CPU. O ganho
     de velocidade não compensa inconsistência vetorial.

4. **Qdrant e pipeline**
   - Criar coleção Qwen com dimensão efetiva e distância iguais ao endpoint.
   - Indexar uma amostra, comparar Recall@K/nDCG@K contra GTE, depois executar
     reembedding completo somente após aprovação.
   - Pipeline: embed query -> Qdrant top-20 -> rerank -> top-5/10. O reranker
     nunca recebe o corpus inteiro.

5. **Governor/router**
   - Adicionar os dois aliases à allowlist do `embeddinggovernor`.
   - Aplicar admission control por modelo, workload, caracteres/tokens e
     documentos; rejeitar >20 documentos antes do backend.
   - Registrar dois channels privados, sem expor endpoint do modelo diretamente.
   - Configurar fallback explícito para GTE e rollback por alias, sem alterar a
     coleção ou o alias GTE existente.

6. **Escala controlada**
   - Embedding: 1 container de 500m no canary e produção inicial.
   - Reranker: 2 containers de 500m no mínimo (`1000m`), podendo testar 4
     (`2000m`) apenas com headroom de RAM/CPU medido.
   - Não executar simultaneamente todos os máximos GTE + Qwen sem uma política
     de teto agregado; no host de 4 CPUs, Qwen embedding + 4 rerankers já
     consome `2500m` de quota explícita antes dos demais serviços.

## Critério de promoção

Promover Qwen somente se: (a) o artifact passa health e batch; (b) os vetores
são consistentes; (c) o ranking PT-BR não piora o baseline na métrica definida;
(d) o custo de CPU total é aceitável; (e) Qdrant foi reindexado em coleção
separada; e (f) router/governor, observabilidade e rollback foram testados.

Se qualquer gate falhar, manter GTE em produção, registrar o motivo e testar o
fallback FP16 ou outro runtime sem mudar o tráfego principal.
