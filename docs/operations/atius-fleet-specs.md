# ATIUS Fleet — Fleet Specs (Specs das Máquinas)

> **DOCUMENTO SUBSTITUÍDO EM 2026-06-16.**
>
> **Leia o novo documento canônico:**
> [[ATIUS-FLEET-NETWORK-PORT-MAP]] (em `30-RECURSOS/operations/`)
>
> Este arquivo é mantido apenas como histórico (já que tem specs de
> I/O write max e tabelas de disco que foram validadas em 2026-05-04).
> Está desatualizado quanto a OS (diz 22.04, real é 24.04) e não
> cobre o pool de displays :5..9, nem o estado pós-Phase 18.

---

## Especificações comuns (válido, OS desatualizado)

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
| OS | ~~Ubuntu 22.04.5 LTS~~ **Ubuntu 24.04.4 LTS** (atualizado 2026-06) |
| Kernel | ~~6.8.0-1050-oracle~~ **6.17.x-oracle** (atualizado 2026-06) |

## Máquinas (dados de disco ainda válidos)

| Máquina | IP Público | IP VPN | Disco usado | RAM disp. | Write max | 85% safe |
|---|---|---|---|---|---|---|
| **SRV-1** | 137.131.190.161 | 10.1.1.1 | **95%** (12G livre) | ~8.5 GiB | **108 MB/s** | **92 MB/s** |
| **SRV-2** | 129.148.47.32 | 10.1.1.2 | **71%** (58G livre) | ~17 GiB | **124 MB/s** | **105 MB/s** |
| **SRV-3** | 136.248.126.12 | 10.1.1.7 | **97%** (7.8G livre) | ~17 GiB | ~108 MB/s | ~92 MB/s |

## Conversões

- MemTotal: 24,556,000 kB = **23.42 GiB**
- SwapTotal: 10,485,756 kB = **10.00 GiB**
- Disco (200 GB nominal): 200 × 10⁹ ÷ 1024³ = **186.26 GiB**
- 85% write limit SRV-1: 108 × 0.85 = **92 MB/s**
- 85% write limit SRV-2: 124 × 0.85 = **105 MB/s**

## I/O Limiting

Para operações pesadas (backup, cleanup), usar:
```bash
ionice -c 2 -n 7 nice -n 19 <comando>
```
Ou com rate limiter absoluto via `pv`:
```bash
tar cf - <dir> | pv -q -L 80M -W > output.tar
```

## Ver também

- [[ATIUS-FLEET-NETWORK-PORT-MAP]] — doc canônico (rede, IPs, portas, displays)
- `docs/operations/ATIUS-FLEET-NETWORK-PORT-MAP.md` no repo omni-srv-admin
- `inventory/hosts/atius-srv-{1,2,3}.yaml` — fonte de verdade por host
