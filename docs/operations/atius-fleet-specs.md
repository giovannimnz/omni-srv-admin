# ATIUS Fleet — Especificações das Máquinas

Todas as 3 máquinas são Oracle OCI Ampere A1 (ARM64).

## Especificações comuns

| Parâmetro | Valor |
|---|---|
| Shape | VM.Standard.A1.Flex |
| Arquitetura | ARM64 / aarch64 |
| CPU | Ampere Altra (4 vCPUs, 1 thread/core) |
| RAM | **23.42 GiB** (24,556,000 kB / 25.1 GB) |
| Swap | **10.00 GiB** (10,485,756 kB) — swapfile |
| Disco nominal | 200 GB |
| Disco real (formatado) | **186.26 GiB** |
| Tipo de disco | Oracle Block Volume (rotational=1, HDD-backed) |
| OS | Ubuntu 24.04.4 LTS |
| Kernel | 6.17.0-1016-oracle |
| Current snapshot | 2026-06-13 M005 execution checkpoint |

## Máquinas

| Máquina | IP Público | IP VPN | Disco usado | RAM disp. | Write max | 85% safe |
|---|---|---|---|---|---|---|
| **SRV-1** | 137.131.190.161 | 10.1.1.1 | **70%** (60G livre) | ~10 GiB | **108 MB/s** | **92 MB/s** |
| **SRV-2** | 129.148.47.32 | 10.1.1.2 | **70%** (60G livre) | ~18 GiB | **124 MB/s** | **105 MB/s** |
| **SRV-3** | 136.248.126.12 | 10.1.1.7 | **30%** (137G livre) | ~21 GiB | ~108 MB/s | ~92 MB/s |

## Conversões

- MemTotal: 24,556,000 kB = **23.42 GiB**
- SwapTotal: 10,485,756 kB = **10.00 GiB**
- Disco (200 GB nominal): 200 × 10⁹ ÷ 1024³ = **186.26 GiB**
- 85% write limit SRV-1: 108 × 0.85 = **92 MB/s**
- 85% write limit SRV-2: 124 × 0.85 = **105 MB/s**
- K3s network decision: WireGuard `wg0` / `10.1.1.0/24`.
- K3s PTP fallback: planned in `13-02-PLAN.md`; no new IPs/ports assigned yet.
- K3s swap gate: SRV-1 still has `/swapfile` active; disable and persist swap off before installation.

## I/O Limiting

Para operações pesadas (backup, cleanup), usar:
```bash
ionice -c 2 -n 7 nice -n 19 <comando>
```
Ou com rate limiter absoluto via `pv`:
```bash
tar cf - <dir> | pv -q -L 80M -W > output.tar
```

Documentação completa no Obsidian: `30-RECURSOS/atius/atius-fleet-specs.md`
