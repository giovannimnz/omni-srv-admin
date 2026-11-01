# Matriz Canônica de IPs Públicos OCI da Frota ATIUS

**Data da Auditoria:** 2026-11-01  
**Autor:** Worker `[oci-admin + omni] - Server Cluster Config` (`a81e7d09-9393-4a1e-bc94-a15be067f958`)  
**Homologação:** Orchestrator Soberano `Orch - [omni-srv-admin]` (`1db8d421-5cba-48c9-a245-ba475f0899cb`)  
**Mecanismo de Inspeção:** OCI Python SDK 2.179.0 autenticado contra todas as 6 tenancies OCI via `atius-srv-3`.

---

## 1. Tabela Consolidada de IPs Públicos e Privados

| Host | Tenancy OCI | Compartment | Private IP | Public IP | Lifetime | Lifecycle State | Função / Identificador |
|---|---|---|---|---|---|---|---|
| **atius-srv-1** | `atius1` | `atiuscapital1` | `10.0.0.38` | `137.131.190.161` | **EPHEMERAL** | ASSIGNED | Primário (Edge Gateway / Ingress Cloudflare / Apache) |
| **atius-srv-1** | `atius1` | `atiuscapital1` | `10.0.0.238` | `137.131.140.20` | **RESERVED** | ASSIGNED | Secundário (`dns-casa-public`) |
| **atius-srv-1** | `atius1` | `atiuscapital1` | `10.0.0.236` | `64.181.180.167` | **RESERVED** | ASSIGNED | Secundário (`atius-srv-1-ssh-wsl-public`) |
| **atius-srv-1** | `atius1` | `atiuscapital1` | `10.0.0.237` | `147.15.109.140` | **RESERVED** | ASSIGNED | Secundário (`atius-srv-1-ssh-s23-public`) |
| **atius-srv-1** | `atius1` | root (`atius1`) | - | `163.176.130.211` | **RESERVED** | AVAILABLE | Reserva livre no pool (`ip-atius-srv-1-reserved-phase15`) |
| **atius-srv-2** | `atius2` | `atiuscapital2` | `10.0.0.197` | `129.148.47.32` | **EPHEMERAL** | ASSIGNED | Primário (SSH / OS) |
| **atius-srv-2** | `atius2` | `atiuscapital2` | `10.0.0.102` | `64.181.185.218` | **RESERVED** | ASSIGNED | Secundário VNIC MT5 (`ip-atius-mt5`) |
| **atius-srv-3** | `atius3` | root (`atius3`) | `10.0.0.154` | `136.248.126.12` | **EPHEMERAL** | ASSIGNED | Primário (SSH / OS) |
| **atius-srv-3** | `atius3` | root (`atius3`) | - | `163.176.178.228` | **RESERVED** | AVAILABLE | Reserva livre no pool (`ip-atius-srv-3-reserved-phase15`) |
| **atius-srv-4** | `atius4` | root (`atius4`) | `10.14.1.14` | `164.152.48.22` | **RESERVED** | ASSIGNED | VNIC Única (100% RESERVED - modelo canônico de referência) |
| **horistic-srv** | `horistic` | root (`horistic`)| `10.0.0.65` | `163.176.232.119` | **RESERVED** | ASSIGNED | Primário (100% RESERVED) |
| **aln-srv** | `alnrec` | root (`alnrec`) | `10.9.1.9` | `168.75.68.41` | **RESERVED** | ASSIGNED | Secundário VNIC (`aln-srv-10-9-1-reserved-public-ip`) |
| **aln-srv** | `alnrec` | root (`alnrec`) | `10.31.1.17` | `147.15.40.118` | **EPHEMERAL** | ASSIGNED | Primário VNIC |
| **aln-srv** | `alnrec` | root (`alnrec`) | - | `168.138.136.251` | **RESERVED** | AVAILABLE | **JÁ RESERVADO!** Reserva livre no pool (`aln-srv-ip-1`) |

---

## 2. Veredito Técnico de Infraestrutura OCI (IP Efêmero vs Reservado)

### 2.1 Impossibilidade de Conversão In-Place
Conforme especificação formal da documentação da Oracle Cloud Infrastructure:
> *"After you create a given public IP object, you can't change which type it is. Therefore, if you launch an instance and assign it an ephemeral public IP with address 203.0.113.2, you can't convert the ephemeral public IP to a reserved public IP with address 203.0.113.2."*
> — *Oracle Cloud Documentation: Managing Public IP Addresses (`managingpublicIPs.htm`)*

Foi executado teste de validação via API REST nativa com assinatura criptográfica (`Signer` OCI) no endpoint `PUT /publicIps/{id}` passando `{"lifetime": "RESERVED"}`. A API aceita a atualização de metadados (`displayName`), mas **ignora** qualquer alteração de `lifetime`, mantendo o IP com `lifetime: EPHEMERAL` e `scope: AVAILABILITY_DOMAIN`.

### 2.2 Salvaguarda Absoluta contra Perda de IP
1. **Risco Crítico:** Desanexar ou excluir `137.131.190.161` na VNIC do `atius-srv-1` devolveria o endereço IP imediatamente para o pool público da Oracle Cloud, inviabilizando qualquer recuperação.
2. **Diretriz Homologada pelo ORCH:** O IP público `137.131.190.161` **NÃO DEVE** sofrer desanexação prévia nem tentativas de recriação in-place.
3. **Plano de Cutover Seguro:** O `atius-srv-1` já dispõe no seu pool da reserva persistente `163.176.130.211` (além do IP secundário reservado `137.131.140.20`). A transição para VNIC Única ocorrerá mediante apontamento coordenado no Cloudflare DNS no momento do cutover, garantindo zero perda de tráfego.
4. **Alinhamento do aln-srv:** O IP `168.138.136.251` já se encontra em estado `RESERVED` e `AVAILABLE` no pool da tenancy `alnrec`, pronto para associação direta.
