# 2026-10-04 — Integração de aln-srv (aln-srv-amd) à malha OCI DRG e Rede da Frota

## Resumo Executivo

A instância parceira `aln-srv-amd` (tenancy `alnrec`, shape `VM.Standard.E2.1.Micro`, AMD EPYC, região `sa-saopaulo-1`) foi plenamente integrada à malha DRG Central (`Brasil - Sao Paulo`, OCID `...774zqa`) hospedada na tenancy `atius1`.

Seguindo a lógica de convenção da frota onde os servidores centrais residem nas faixas `10.11.0.0/16` (`atius-srv-1`), `10.12.0.0/16` (`atius-srv-2`), `10.13.0.0/16` (`atius-srv-3`), `10.14.0.0/16` (`atius-srv-4`), e o nó parceiro `horistic-srv` ocupa `10.21.0.0/16` com IP `.21` (`10.21.1.21`), o servidor parceiro `aln-srv` foi integrado em:
- **Faixa VCN:** `10.31.0.0/16`
- **Subnet:** `10.31.0.0/24` (`aln-srv-subnet`)
- **IP Privado Canônico DRG:** `10.31.0.31` (atribuído como IP secundário na VNIC primária `ens3`)
- **IP Privado DHCP Original:** `10.31.0.197`
- **IP Público:** `168.138.136.251`
- **Tailscale IP:** `100.88.42.80`

A conectividade bidirecional foi validada em 100% dos nós com latência ultra-baixa (~0.5ms a 0.6ms), e o DNS interno da frota (`aln-srv.atius.internal`) foi configurado no CoreDNS do `atius-srv-1`.

---

## 1. Topologia e Identidade

| Atributo | Valor |
|---|---|
| Host / Identificador | `aln-srv` |
| Hostname no SO | `aln-srv-amd` |
| Tenancy OCI | `alnrec` (`ocid1.tenancy.oc1..aaaaaaaayiktgkyn5nzjjfkkcohplmdp2k6xccqmn56wjcfywd3pcdftqdqq`) |
| Compartment | `alnrec` (root) |
| Região | `sa-saopaulo-1` (Brasil - Sao Paulo) |
| Shape | `VM.Standard.E2.1.Micro` (1 vCPU AMD EPYC, 1 GiB RAM) |
| OS | Ubuntu 24.04 LTS (Noble Numbat) |
| Papel | Servidor parceiro (rede isolada conectada via DRG, similar a `horistic-srv`) |
| VCN | `aln-srv-vcn` (`ocid1.vcn.oc1.sa-saopaulo-1.amaaaaaa5c3asqiabdcq7hn5ft5yrtc3yehj5qtygggi2whe6iogckrmp7ka`) |
| Subnet | `aln-srv-subnet` (`ocid1.subnet.oc1.sa-saopaulo-1.aaaaaaaar666y7gq7b3gxd2r6v672c2h3mgyh5vsmc62hrcq2k26qqu667la`) |
| VNIC Primária | `ocid1.vnic.oc1.sa-saopaulo-1.abtxeljr36yff4f7ffj7qndd3lshdnhqrvt6z3b7543q56pddr2yqfq65z4q` |
| IP Secundário Canônico | `10.31.0.31` (`ocid1.privateip.oc1.sa-saopaulo-1.aaaaaaaanpw4einmn47zcmk4nnkshafyjwxrcfpi35op7ziciytkdz5y3ioa`) |
| DRG Attachment | `drg-attachment-aln-srv-vcn` (`ocid1.drgattachment.oc1.sa-saopaulo-1.aaaaaaaau52jbhi2344esp7jfubabcxyzx5ke7bagphmxvqiejfzaum5su3q`) |
| Route Table Ingress DRG | `rt-aln-drg-ingress` (`ocid1.routetable.oc1.sa-saopaulo-1.aaaaaaaask3txgnnfpcfab76j7va7a47mh6thubuwdws7icdqqglhsmmtcka`) |

---

## 2. Ações de Infraestrutura OCI Realizadas

### 2.1 Políticas IAM Cross-Tenancy
Para permitir a conexão da VCN de uma tenancy secundária (`alnrec`) ao DRG central na tenancy primária (`atius1`):
1. **Em `atius1` (DRG Owner):**
   - Policy: `phase26-alnrec-drg-central`
   - Statements:
     - `Define tenancy alnrec as ocid1.tenancy.oc1..aaaaaaaayiktgkyn5nzjjfkkcohplmdp2k6xccqmn56wjcfywd3pcdftqdqq`
     - `Endorse any-user to manage drg-attachment in tenancy alnrec where target.drg.id = 'ocid1.drg.oc1.sa-saopaulo-1.aaaaaaaapkv4lkgvhwkumakeq5pbdnbe32hbp2zai2mhe7d7pzwk7x774zqa'`
     - `Admit any-user of tenancy alnrec to manage drg in tenancy atius1`
2. **Em `alnrec` (VCN Owner):**
   - Policy: `phase26-alnrec-vcn-attachment`
   - Statements:
     - `Define tenancy atius1 as ocid1.tenancy.oc1..aaaaaaaa5s4cimfur7gpfukjsqjhvywbdh66hngxmpj4iexmb6vwwmix76ta`
     - `Endorse any-user to manage drg-attachment in compartment id ocid1.tenancy.oc1..aaaaaaaayiktgkyn5nzjjfkkcohplmdp2k6xccqmn56wjcfywd3pcdftqdqq where all {request.principal.type='user', target.drg.id='ocid1.drg.oc1.sa-saopaulo-1.aaaaaaaapkv4lkgvhwkumakeq5pbdnbe32hbp2zai2mhe7d7pzwk7x774zqa'}`
     - `Admit any-user of tenancy atius1 to manage drg-attachment in tenancy alnrec`

### 2.2 Criação do DRG Attachment
- Criada a tabela de rotas de ingresso dedicada `rt-aln-drg-ingress` (requisito OCI para DRG attachments customizados).
- Anexado `aln-srv-vcn` ao DRG Central. O DRG autopropagou a rota `10.31.0.0/24` na tabela de rotas interna do DRG.

### 2.3 Atualização de Tabelas de Rotas VCN
- **Em `alnrec`:** Adicionadas rotas na Route Table padrão da VCN apontando `10.11.0.0/16`, `10.12.0.0/16`, `10.13.0.0/16`, `10.14.0.0/16` e `10.21.0.0/16` para o DRG Central.
- **Em `atius1`, `atius2`, `atius3`, `atius4`, `horistic`:** Adicionada rota para `10.31.0.0/16` apontando para o DRG Central.

### 2.4 Atualização de Security Lists
- Regras de Ingress liberadas para todo o tráfego originado em `10.31.0.0/16` nas Security Lists de todos os pares da frota.
- Security List de `alnrec` liberada para receber todo o tráfego de `10.11.0.0/16`, `10.12.0.0/16`, `10.13.0.0/16`, `10.14.0.0/16`, `10.21.0.0/16` e `10.100.100.0/24`.

---

## 3. Configuração nos Sistemas Operacionais (Guest OS)

### 3.1 Atribuição e Persistência de IP Secundário no `aln-srv-amd`
- Criado arquivo `/etc/netplan/60-secondary-ip.yaml` no Ubuntu:
```yaml
network:
  version: 2
  ethernets:
    ens3:
      addresses:
        - 10.31.0.31/24
```
- Aplicado com `netplan apply`. O host agora responde tanto no IP DHCP primário `10.31.0.197` quanto no IP canônico de máquina `10.31.0.31`.

### 3.2 Rotas de Retorno nos Servidores Multi-VNIC
Para servidores que possuem VNIC secundária de infraestrutura OCI (`enp1s0`/`enp2s0`):
- Adicionada rota estática para `10.31.0.0/16` em `/etc/netplan/61-oci-primary-vnic.yaml` no `atius-srv-1`, `atius-srv-2`, `atius-srv-3` e `horistic-srv`, garantindo roteamento simétrico via VNIC privada do DRG.

### 3.3 DNS Interno da Frota (CoreDNS)
- Configurado `/home/ubuntu/GitHub/vpn-atius/coredns/custom_hosts_atius_internal` no `atius-srv-1`:
  ```text
  10.31.0.31 aln-srv.atius.internal aln-srv aln-srv-amd
  ```
- Reiniciado `coredns-vpn.service`. Resolução testada com sucesso de ponta a ponta.

---

## 4. Matriz de Conectividade Validada

| Origem | Destino | Tipo | Latência / Resultado |
|---|---|---|---|
| `aln-srv` (`10.31.0.31`) | `atius-srv-1` (`10.11.1.11`) | ICMP / Ping | 0.52 ms, 0% loss |
| `aln-srv` (`10.31.0.31`) | `atius-srv-2` (`10.12.1.12`) | ICMP / Ping | 0.61 ms, 0% loss |
| `aln-srv` (`10.31.0.31`) | `atius-srv-3` (`10.13.1.13`) | ICMP / Ping | 0.56 ms, 0% loss |
| `aln-srv` (`10.31.0.31`) | `atius-srv-4` (`10.14.1.14`) | ICMP / Ping | 0.53 ms, 0% loss |
| `aln-srv` (`10.31.0.31`) | `horistic-srv` (`10.21.1.21`) | ICMP / Ping | 0.55 ms, 0% loss |
| `atius-srv-1` (`10.11.1.11`) | `aln-srv` (`10.31.0.31`) | ICMP / Ping | 0.54 ms, 0% loss |
| `atius-srv-2` (`10.12.1.12`) | `aln-srv` (`10.31.0.31`) | ICMP / Ping | 0.60 ms, 0% loss |
| `atius-srv-3` (`10.13.1.13`) | `aln-srv` (`10.31.0.31`) | ICMP / Ping | 0.58 ms, 0% loss |
| `atius-srv-4` (`10.14.1.14`) | `aln-srv` (`10.31.0.31`) | ICMP / Ping | 0.55 ms, 0% loss |
| `horistic-srv` (`10.21.1.21`) | `aln-srv` (`10.31.0.31`) | ICMP / Ping | 0.57 ms, 0% loss |
| `aln-srv` | `10.11.1.11:53` (CoreDNS) | DNS query | `aln-srv.atius.internal -> 10.31.0.31` |
| `aln-srv` | `10.13.1.13:8202` (Vault) | TCP SYN | Handshake PASS |

---

## 5. Próximos Passos e Observações

- O host `aln-srv` não integra o cluster K3s por padrão (shape de 1 vCPU e 1 GiB RAM reservado para serviços próprios de parceria).
- Qualquer serviço executado em `aln-srv` que necessite falar com APIs internas da frota (Vault, DB, RabbitMQ, etc) pode utilizar diretamente as rotas privadas do DRG em `10.11.x`, `10.12.x`, `10.13.x` sem sair para a internet pública.
