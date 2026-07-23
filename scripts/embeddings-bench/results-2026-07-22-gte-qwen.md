# Benchmark GTE x Qwen3-Embedding-0.6B INT8

Data: 2026-07-22. Execução direta nos endpoints privados, sem alteração de rota
de produção. Todos os runtimes foram limitados a `500m`; Qwen usou Podman
rootless em `atius-srv-1`, imagem TEI ARM64, `janni-t/qwen3-embedding-0.6b-int8-tei-onnx`,
`--pooling mean`, um thread e memória de 4 GiB. O GTE foi o Deployment atual
`tei-gte`, TEI ARM64, `Alibaba-NLP/gte-multilingual-base`, 768d.

## Correção

| Runtime | Dimensão | Norma L2 | Cosine single/batch | Busca semântica em português |
|---|---:|---:|---:|---|
| GTE atual | 768 | 0.99999998–1.00000003 | 1.00000003 | top=doc 0 |
| Qwen INT8 | 1024 | 0.99999997–1.00000002 | 0.99999995 | top=doc 0 |
| Qwen INT8 | 768 | 0.99999998–1.00000004 | 0.99999997 | top=doc 0 |

## Desempenho pareado

CPU e latência foram medidos no mesmo corpus determinístico. A unidade de CPU
abaixo é CPU-segundos por 1.000 palavras de entrada; não é token-normalizada.

| Perfil | GTE 768 CPU s/1k palavras | Qwen 1024 CPU s/1k | Qwen 768 CPU s/1k | GTE p50 | Qwen 1024 p50 | Qwen 768 p50 |
|---|---:|---:|---:|---:|---:|---:|
| interactive, 64w x 1 | 18.90 | 15.84 | 15.91 | 2.171s | 1.887s | 1.907s |
| batch, 128w x 4 | 16.93 | 17.01 | 16.84 | 16.162s | 15.910s | 15.668s |
| sustained, 128w x 1 | 17.10 | 16.81 | 16.70 | 4.083s | 3.977s | 4.032s |

Memória observada: GTE working set máximo de 1,93 GiB e pico cgroup de 8,25
GiB; Qwen INT8 ficou em 1,37–1,40 GiB de memória corrente. O pico cgroup do
GTE inclui o warmup e não deve ser comparado diretamente ao `podman stats`
corrente do Qwen.

## Stress longo e disponibilidade

Foi tentado o perfil GTE de 512 palavras. As requisições levaram cerca de
17–20s sob `500m`; o liveness probe atual (`timeoutSeconds=5`) falhou e o
kubelet reiniciou o container. Portanto não há número válido de desempenho
para 512 palavras no GTE atual; este é um limite operacional real da
configuração, não uma falha de correção do modelo. O perfil comparável foi
reduzido para 128 palavras e 3 rodadas.

## Decisão desta medição

- Qwen INT8 funciona no TEI ARM64 via Podman com `--pooling mean`, retorna
  1024 ou 768 dimensões e passou as verificações de normalização, lote e
  semântica.
- Reduzir a saída de 1024 para 768 quase não reduziu CPU ou memória neste
  artefato: a diferença ficou dentro da variação do teste. 768 economiza
  25% de armazenamento vetorial; 1024 oferece 33,3% mais coordenadas.
- No perfil interativo, Qwen foi aproximadamente 16% menor em CPU que o GTE
  medido agora. Em batch e sustained ficaram praticamente empatados; não há
  evidência para trocar o GTE apenas por economia de CPU.
- Para a arquitetura atual, o Qwen 768 é a opção de menor armazenamento sem
  perda operacional observada; Qwen 1024 deve ser escolhido somente se a
  qualidade/recall do índice justificar os 33,3% extras.

O canary Podman foi removido após a coleta; o volume de cache foi preservado.
O GTE Deployment não foi alterado nem escalado.
