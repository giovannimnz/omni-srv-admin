# Governança de Portas Mosh (Mobile Shell) - Frota ATIUS & Horistic

## 1. Visão Geral e Padronização Canônica

Para garantir conexões interativas de terminal resilientes a perdas de pacotes e mudanças de rede móvel (Termius, Blink Shell, mosh-client), a frota unificada adota a seguinte faixa estrita para o serviço Mosh (`mosh-server`):

- **Protocolo:** UDP
- **Faixa de Portas Canônica:** `60001 a 60999` (UDP 60001-60999)
- **Status:** Padronizado e aplicado em toda a frota (100%).

> [!NOTE]
> A documentação histórica continha referências a `60000-61000`. Essa faixa foi substituída e estritamente consolidada para **60001 a 60999**, respeitando a convenção de portas padrão do binário oficial `mosh` (que inicia por padrão em 60001) e alinhando com as Security Lists da OCI e iptables de cada nó.

---

## 2. Inventário de Hosts e Status Atual

| Host | IP Público | IP OCI / DRG | WireGuard | Mosh Server | Firewall Host (iptables) | OCI Security Lists |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **atius-srv-1** | `137.131.190.161` | `10.11.1.11` | `10.100.100.1` | Instalado (v1.4.0) | UDP 60001:60999 [OK] | VCN-AtiusBR + vcn-atius1 [OK] |
| **atius-srv-2** | `129.148.47.32` | `10.12.1.12` | `10.100.100.2` | Instalado (v1.4.0) | UDP 60001:60999 [OK] | vcn-atiuscapital2 + vcn-atius2 [OK] |
| **atius-srv-3** | `136.248.126.12` | `10.13.1.13` | `10.100.100.3` | Instalado (v1.4.0) | UDP 60001:60999 [OK] | Atius3VCN + vcn-atius3 [OK] |
| **atius-srv-4** | `137.131.156.141`| `10.14.1.14` | - | Instalado (v1.4.0) | UDP 60001:60999 [OK] | vcn-atius4 [OK] |
| **horistic-srv** | `163.176.232.119`| `10.21.1.21` | `10.100.100.4` | Instalado (v1.4.0) | UDP 60001:60999 [OK] | horistic-vcn-1 + vcn-horistic [OK] |

---

## 3. Configuração do Firewall no Sistema Operacional (Host iptables)

Em sistemas Linux Ubuntu (especialmente com a imagem Ubuntu 24.04 / 22.04 na OCI), as regras padrão do iptables bloqueiam qualquer porta não declarada antes da regra final de rejeição ICMP (`-j REJECT --reject-with icmp-host-prohibited`).

### 3.1 Regra Aplicada (Topo do Chain INPUT)
```bash
sudo iptables -I INPUT 1 -p udp -m udp --dport 60001:60999 -m comment --comment "MOSH_SERVER_UDP_RANGE" -j ACCEPT
```

### 3.2 Persistência
```bash
sudo netfilter-persistent save
```
Arquivo de configuração persistente: `/etc/iptables/rules.v4` e `iptables/iptables-backup-v4.conf` no repositório `omni-srv-admin`.

---

## 4. Configuração na Oracle Cloud Infrastructure (OCI)

Para que os pacotes UDP cheguem à interface de rede (VNIC) da instância, a Security List associada à Subnet (pública e privada/DRG) deve conter uma regra de Ingress correspondente.

### 4.1 Especificação da Regra de Ingress
- **Stateless:** `False` (Stateful)
- **Source CIDR:** `0.0.0.0/0`
- **IP Protocol:** `UDP` (Código 17)
- **Source Port Range:** Todos (`null`)
- **Destination Port Range:** Min `60001`, Max `60999`
- **Description:** `MOSH SERVER UDP RANGE (Termius/Mobile Shell)`

### 4.2 Security Lists Provisionadas na Frota
1. `atius1` (Pública): `Default Security List for VCN-AtiusBR`
2. `atius1` (DRG): `Default Security List for vcn-atius1`
3. `atius2` (Pública): `Default Security List for vcn-atiuscapital2`
4. `atius2` (DRG): `Default Security List for vcn-atius2`
5. `atius3` (Pública): `Default Security List for Atius3VCN`
6. `atius3` (DRG): `Default Security List for vcn-atius3`
7. `atius4` (Geral): `Default Security List for vcn-atius4`
8. `horistic` (Pública): `Default Security List for horistic-vcn-1`
9. `horistic` (DRG): `Default Security List for vcn-horistic`

### 4.3 Modo de Execução na OCI
A aplicação das regras de segurança foi realizada via automação governada utilizando o **OCI Python SDK / OCI Admin** a partir de `atius-srv-3`, operando com os perfis canônicos OCI (`atius1`, `atius2`, `atius3`, `atius4`, `horistic`) sob autenticação por chave RSA (`.oci/config`).

Para novas instâncias ou automação via `oci-admin`:
- **CLI / SDK:** Invocação de `VirtualNetworkClient.update_security_list` adicionando o objeto `IngressSecurityRule` com `UdpOptions(destination_port_range=PortRange(min=60001, max=60999))`.
- **MCP (`oci_admin_http`):** Chamada de controle de segurança de rede da OCI.

---

## 5. Provisionamento de Novas Instâncias no `omni-srv-admin`

Ao provisionar um novo servidor na frota:
1. **Etapa 1 de Sistema (`setup.sh`):**
   - O pacote `mosh` é instalado automaticamente no bloco de ferramentas básicas:
     ```bash
     sudo apt-get install $APT_OPTS nano mosh
     ```
   - O arquivo `iptables/iptables-backup-v4.conf` já contém a diretiva `60001:60999`.
2. **Subnet / Security List na OCI:**
   - Adicionar a regra Ingress UDP `60001-60999` na Security List da nova VCN/Subnet antes do primeiro acesso.
3. **Registro no Inventário:**
   - Declarar o app `mosh` em `inventory/hosts/<nome-do-host>.yaml` com `port_range: "60001-60999/udp"`.

---

## 6. Procedimento de Acesso via Termius / Mosh Client

Para se conectar via Mosh especificando a porta inicial ou deixando o mosh alocar dentro da faixa:
```bash
# Conexão direta com porta automática (inicia em 60001)
mosh ubuntu@137.131.190.161

# Conexão especificando porta fixa da faixa
mosh -p 60001 ubuntu@137.131.190.161

# Conexão com chave SSH e porta SSH não-padrão se aplicável
mosh --ssh="ssh -p 22 -i ~/.ssh/id_rsa" ubuntu@137.131.190.161
```
No **Termius**:
1. Ative a opção **Mosh** nas configurações do host.
2. Defina a porta inicial como `60001` (ou deixe o padrão que aloca a partir de 60001).
