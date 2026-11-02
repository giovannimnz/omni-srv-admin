# Plano Mestre de Reendereçamento IPAM DRG e Unificação VNIC Única (10.1 - 10.4 & Parceiros 10.51 - 10.52)

**Data:** 2026-11-02  
**Status:** Planejado, Contratado no `oci-admin` e Homologado via TDD (24/24 Testes Verdes)  
**Branch OCI Admin:** `feature/drg-vnic-unica-ipam-10-1` (Commit `09efdf6`)  
**Sessão Operacional:** Worker 5 (`[oci-admin + omni] - Server Cluster Config` — `a81e7d09-9393-4a1e-bc94-a15be067f958`)  
**Orquestrador Central:** `Orch - [omni-srv-admin]` (`1db8d421-5cba-48c9-a245-ba475f0899cb`)  

---

## 1. Resumo Executivo e Nova Matriz de Endereçamento

A frota ATIUS concluiu a etapa de **100% Reserved Public IPs** (zero IPs efêmeros) e agora avança para a padronização definitiva da malha de rede privada via Oracle Cloud Infrastructure (OCI) Dynamic Routing Gateway (DRG) e unificação para VNIC Única.

A alocação de blocos VCN foi reordenada para seguir faixas puras, eliminando a dependência histórica de prefixos legados:

| Host | Perfil OCI | Grupo | VCN CIDR Alvo | Subnet Servidores | IP Host Estável | Subnet Serviços | IP Público Reservado (Ativo) |
|---|---|---|---|---|---|---|---|
| `atius-srv-1` | `atius1` | ATIUS | `10.1.0.0/16` | `10.1.0.0/24` | `10.1.0.11` | `10.1.2.0/24` | `64.181.172.236` |
| `atius-srv-2` | `atius2` | ATIUS | `10.2.0.0/16` | `10.2.0.0/24` | `10.2.0.12` | `10.2.2.0/24` | `163.176.55.228` |
| `atius-srv-3` | `atius3` | ATIUS | `10.3.0.0/16` | `10.3.0.0/24` | `10.3.0.13` | `10.3.2.0/24` | `150.230.71.10` |
| `atius-srv-4` | `atius4` | ATIUS | `10.4.0.0/16` | `10.4.0.0/24` | `10.4.0.14` | `10.4.2.0/24` | `164.152.48.22` |
| `horistic-srv` | `horistic` | non-ATIUS (Parceiro) | `10.51.0.0/16` | `10.51.0.0/24` | `10.51.0.51` | `10.51.2.0/24` | `163.176.232.119` |
| `aln-srv` | `alnrec` | non-ATIUS (Parceiro) | `10.52.0.0/16` | `10.52.0.0/24` | `10.52.0.52` | `10.52.2.0/24` | `168.138.136.251` |

---

## 2. Restrições Arquiteturais Rígidas da Oracle Cloud (OCI)

Durante os testes empíricos de validação via OCI SDK contra a API ao vivo de `sa-saopaulo-1`, comprovamos com evidência de erro HTTP as seguintes regras determinísticas:

1. **Reserva do Primeiro IP (`network + 1`):**
   - O endereço `.1` de qualquer subnet (ex: `10.1.0.1` em `10.1.0.0/24`) é **obrigatoriamente reservado pela Oracle** para o **Virtual Router (Default Gateway)** da subnet.
   - Qualquer tentativa de associar `.1` a uma VNIC ou instância retorna:
     ```text
     400 - InvalidParameter - The requested privateIp 10.1.0.1 is invalid: IP v4 Address is reserved.
     ```
2. **Reserva do Segundo IP (`network + 2`):**
   - O endereço `.2` de qualquer subnet (ex: `10.2.0.2` em `10.2.0.0/24`) é **alocado automaticamente para o Oracle DNS Resolver**.
   - Qualquer tentativa de criar esse IP privado retorna:
     ```text
     409 - Conflict - The IP address 10.2.0.2 has already been allocated for the Subnet ...
     ```
3. **Resolução de Engenharia Adotada:**
   - Na Subnet `10.1.0.0/24`:
     - Gateway da Subnet: `10.1.0.1` (o que satisfaz a referência natural de gateway da rede).
     - DNS da Subnet: `10.1.0.2`.
     - Host IP Primário da Instância: `10.1.0.11` (para srv-1), `10.2.0.12` (para srv-2), `10.3.0.13` (para srv-3), `10.4.0.14` (para srv-4), `10.51.0.51` (horistic) e `10.52.0.52` (aln).

---

## 3. Implementação e Contratos TDD no `oci-admin`

Os contratos foram atualizados e commitados na branch `feature/drg-vnic-unica-ipam-10-1` (`09efdf6`):

1. **`app/oci_client/peering_actions.py`:**
   - `_TARGET_ADDRESS_ROWS`: Atualizado para conter os 6 servidores da frota com as novas faixas `10.1.0.0/16` a `10.4.0.0/16` e `10.51.0.0/16` / `10.52.0.0/16`.
   - `_EXCLUDED_BLOCKS`: Removido `"10.1.0.0/16"` da lista de exclusão (anteriormente bloqueado por colisão com a antiga WireGuard).
   - `reservations`: Atualizado `atius.first_vcn_cidr="10.1.0.0/16"` e `non_atius.first_vcn_cidr="10.51.0.0/16"`.
2. **Testes Validados (24/24 PASS):**
   - `tests/test_peering_addressing.py`: 7 passed.
   - `tests/test_peering_drg.py`: 9 passed.
   - `tests/test_peering_routes.py`: 5 passed.
   - `tests/test_cli_peering.py`: 3 passed.

---

## 4. Execução Live Concluída (Waves 1 e 2 Homologadas ao Vivo)

### Wave 1 — Provisionamento da VCN Alvo (`vcn-atius1` em `10.1.0.0/16`) — CONCLUÍDO (100%)
- **VCN `vcn-atius1`:** `10.1.0.0/16` (DNS: `peeratius1`) | OCID: `ocid1.vcn.oc1.sa-saopaulo-1.amaaaaaa7yjj2jaardezfkdz7b2tnzkzylzbllge5n66etayenzkbmofozba`
- **Internet Gateway:** `igw-vcn-atius1` | OCID: `ocid1.internetgateway.oc1.sa-saopaulo-1.aaaaaaaajzq5y7pfudxjnnhtsqzcugaeklek44dswgkfqlwjipxpnnqslpxa`
- **Route Table:** `route-table-atius1-core` (`0.0.0.0/0` -> IGW; rotas de retorno e malha DRG -> DRG Hub `Brasil - Sao Paulo`) | OCID: `ocid1.routetable.oc1.sa-saopaulo-1.aaaaaaaaktbpcztuh2qjskllczd23foluzv2ayibxulqrhfszry645ylfueq`
- **Security List:** `security-list-atius1-core` (regras completas para SSH 22, HTTP 80, HTTPS 443, XRDP 3389, MOSH 60001-60999 UDP, ICMP MTU/Ping, DRG Mesh `10.0.0.0/8` e WireGuard `10.100.100.0/24`) | OCID: `ocid1.securitylist.oc1.sa-saopaulo-1.aaaaaaaaarbyln7nnlh2ufl5kjicv75tacymfe3n3xvmhq4vsoq23q4mb3da`
- **Subnet Servidores:** `subnet-atius1` (`10.1.0.0/24`, Gateway: `10.1.0.1`, DNS: `10.1.0.2`, Pública) | OCID: `ocid1.subnet.oc1.sa-saopaulo-1.aaaaaaaa4d3sj64eyu2zlkyj7rxj33blbtgc3cteuzkwewghmltioc2w2aoq`
- **Subnet Serviços:** `subnet-atius1-service` (`10.1.2.0/24`, Pública) | OCID: `ocid1.subnet.oc1.sa-saopaulo-1.aaaaaaaa5ajvez65am45mafzd4j6vffx3kfqy4obu46mybzouv66agjw4eta`
- **DRG Attachment:** `drg-attachment-vcn-atius1` associado ao DRG Hub `Brasil - Sao Paulo` (`ocid1.drg.oc1.sa-saopaulo-1.aaaaaaaapkv4lkgvhwkumakeq5pbdnbe32hbp2zai2mhe7d7pzwk7x774zqa`) | OCID: `ocid1.drgattachment.oc1.sa-saopaulo-1.aaaaaaaaskedpl7gpdfwp675s7aajdth6xgkadfuw2d5rgb6fuwztnnukk4q` (`ATTACHED`)
- **Propagação Dinâmica:** `10.1.0.0/24` e `10.1.2.0/24` propagados dinamicamente para o DRG Hub.

### Wave 2 — Anexação da VNIC e Homologação da Malha Privada e Pública — CONCLUÍDO (100%)
- **Anexação de VNIC:** Anexada VNIC `vnic-atius1-core-10-1` na instância `atius-srv-1` (`ocid1.instance.oc1.sa-saopaulo-1.antxeljr7yjj2jacsuaeho7denrimjq3rcdwiu6tquznfyzojh3y6gp6byxa`).
  - VNIC OCID: `ocid1.vnic.oc1.sa-saopaulo-1.abtxeljr5dgajhrnrjmnfjx7a4k6mvzc3sz7atdyfkbynrrovlkxjbu2njfa`
  - Private IP: `10.1.0.11` (`ocid1.privateip.oc1.sa-saopaulo-1.abtxeljrxr5mnzrpzfmyhcis3kpuvfd6c7dlnjq6vdwf6r6zwokx5bcarnya`)
  - MAC Address: `02:00:17:06:ed:dc`
- **Configuração no Host Linux (`atius-srv-1`):**
  - Interface reconhecida como `enp2s0`.
  - Persistida e aplicada em `/etc/netplan/62-oci-target-vnic.yaml` com tabela de roteamento de política (PBR) `101`:
    - `ip route add default via 10.1.0.1 dev enp2s0 table 101`
    - `ip rule add from 10.1.0.11 lookup 101 proto static`
  - Ping local para Gateway `10.1.0.1`: **0.235 ms RTT, 0% packet loss**.
- **Atualização das Tabelas de Rota e Security Lists em Toda a Frota OCI:**
  - `atius-srv-2`: RT `10.1.0.0/16 -> DRG` atualizada; Netplan persistido com rota estática `10.1.0.0/16 via 10.12.1.1 dev enp2s0`.
  - `atius-srv-3`: RT `10.1.0.0/16 -> DRG` atualizada; Netplan persistido com rota estática `10.1.0.0/16 via 10.13.1.1 dev enp1s0`.
  - `atius-srv-4`: RT `10.1.0.0/16 -> DRG` atualizada; Security List atualizada autorizando `10.1.0.0/16`.
  - `horistic-srv`: RT `10.1.0.0/16 -> DRG` atualizada; Security List atualizada autorizando `10.1.0.0/16`; Netplan persistido com rota estática `10.1.0.0/16 via 10.21.1.1 dev enp1s0`.
  - `aln-srv`: RT `10.1.0.0/16 -> DRG` atualizada; Security List atualizada autorizando `10.1.0.0/16`.
- **Validação de Conectividade DRG Fleet-Wide (100% PASS, 0% packet loss):**
  - `10.1.0.11` $\rightarrow$ `atius-srv-2` (`10.12.1.12`): **0.585 ms RTT**
  - `10.1.0.11` $\rightarrow$ `atius-srv-3` (`10.13.1.13`): **0.608 ms RTT**
  - `10.1.0.11` $\rightarrow$ `atius-srv-4` (`10.14.1.14`): **0.639 ms RTT**
  - `10.1.0.11` $\rightarrow$ `horistic-srv` (`10.21.1.21`): **0.686 ms RTT**
  - `10.1.0.11` $\rightarrow$ `aln-srv` (`10.31.1.17`): **0.635 ms RTT**
- **Validação de Ingress e Egress de Internet Pública (100% PROVADO):**
  - Associação temporária do IP Público Reservado `163.176.130.211` a `10.1.0.11`.
  - `curl --interface 10.1.0.11 https://ifconfig.me` confirmou saída nativa com IP `163.176.130.211`.
  - Conexão SSH externa `ssh -i ~/.ssh/atius-srv-1_ed25519 ubuntu@163.176.130.211` confirmou entrada e shell ativo em `atius-srv-1` via `enp2s0`.
  - IP de teste desassociado com sucesso retornando para `AVAILABLE`.

---

## 5. Wave 3 — Cutover de Produção e Desativação Legada — CONCLUÍDO (100%)

Com a autorização soberana concedida pelo Orquestrador Central (`1db8d421-5cba-48c9-a245-ba475f0899cb`), o cutover de produção foi executado e homologado com zero downtime:

1. **Reatribuição do IP Público Reservado de Produção (`64.181.172.236`):**
   - O IP Reservado `64.181.172.236` (`ocid1.publicip.oc1.sa-saopaulo-1.amaaaaaa7yjj2jaajvvk63xe5jd4j4gpui25e4srrk4mmkwnfei7hpae455a`) foi transferido atomicamente da VNIC legada (`10.0.0.38`) para o IP privado alvo `10.1.0.11` (`ocid1.privateip.oc1.sa-saopaulo-1.abtxeljrxr5mnzrpzfmyhcis3kpuvfd6c7dlnjq6vdwf6r6zwokx5bcarnya`) na interface `enp2s0` da VCN `vcn-atius1`.
   - Estado: `ASSIGNED` em `10.1.0.11`.
2. **Roteamento Default no Host (`atius-srv-1`):**
   - Tabela `main` atualizada via Netplan (`/etc/netplan/62-oci-target-vnic.yaml`): `default via 10.1.0.1 dev enp2s0 metric 50`.
   - Tabela PBR `101` ativa com `from 10.1.0.11 lookup 101`.
   - Egresso público nativo verificado via `curl -s https://ifconfig.me` $\rightarrow$ retornando `64.181.172.236`.
3. **Auditoria de Conectividade Externa (100% Online):**
   - SSH externo: `ssh -i ~/.ssh/atius-srv-1_ed25519 ubuntu@64.181.172.236` conectando instantaneamente em `atius-srv-1.atius.internal`.
   - Web Edge Cloudflare:
     - `https://admin.atius.com.br`: HTTP/2 307 SSO redirect ativo.
     - `https://admin.atius.io`: HTTP/2 307 SSO redirect ativo.
   - Daemons internos: Todos os 28 processos PM2 (`atius-web`, `atius-api`, `xdriver-*`, etc.) e Apache2 ativos sem nenhuma interrupção.
4. **Sincronização de Resolução de Nomes (`/etc/hosts`) Fleet-Wide:**
   - Atualizado de `10.11.1.11` para `10.1.0.11 atius-srv-1 atius-srv-1.atius.internal` em:
     - `atius-srv-1`
     - `atius-srv-2`
     - `atius-srv-3`
     - `atius-srv-4`
     - `horistic-srv`
5. **Desanexação da Interface Legada de Transição:**
   - Configuração de Netplan antiga `/etc/netplan/61-oci-primary-vnic.yaml` removida do host.
   - VNIC Attachment legado `phase16-oci-primary-atius1` (`ocid1.vnicattachment.oc1.sa-saopaulo-1.antxeljr7yjj2jacvvikknv3hzxu2ebmkmpwpep6gnuhe5cyuawx6jf4jqlq`) desanexado com sucesso no OCI Compute.
   - Host `atius-srv-1` agora opera com sua VNIC moderna em `10.1.0.11` carregando a totalidade do tráfego público e privado DRG.


