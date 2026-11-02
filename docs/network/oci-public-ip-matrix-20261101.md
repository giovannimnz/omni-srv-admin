# Matriz Canônica de IPs Públicos OCI da Frota ATIUS (100% RESERVED)

**Data da Auditoria e Cutover:** 2026-11-01  
**Autor:** Worker `[oci-admin + omni] - Server Cluster Config` (`a81e7d09-9393-4a1e-bc94-a15be067f958`)  
**Homologação:** Orchestrator Soberano `Orch - [omni-srv-admin]` (`1db8d421-5cba-48c9-a245-ba475f0899cb`)  
**Status da Frota:** **100% RESERVED** (Zero IPs efêmeros em operação)

---

## 1. Tabela Definitiva de IPs Públicos e Privados

| Host | Tenancy OCI | Compartment | Private IP | Public IP | Lifetime | Lifecycle State | Função / Identificador |
|---|---|---|---|---|---|---|---|
| **atius-srv-1** | `atius1` | `atiuscapital1` | `10.0.0.38` | **`64.181.172.236`** | **RESERVED** | ASSIGNED | **Primário** (`ip-atius-srv-1-reserved-primary` - Edge Gateway / Ingress Cloudflare / Apache) |
| **atius-srv-1** | `atius1` | `atiuscapital1` | `10.0.0.238` | `137.131.140.20` | **RESERVED** | ASSIGNED | Secundário (`dns-casa-public`) |
| **atius-srv-1** | `atius1` | `atiuscapital1` | `10.0.0.236` | `64.181.180.167` | **RESERVED** | ASSIGNED | Secundário (`atius-srv-1-ssh-wsl-public`) |
| **atius-srv-1** | `atius1` | `atiuscapital1` | `10.0.0.237` | `147.15.109.140` | **RESERVED** | ASSIGNED | Secundário (`atius-srv-1-ssh-s23-public`) |
| **atius-srv-1** | `atius1` | root (`atius1`) | - | `163.176.130.211` | **RESERVED** | AVAILABLE | Reserva livre no pool (`ip-atius-srv-1-reserved-phase15`) |
| **atius-srv-2** | `atius2` | `atiuscapital2` | `10.0.0.197` | **`163.176.55.228`** | **RESERVED** | ASSIGNED | **Primário** (`ip-atius-srv-2-reserved-primary` - SSH / OS) |
| **atius-srv-2** | `atius2` | `atiuscapital2` | `10.0.0.102` | `64.181.185.218` | **RESERVED** | ASSIGNED | Secundário VNIC MT5 (`ip-atius-mt5`) |
| **atius-srv-3** | `atius3` | root (`atius3`) | `10.0.0.154` | **`150.230.71.10`** | **RESERVED** | ASSIGNED | **Primário** (`ip-atius-srv-3-reserved-primary` - SSH / OS / Vault / Landscape) |
| **atius-srv-3** | `atius3` | root (`atius3`) | - | `163.176.178.228` | **RESERVED** | AVAILABLE | Reserva livre no pool (`ip-atius-srv-3-reserved-phase15`) |
| **atius-srv-4** | `atius4` | root (`atius4`) | `10.14.1.14` | **`164.152.48.22`** | **RESERVED** | ASSIGNED | VNIC Única (100% RESERVED - modelo canônico de referência) |
| **horistic-srv** | `horistic` | root (`horistic`)| `10.0.0.65` | **`163.176.232.119`** | **RESERVED** | ASSIGNED | **Primário** (100% RESERVED) |
| **aln-srv** | `alnrec` | root (`alnrec`) | `10.31.1.17` | **`168.138.136.251`** | **RESERVED** | ASSIGNED | **Primário** (`aln-srv-ip-1` - 100% RESERVED) |
| **aln-srv** | `alnrec` | root (`alnrec`) | `10.9.1.9` | `168.75.68.41` | **RESERVED** | ASSIGNED | Secundário VNIC (`aln-srv-10-9-1-reserved-public-ip`) |

---

## 2. Sincronização de DNS Cloudflare

- **Zona `atius.com.br` (`a2cbd24e16387b6b5b51699efdd23277`):**
  - 42 registros A apontados anteriormente para `137.131.190.161` foram atualizados para `64.181.172.236`.
  - Registros de `atius-srv-2` (`129.148.47.32`) foram atualizados para `163.176.55.228`.
- **Zona `atius.io` (`c1d167941f7841f3c893669a76a057c7`):**
  - 24 registros A apontados anteriormente para `137.131.190.161` foram atualizados para `64.181.172.236`.
- **Validação de Ingress HTTP/2:**
  - `https://admin.atius.com.br` $\rightarrow$ `HTTP/2 307` (Redirecionamento para Atius SSO validado).
  - `https://mcp.atius.com.br/gbrain` $\rightarrow$ `HTTP/2 403` (Edge Gateway ativo, autenticação exigida).

---

## 3. Conectividade SSH e Ferramental de Operação

- Arquivo `~/.ssh/config` atualizado com as novas entradas primárias reservadas.
- Todos os 6 hosts validados com sucesso via SSH direto.
- Subordinação ao Orchestrator Central (`1db8d421-5cba-48c9-a245-ba475f0899cb`) e alinhamento com Worker 9 (`28eec252-459e-4fe4-81bf-ae7f936cc008`) confirmados.
