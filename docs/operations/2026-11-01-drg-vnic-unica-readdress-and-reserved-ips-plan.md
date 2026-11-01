# Plano de Engenharia Canônico: Reendereçamento DRG, Unificação VNIC Única e Padronização 100% Reserved Public IPs

- **Data:** 2026-11-01
- **Status:** Proposta Aprovada / Em Planejamento de Execução
- **Autoridade OCI:** `[oci.atius.io] - Orch - OCI Admin Cluster` (`8a2d864b-6210-42a3-a0aa-7a29da78f4f7`)
- **Worker Executor OCI:** `[oci.atius.io] - Worker 1 - Admin Cluster via SDK/MCP` (`47bef0e0-618c-4aad-bb29-6635339b0837`)
- **Escopo:** Frota ATIUS Core (`atius-srv-1..4`), Servidores Parceiros (`horistic-srv`, `aln-srv`), DRG Central OCI (`Brasil - Sao Paulo`), HashiCorp Vault, CoreDNS, K3s, Prometheus e Edge SSO.

---

## 1. Matriz Canônica de Endereçamento DRG e VCNs

A nova topologia substitui a convenção transitória (`10.1x.1.1x` / `10.21.1.21` / `10.31.0.31`) por uma arquitetura simétrica, com blocos `/16` estritamente disjuntos por tenancy, permitindo roteamento direto de alta performance no DRG Central sem colisão de CIDRs.

### A. Tabela Mestra de IPs e VCNs

| Host | Tenancy OCI | Grupo de Governança | VCN CIDR | Subnet Servidores | IP Privado Primário (VNIC Única) | Subnet Serviços | IP Público Oracle | Status de Reserva |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **`atius-srv-1`** | `atius1` | `atius_core` | `10.1.0.0/16` | `10.1.0.0/24` | **`10.1.0.1`** | `10.1.2.0/24` | `137.131.190.161` | **MIGRAR PARA RESERVED** |
| **`atius-srv-2`** | `atius2` | `atius_core` | `10.2.0.0/16` | `10.2.0.0/24` | **`10.2.0.2`** | `10.2.2.0/24` | `64.181.185.218` | **RESERVED** (`ip-atius-mt5`) |
| **`atius-srv-3`** | `atius3` | `atius_core` | `10.3.0.0/16` | `10.3.0.0/24` | **`10.3.0.3`** | `10.3.2.0/24` | `163.176.178.228`| **RESERVED** (`ip-atius-srv-3`) |
| **`atius-srv-4`** | `atius4` | `atius_core` | `10.4.0.0/16` | `10.4.0.0/24` | **`10.4.0.4`** | `10.4.2.0/24` | `164.152.48.22`  | **RESERVED** (Já VNIC Única) |
| **`horistic-srv`**| `horistic` | `partners` | `10.51.0.0/16` | `10.51.0.0/24` | **`10.51.0.1`** | `10.51.2.0/24` | `163.176.232.119`| **RESERVED** (`horistic-srv-1`) |
| **`aln-srv`** | `alnrec` | `partners` | `10.52.0.0/16` | `10.52.0.0/24` | **`10.52.0.2`** | `10.52.2.0/24` | `168.138.136.251`| **VALIDAR / RESERVAR** |

### B. Mapeamento de Faixas Reservadas e Redes Excluídas
- **ATIUS Core Range:** `10.1.0.0/16` até `10.20.0.0/16` (reservado para nós de controle e aplicações centrais).
- **Parceiros (Partners) Range:** `10.51.0.0/16` até `10.70.0.0/16` (reservado para nós externos/parceiros).
- **WireGuard Control Plane (`wg100`):** `10.100.0.0/16` (subnet ativa `10.100.100.0/24`).
- **K3s Pods:** `10.42.0.0/16` (inalterado).
- **K3s Services:** `10.43.0.0/16` (inalterado).
- **Tailscale Mesh:** `100.64.0.0/10` (inalterado).
- **Docker / Podman Local Bridges:** `10.65.172.0/24` e `10.89.53.0/24`.
- **Faixas Aposentadas:** `10.1.1.0/24` (antiga wg0) e `10.0.0.0/16` (VCNs default legadas da OCI).

---

## 2. Política Mandatória: Padronização 100% Reserved Public IPs

### A. Diagnóstico de Risco Atual
- No `sa-saopaulo-1`, o endpoint público primário do `atius-srv-1` (`137.131.190.161`), que hospeda o Edge Gateway e o Apache de entrada para `atius.com.br` e `atius.io`, foi provisionado originalmente como **EPHEMERAL** na VNIC primária `AtiusCapital1`.
- **Risco Severo:** Se a instância for recriada ou a VNIC sofrer rebuild para migração de rede sem reserva prévia, o IP público `137.131.190.161` seria liberado pela Oracle e perdido, quebrando todos os apontamentos DNS públicos do Cloudflare e certificados TLS.

### B. Ação de Promoção e Reserva
1. **Promoção de `137.131.190.161`:**
   - Utilizar o `oci-admin` para invocar a API OCI (`UpdatePublicIp` / `CreatePublicIp` com `lifetime: RESERVED`, `privateIpId: ocid1.privateip...`), convertendo o IP efêmero atual em um **Reserved Public IP** permanente vinculado à tenancy `atius1`.
2. **Auditoria de `aln-srv` (`alnrec`):**
   - Confirmar se `168.138.136.251` é `RESERVED` no root compartment da tenancy `alnrec`. Caso seja efêmero, aplicar a mesma promoção via `oci-admin`.
3. **Regra de Gate:** Zero mutações de VNIC ou compute permitidas antes do readback formal de que 100% dos IPs públicos da frota reportam `lifetime: RESERVED` e `lifecycle_state: ASSIGNED`.

---

## 3. Arquitetura de Transição para VNIC Única (Single-VNIC)

### A. Justificativa Arquitetural
- **Problema Atual (Dual-VNIC em srv-1, srv-2, srv-3 e Horistic):** Duas placas de rede na VM geram complexidade de Policy Routing no Linux (`ip rule`, tabelas `rt2`, Netplan duplo, risco de assimetria de pacotes).
- **Vantagem da VNIC Única (Já em produção no `atius-srv-4`):**
  - Uma única interface de rede física (`enp...` ou `ens3`).
  - O kernel Linux usa apenas a tabela padrão com default gateway para a Internet (`0.0.0.0/0 via Internet Gateway`).
  - O tráfego para a frota (`10.0.0.0/8`, especificamente `10.1/16`..`10.52/16`) é roteado pelo hardware virtual da OCI via **Longest Prefix Match (LPM)** diretamente para o DRG attachment da VCN, com latência sub-milissegundo e zero regras no sistema operacional do servidor.

### B. Procedimento de Cutover por Nó (Sem Perda de Dados)
1. **Garantia de Boot Volume:** O boot volume da VM é preservado integralmente.
2. **Stop da Instância:** `oci-admin compute action <OCID> stop --confirm "STOP:<TOKEN>"`.
3. **Detach do Boot Volume:** Liberação do volume original.
4. **Provisionamento da Nova Instância (ou Reanexação na VCN Definitiva):**
   - Criada diretamente na nova VCN (`vcn-atius1` em `10.1.0.0/16`) com VNIC única e IP privado estático (`10.1.0.1`).
   - Reassociação do **Reserved Public IP** correspondente à nova VNIC.
   - Start da instância com o boot volume preservado.

---

## 4. Matriz de Impactos em Aplicações, Serviços e Portas

A migração de IPs exige atualização sincronizada nas seguintes camadas:

### A. HashiCorp Vault (`atius-srv-3`)
- **Porta:** `8202/TCP`
- **Novo Endpoint:** `https://10.3.0.3:8202`
- **Ações:**
  - Atualizar listeners em `/etc/vault.d/vault.hcl` no `atius-srv-3`.
  - Atualizar certificados TLS SAN (`10.3.0.3` adicionado ao certificado do Vault).
  - Atualizar scripts helpers de ambiente: `atius-vault-env`, `~/.bashrc`, `~/.zshrc`, `/etc/environment` no `srv-1`, `srv-2`, `srv-4`, `horistic-srv`, W11 e WSL.

### B. DNS Interno CoreDNS / AdGuard Home (`atius-srv-1`)
- **Porta:** `53/UDP` e `53/TCP`
- **Novo IP do Resolver:** `10.1.0.1`
- **Mapeamentos em `/etc/coredns/hosts`:**
  ```text
  10.1.0.1   atius-srv-1.atius.internal atius-srv-1
  10.2.0.2   atius-srv-2.atius.internal atius-srv-2
  10.3.0.3   atius-srv-3.atius.internal atius-srv-3
  10.4.0.4   atius-srv-4.atius.internal atius-srv-4
  10.51.0.1  horistic-srv.atius.internal horistic-srv
  10.52.0.2  aln-srv.atius.internal aln-srv
  ```
- **AdGuard Home / Systemd-Resolved:** Apontar nameserver local para `10.1.0.1`.

### C. Apache Reverse Proxy e Edge Gateway (`atius-srv-1`)
- **Porta Edge:** `8210/TCP` (Edge Gateway SSO) e `443/TCP` (Apache)
- **Upstreams atualizados:**
  - `landscape.atius.com.br` / `landscape.atius.io`: aponta para `https://10.3.0.3:443`
  - `grafana.atius.com.br` / `grafana.atius.io`: aponta para `http://10.3.0.3:3005`
  - `oci.atius.io` / `oci-admin`: aponta para `http://10.3.0.3:8090`
  - Aplicações no SRV-2 (`portainer`, `pm2`, etc.): apontam para `10.2.0.2`

### D. K3s HA Cluster e Monitoramento
- **K3s Flannel & Kubelet:**
  - Flags de inicialização `--node-ip` e `--advertise-address` em cada nó ajustadas para os novos IPs.
  - Port-forward local do Grafana (`k3s-grafana-portforward.service`): bind em `10.3.0.3:3005`.
- **Prometheus Scrapes:**
  - Atualizar `scrape_configs` do Prometheus para coletar métricas de `node-exporter` em:
    - `10.1.0.1:9100`, `10.2.0.2:9100`, `10.3.0.3:9100`, `10.4.0.4:9100`, `10.51.0.1:9100`.

### E. Servidores Parceiros (`horistic-srv` e `aln-srv`)
- **Isolamento Confirmado:** Repositórios `omni-srv-admin` e `oci-admin` mantêm status estrito de `forbidden_hosts: purge`.
- **Aplicações Locais:**
  - `horistic-srv` (`10.51.0.1`): `divap-painel` e node-exporter.
  - `aln-srv` (`10.52.0.2`): `parceiro-certo` (`parceiro.aln.internal`) via Nginx local.

---

## 5. Estratégia de Testes e Validação por Waves (TDD)

Cada etapa de migração é governada por suítes de testes automatizados com fail-fast e rollback imediato.

### Wave 0: Contrato e TDD no `oci-admin`
- [ ] Atualizar `_TARGET_ADDRESS_ROWS` em `app/oci_client/peering_actions.py` com as novas faixas (`10.1`, `10.2`, `10.3`, `10.4`, `10.51`, `10.52`).
- [ ] Executar suíte de testes de endereçamento:
  ```bash
  pytest tests/test_peering_addressing.py tests/test_peering_drg.py tests/test_peering_routes.py -v
  ```
- [ ] Testes devem cobrir:
  1. Detecção e rejeição de qualquer sobreposição de CIDR.
  2. Geração correta de OperationPlans com nomes `vcn-atius1`, `subnet-atius1` nas novas faixas.
  3. Previsão de rotas DRG para os novos blocos de parceiros (`10.51` e `10.52`).

### Wave 1: Garantia e Reserva de IPs Públicos na OCI
- [ ] Readback do status de todos os IPs públicos via `oci-admin`.
- [ ] Promoção de `137.131.190.161` para `RESERVED` na tenancy `atius1`.
- [ ] Prova de que zero instâncias da frota utilizam IP público efêmero.

### Wave 2: Preparação das Novas VCNs e DRG Attachments
- [ ] Criação das novas VCNs sem afetar as instâncias ativas:
  - `vcn-atius1` (`10.1.0.0/16`), `vcn-atius2` (`10.2.0.0/16`), etc.
- [ ] Anexação ao DRG Central (`Brasil - Sao Paulo`) e propagação de rotas.
- [ ] Testes de validação de rota sintética no DRG (`peering.drg_status` reportando `attached_to_central` e `blocked=false`).

### Wave 3: Migração Controlada Host a Host (Ordem Crítica)
1. **Passo 1: `horistic-srv` e `aln-srv` (Parceiros isolados)**:
   - Migração para VNIC única em `10.51.0.1` e `10.52.0.2`.
   - Teste de conectividade ICMP e HTTP local.
2. **Passo 2: `atius-srv-2` e `atius-srv-4` (Workloads e CI/CD)**:
   - Migração para `10.2.0.2` e `10.4.0.4`.
3. **Passo 3: `atius-srv-3` (HashiCorp Vault e Landscape)**:
   - Migração para `10.3.0.3`.
   - Revalidação imediata do Vault e reativação do token OCI.
4. **Passo 4: `atius-srv-1` (Gateway e CoreDNS)**:
   - Migração final para `10.1.0.1` com o IP reservado `137.131.190.161`.
   - Reload do CoreDNS e revalidação do Edge Gateway.

### Wave 4: Teste de Aceite Global e Prova de Ponta a Ponta
- [ ] Scrapes Prometheus: 5/5 nós `up=1`.
- [ ] Vault health check em `10.3.0.3:8202`: HTTP 200 / Unsealed.
- [ ] Edge Gateway em `127.0.0.1:8210`: 100% dos domínios `.io` e `.com.br` respondendo HTTP 200/302.
- [ ] Rota SSH pública nativa e WireGuard `wg100` verificados como redundância de reserva ativa.
- [ ] Atualização final de documentação no Obsidian, GBrain e Graphify.
