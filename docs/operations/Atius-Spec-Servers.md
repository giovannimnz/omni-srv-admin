# Atius-Spec-Servers — Especificações dos Servidores ATIUS

> **DOCUMENTO SUBSTITUÍDO EM 2026-06-16.**
>
> **Leia o novo documento canônico:**
> [[ATIUS-FLEET-NETWORK-PORT-MAP]] (em `30-RECURSOS/operations/`)
>
> Este arquivo é mantido apenas como histórico. Está desatualizado
> quanto a OS (diz 22.04, real é 24.04). As regras de 50% por
> processo permanecem válidas e foram incorporadas no doc canônico.

---

> **Regra de Ouro:** Nenhum processo, container, programa ou serviço
> pode consumir mais de **50%** de qualquer recurso da máquina.

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

## Limite de 50% por Processo (ainda válido)

| Recurso | 100% | 50% máximo | Docker | Systemd |
|---|---|---|---|---|
| CPU | 4 vCPUs | **2 vCPUs** | `--cpus=2` | `CPUQuota=200%` |
| RAM | 23,42 GiB | **11,71 GiB** | `--memory=11.7g` | `MemoryMax=11991M` |
| Swap | 10,00 GiB | **5,00 GiB** | `--memory-swap=16.7g` | — |
| Write (SRV-1) | 108 MB/s | **54 MB/s** | — | `IOWriteBandwidthMax=/dev/sda 54M` |
| Write (SRV-2) | 124 MB/s | **62 MB/s** | — | `IOWriteBandwidthMax=/dev/sda 62M` |
| Read | ~120 MB/s | **~60 MB/s** | — | `IOReadBandwidthMax=/dev/sda 60M` |
| Armazenamento | 186,26 GiB | **93,13 GiB** | `--storage-opt size=93G` | — |

## Servidores (dados de disco ainda válidos)

| Máquina | IP Público | IP VPN | Disco usado | RAM disp. | Write max | 50% write |
|---|---|---|---|---|---|---|
| **SRV-1** | 137.131.190.161 | 10.1.1.1 | **95%** (12G livre) | ~8,5 GiB | 108 MB/s | **54 MB/s** |
| **SRV-2** | 129.148.47.32 | 10.1.1.2 | **71%** (58G livre) | ~17 GiB | 124 MB/s | **62 MB/s** |
| **SRV-3** | 136.248.126.12 | 10.1.1.7 | **97%** (7,8G livre) | ~17 GiB | ~108 MB/s | **~54 MB/s** |

## Exemplo Prático

```bash
# Container com 50% máximo
docker run --cpus=2 --memory=11.7g --memory-swap=16.7g ...

# Systemd scope com 50%
systemd-run --user --scope -p CPUQuota=200% -p MemoryMax=11991M \
  -p IOWriteBandwidthMax='/dev/sda 54M' <comando>
```

## Ver também

- [[ATIUS-FLEET-NETWORK-PORT-MAP]] — doc canônico consolidado
- `docs/operations/ATIUS-FLEET-NETWORK-PORT-MAP.md` no repo
- `inventory/hosts/*.yaml` — fonte de verdade por host
