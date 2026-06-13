# Atius-Spec-Servers — Especificações dos Servidores ATIUS

> **Regra de Ouro:** Nenhum processo, container, programa ou serviço pode consumir mais de **50%** de qualquer recurso da máquina.

## Especificações Comuns

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
| SO | Ubuntu 24.04.4 LTS |
| Kernel | 6.17.0-1016-oracle |
| Snapshot atual | 2026-06-13 M005 execution checkpoint |

## Limite de 50% por Processo

| Recurso | 100% | 50% máximo | Docker | Systemd |
|---|---|---|---|---|
| CPU | 4 vCPUs | **2 vCPUs** | `--cpus=2` | `CPUQuota=200%` |
| RAM | 23,42 GiB | **11,71 GiB** | `--memory=11.7g` | `MemoryMax=11991M` |
| Swap | 10,00 GiB | **5,00 GiB** | `--memory-swap=16.7g` | — |
| Write (SRV-1) | 108 MB/s | **54 MB/s** | — | `IOWriteBandwidthMax=/dev/sda 54M` |
| Write (SRV-2) | 124 MB/s | **62 MB/s** | — | `IOWriteBandwidthMax=/dev/sda 62M` |
| Read | ~120 MB/s | **~60 MB/s** | — | `IOReadBandwidthMax=/dev/sda 60M` |
| Armazenamento | 186,26 GiB | **93,13 GiB** | `--storage-opt size=93G` | — |

## Servidores

| Máquina | IP Público | IP VPN | Disco usado | RAM disp. | Write max | 50% write |
|---|---|---|---|---|---|---|
| **SRV-1** | 137.131.190.161 | 10.1.1.1 | **70%** (60G livre) | ~10 GiB | 108 MB/s | **54 MB/s** |
| **SRV-2** | 129.148.47.32 | 10.1.1.2 | **70%** (60G livre) | ~18 GiB | 124 MB/s | **62 MB/s** |
| **SRV-3** | 136.248.126.12 | 10.1.1.7 | **30%** (137G livre) | ~21 GiB | ~108 MB/s | **~54 MB/s** |

## K3s M005 Notes

- Rede de cluster escolhida: WireGuard `wg0` / `10.1.1.0/24`.
- Fallback PTP full-mesh planejado em `13-02-PLAN.md`; nao ha portas/IPs novos reservados ainda.
- SRV-1 ainda tem `/swapfile` ativo; desabilitar e persistir `swapoff` antes do install K3s.
- SRV-2 e SRV-3 nao reportaram swap ativo no checkpoint de 2026-06-13.

## Exemplo Prático

```bash
# Container com 50% máximo
docker run --cpus=2 --memory=11.7g --memory-swap=16.7g ...

# Systemd scope com 50%
systemd-run --user --scope -p CPUQuota=200% -p MemoryMax=11991M \
  -p IOWriteBandwidthMax='/dev/sda 54M' <comando>
```

Documentação completa no Obsidian: `30-RECURSOS/atius/Atius-Spec-Servers.md`
