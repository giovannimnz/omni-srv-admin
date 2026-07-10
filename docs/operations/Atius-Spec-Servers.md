# Atius-Spec-Servers — Especificações dos Servidores ATIUS

> **DOCUMENTO SUBSTITUÍDO EM 2026-06-16.**
>
> **Leia o novo documento canônico:**
> [[ATIUS-FLEET-NETWORK-PORT-MAP]] (em `30-RECURSOS/operations/`)
>
> Este arquivo é mantido apenas como histórico. Está desatualizado e não representa
> a regra operacional atual de CPU.

---

> **Regra de Ouro (2026-07-06):** Por padrão, build/processo de build no SRV Linux
> não pode ultrapassar **20% do CPU total do host**. Use este arquivo apenas como registro histórico.

## Especificações Comuns (válido, OS desatualizado)

Todas as 3 máquinas são Oracle OCI Ampere A1 (ARM64).

| Parâmetro | Valor |
|---|---|
| Shape | VM.Standard.A1.Flex |
| Arquitetura | ARM64 / aarch64 |
| CPU | Ampere Altra (4 vCPUs, 1 thread/core) |
| RAM total | **23,42 GiB** (24.556.000 kB) |
| Swap total | **10,00 GiB** (10.485.756 kB) |
| Disco real | **186,26 GiB** (200 GB nominal) |
| Tipo de disco | Oracle Block Volume (rotational=1, HDD-backed) |
| Escrita máxima | 108 MB/s (SRV-1) a 124 MB/s (SRV-2) |
| SO | ~~Ubuntu 22.04.5 LTS~~ **Ubuntu 24.04.4 LTS** (atualizado 2026-06) |

## Regra Antiga Revogada

O antigo limite generico de 50% por processo nao e mais a politica padrao.
Para builds, rebuilds, compiles, container builds, bundlers, broad indexers e
testes pesados, a regra ativa e **20% do CPU total do host** via
`resource-governor`.

## Servidores (dados de disco ainda válidos)

| Máquina | IP Público | IP VPN | Disco usado | RAM disp. | Write max |
|---|---|---|---|---|---|
| **SRV-1** | 137.131.190.161 | 10.1.1.1 | **95%** (12G livre) | ~8,5 GiB | 108 MB/s |
| **SRV-2** | 129.148.47.32 | 10.1.1.2 | **71%** (58G livre) | ~17 GiB | 124 MB/s |
| **SRV-3** | 136.248.126.12 | 10.1.1.7 | **97%** (7,8G livre) | ~17 GiB | ~108 MB/s |

## Exemplo Prático (legado)

```bash
# Build moderno: usar o profile builds, limitado a 20% do CPU total do host.
omni srv1-ops resources run builds -- <comando-de-build>
```

Observação: para builds modernos, a regra ativa é 20% de CPU do host via `resource-governor` (ver doc canônico).

## Ver também

- [[ATIUS-FLEET-NETWORK-PORT-MAP]] — doc canônico consolidado
- `docs/operations/ATIUS-FLEET-NETWORK-PORT-MAP.md` no repo
- `inventory/hosts/*.yaml` — fonte de verdade por host
