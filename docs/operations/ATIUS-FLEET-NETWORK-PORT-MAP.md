# ATIUS Fleet — Network & Port Map (canônico)

> **Este é o documento canônico** para topologia de rede, IPs, portas
> e convenção de displays da frota ATIUS. Substitui e unifica
> docs fragmentados (atius-fleet-specs.md, Atius-Spec-Servers.md,
> atius-home-server-overview.md, SERVER-AUDIT-20260506.md,
> 17.08-Obsidian-Local-REST-API-MCP-Setup.md).
>
> Versão: 1.7.9 — 2026-07-23
> Owner: giovanni
> Mantido por: omni-srv-admin (repo + vault)
> Cross-refs: [[inventory/hosts/*]], [[.planning/STATE.md]],
>             [[.planning/phases/13-k3s-ha-portainer-oci/*]]

---

## 1. Identidade dos Hosts

Os servidores principais ATIUS/Horistic são Oracle OCI Ampere A1 (ARM64).
Os hosts móveis/complementares são documentados para completeness.

| Host           | Função             | OS            | Status  | Inventory |
|----------------|--------------------|---------------|---------|-----------|
| atius-srv-1    | production         | Ubuntu 24.04  | active  | `inventory/hosts/atius-srv-1.yaml` |
| atius-srv-2    | development        | Ubuntu 24.04  | active  | `inventory/hosts/atius-srv-2.yaml` |
| atius-srv-3    | sandbox            | Ubuntu 24.04  | active  | `inventory/hosts/atius-srv-3.yaml` |
| horistic-srv    | proxy reverso / K3s worker / AI Search | Ubuntu 24.04  | active  | `inventory/hosts/horistic-srv.yaml`    |
| GIOVANNI-W11-PC | workstation Windows + WSL | Windows 11 / Ubuntu 24.04 WSL | active via VPN e Casa gateway | `inventory/hosts/giovanni-w11-pc.yaml` |
| GIOVANNI-PC    | workstation pessoal| Ubuntu 26.04  | planned | `inventory/hosts/dell-inspiron-3520.yaml` |
| GIOVANNI-S23   | mobile node        | Termux (Android) | active via VPN e Casa gateway | `inventory/hosts/giovanni-s23-termux.yaml` |
| GIOVANNI-S23-PROOT | mobile ubuntu | Ubuntu (proot) | planned | `inventory/hosts/giovanni-s23-proot.yaml` |
| atius-mt5-kvm-1 | MT5 execution primary | Ubuntu 24.04 x86_64 | active | `inventory/hosts/atius-mt5-kvm-1.yaml` |
| atius-mt5-kvm-2 | MT5 execution backup | Ubuntu 24.04 x86_64 | active | `inventory/hosts/atius-mt5-kvm-2.yaml` |

Specs comuns (Oracle OCI Ampere A1.Flex):
- Arquitetura: ARM64 / aarch64
- CPU: 4 vCPUs (Ampere Altra, 1 thread/core)
- RAM: 23.42 GiB (24,556,000 kB)
- Swap: 10.00 GiB (10,485,756 kB)
- Disco: 200 GB nominal = 186.26 GiB real (block volume)
- Write max: 108 MB/s (SRV-1) a 124 MB/s (SRV-2)
- Kernel: 6.8.0-1050-oracle (Jammy 22.04) ou 6.17.x-oracle (Noble 24.04)
- builds/process-build: 20% do CPU total por padrão
- RAM=11.71 GiB é teto de uso comum de processo
- write não é build-default (varia por profile)

---

## 2. Topologia de Rede

```
                    INTERNET
                       │
            ┌──────────┴──────────┐
            │ Cloudflare (proxy)  │
            │ *.atius.com.br      │
            │ *.horistic.com      │
            └──────────┬──────────┘
                       │
       ┌───────────────┼───────────────┐
       │               │               │
   OCI VCN         OCI VCN         OCI VCN
   SRV-1           SRV-2           SRV-3
   137.131.190.161  129.148.47.32   136.248.126.12
       │               │               │
       └──────── WireGuard wg100 (hub SRV-1, port 51821) ───┐
                       │                                    │
            10.100.100.0/24 (VPN control plane)             │
                       │                                    │
       ┌───────────────┼───────────────┐                    │
       │               │               │                    │
   SRV-1         SRV-2          SRV-3                Tailscale (mesh backup)
   10.100.100.1  10.100.100.2   10.100.100.3         100.76/100.93/100.72
       │               │               │
       └─── K3s HA cluster (WireGuard-transport) ───────────┘
            flannel.1 10.42.0.0/16
            etcd 2379/2380 (control plane + etcd)
```

Camadas:
1. **Oracle VCN** (10.0.0.0/24 ou DHCP): rede privada de cada OCI
2. **OCI private / DRG** (`10.11.1.11`, `10.12.1.12`, `10.13.1.13`, `10.21.1.21`): plano canônico de serviços entre hosts
3. **WireGuard wg100** (10.100.100.0/24): reserve/fallback, com uso principal para W11/S23 e break-glass
4. **WireGuard wg0 retired** (`10.1.1.0/24`): faixa histórica aposentada; não
   usar como rede operacional, source of truth ou fallback vivo
5. **Tailscale** (100.64.0.0/10): mesh backup / acesso de fora
6. **K3s flannel** (10.42.0.0/16): CNI dos pods no cluster
7. **Cloudflare**: proxy reverso público, escudo anti-DDoS, Origin SSL

---

## 3. Mapa de IPs (canônico)

| Host           | Hostname        | IP Público       | WireGuard reserve | Tailscale       | OCI primary |
|----------------|-----------------|------------------|-------------------|------------------|-------------|
| atius-srv-1    | atius-srv-1     | 137.131.190.161  | 10.100.100.1      | 100.76.56.62     | 10.11.1.11  |
| atius-srv-2    | atius-srv-2     | 129.148.47.32    | 10.100.100.2      | 100.93.43.113    | 10.12.1.12  |
| atius-srv-3    | atius-srv-3     | 136.248.126.12   | 10.100.100.3      | 100.72.102.57    | 10.13.1.13  |
| horistic-srv   | horistic-srv    | 163.176.232.119  | 10.100.100.4      | 100.102.126.61   | 10.21.1.21  |
| GIOVANNI-W11-PC | GIOVANNI-W11-PC | dynamic/home     | 10.100.100.8 (legacy `10.100.100.5`) | - | LAN BE3 192.168.1.8 |
| GIOVANNI-S20   | GIOVANNI-S20    | dynamic/home     | 10.100.100.9 (configured, no handshake) | - | LAN BE3 192.168.1.9; stale lease `.62` at 2026-07-23 readback |
| GIOVANNI-S23   | GIOVANNI-S23    | dynamic/home     | 10.100.100.10 (configured, no handshake; previous `.9`) | - | LAN BE3 192.168.1.10 |
| atius-mt5-kvm-1 | atius-mt5-kvm-1 | 137.131.228.103 | 10.100.100.16 | - | 10.0.0.61 |
| atius-mt5-kvm-2 | atius-mt5-kvm-2 | 147.15.83.218 | 10.100.100.17 | - | 10.0.0.188 |

### Home Edge / Residential

As reservas LAN abaixo são canônicas. O material PPTP continua apenas como
spike. No runtime Casa Remote Gateway descrito depois da tabela, SSH nativo e
browser estão `GO` 4/4; somente o desktop RDP continua parcial/`NO-GO`. O
caminho SSH público não usa PPTP, WireGuard ou Cloudflare Tunnel no cliente.

| Device | Home LAN reserved IP | MAC | Purpose | Status |
|--------|----------------------|-----|---------|--------|
| `GIOVANNI-W11-PC` | `192.168.1.8` | `44:FA:66:01:6F:AB` | PPTP residencial em casa | reserved, spike |
| `GIOVANNI-S20` | `192.168.1.9` | `30:AB:6A:3C:96:D1` | Termux + Ubuntu PRoot no mesmo handset/IP | reservation enabled; handset lease renew pending |
| `GIOVANNI-S23` | `192.168.1.10` | `64:1B:2F:C2:DC:A3` | Termux SSH residencial | reserved; LAN host key proven |

#### Casa Remote Gateway — runtime ativo 2026-07-19

```text
Browser -> Apache atius-srv-1 -> ATS admin gate -> RustGuac/bundled guacd
        -> relay -> home WAN -> BE3 NAT -> residential LAN
```

Cloudflare: `casa.atius.com.br` é um único record `A`, proxied, TTL
Automatic, SSL `Full (strict)`, WebSockets on e zero Tunnels. HTTP `:80`
chega ao Apache e recebe `301`; HTTPS/WSS usa `:443`. O record aponta ao edge
público do SRV-1, não ao WAN residencial.

| Regra BE3 | Proto | WAN externa | LAN destino | Interna | Usuário/serviço | Remote Host live / target |
|---|---|---:|---|---:|---|---|
| `atius-w11-ssh` | TCP | 8122 | `192.168.1.8` | 22 | `muniz`, Windows OpenSSH/PowerShell 7 | `137.131.190.161`; external SSH host-key PASS |
| `atius-s23-ssh` | TCP | 8322 | `192.168.1.10` | 8022 | `termux`, Termux OpenSSH | `137.131.190.161`; external connection closed before KEX |
| `atius-wsl-ssh` | TCP | 8222 | `192.168.1.8` | 8022 | `muniz`, Windows portproxy -> WSL Ubuntu | `137.131.190.161`; external SSH host-key PASS |
| `atius-w11-rdp` | TCP | 3389 | `192.168.1.8` | 3389 | `muniz`, Windows RDP/NLA | `137.131.190.161`; RDP/NLA validate separately |

S20 slots are reserved but not published:

| Logical target | Proposed public port | LAN target | Publication status |
|---|---:|---|---|
| `GIOVANNI-S20` Termux | 8422 | `192.168.1.9:<internal-port-pending>` | blocked on DHCP renew, listener, user, fingerprint and authentication |
| `GIOVANNI-S20-UBUNTU` PRoot | 8522 | `192.168.1.9:<internal-port-pending>` | blocked on PRoot listener, user, fingerprint and authentication |

Proxy interno no SRV-1: ATS `/v1/auth/me` em `127.0.0.1:8015`; gateway Casa
SSH em `127.0.0.1:8196`; gateway RDP dedicado em `127.0.0.1:8197`; RustGuac em
`127.0.0.1:8089`; `guacd:4822` bundled. O catch-all do router segue para o
origin residencial dinâmico `:8888`. `/ssh/*` e `/rdp/*` no Casa são redirects
de compatibilidade; SSH nativo usa os hostnames DNS-only e portas explícitas.

Source detalhada, fingerprints, Vault fields, serviços, backups e validação:
`/home/ubuntu/GitHub/vpn-atius/home-proxy/docs/operations/2026-07-19-casa-ssh-rdp-gateway.md`.

O bloco abaixo é histórico e foi superseded pelo rollout as-built de
2026-07-19. O estado anterior `NO-GO` decorreu de host/path OpenSSH não
portátil, `nc -w 15` encerrando idle, filtro Apache corrompendo assets públicos
do Guacamole e RDP `Origin: null`/403. O rollout atual usa relay TCP por IP
reservado, documentado no runbook do `home-proxy`.

### Casa Remote Gateway — current as-built 2026-07-19

| Alias | Public IP | Cloudflare | Public port | Internal relay | BE3 -> LAN |
|---|---:|---|---:|---:|---|
| `ssh-giovanni-w11-pc.atius.com.br` | `137.131.140.20` | DNS-only | 8122 | nft -> 2222 | WAN 8122 -> `192.168.1.8:22` |
| `ssh-giovanni-wsl-pc.atius.com.br` | `137.131.140.20` | DNS-only | 8222 | nft -> 8822 | WAN 8222 -> `192.168.1.8:8022` |
| `ssh-giovanni-s23.atius.com.br` | `137.131.140.20` | DNS-only | 8322 | nft -> 8022 | WAN 8322 -> `192.168.1.10:8022` |
| `ssh-giovanni-s20.atius.com.br` | reserved, not published | DNS-only candidate | 8422 | pending | same handset `192.168.1.9`, internal port pending proof |
| `ssh-giovanni-s20-ubuntu.atius.com.br` | reserved, not published | DNS-only candidate | 8522 | pending | same handset `192.168.1.9`, internal port pending proof |
| `ssh-horistic-srv.atius.com.br` | `163.176.232.119` | DNS-only | 22 | public VNIC Horistic | `10.0.0.65:22` |
| `ssh.atius.com.br/compute/*` | `137.131.140.20` | DNS-only | 443 | Apache -> 8196/8089 | RustGuac -> relay correspondente |
| `rdp.atius.com.br/giovanni-w11-pc` | `137.131.190.161` | proxied | 443 | Apache -> 8197/8089 | WAN 3389 -> `192.168.1.8:3389` |

#### Ordem operacional de SSH e failover sem VPN

Uma falha de TCP, rota, timeout ou SSH no caminho privado deve sempre disparar
uma tentativa na rota pública nativa antes de o host ser declarado
inacessível. As rotas públicas abaixo terminam no edge/relay OCI e não dependem
de WireGuard no cliente:

| Alvo | Caminho privado direto | Fallback público obrigatório |
|---|---|---|
| W11 | `ssh muniz@10.100.100.8` | `ssh -p 8122 muniz@ssh-giovanni-w11-pc.atius.com.br` |
| WSL | `ssh -p 8022 muniz@10.100.100.8` | `ssh -p 8222 muniz@ssh-giovanni-wsl-pc.atius.com.br` |
| S23 | `ssh -p 8022 termux@10.100.100.10` | `ssh -p 8322 termux@ssh-giovanni-s23.atius.com.br` |
| S20 | configured WG `10.100.100.9`, SSH unproven | no fallback published; `8422` remains reserved |
| S20 Ubuntu PRoot | shares S20 IP, SSH unproven | no fallback published; `8522` remains reserved |
| Horistic | `ssh horistic@10.21.1.21` | `ssh -p 22 horistic@ssh-horistic-srv.atius.com.br` |

Em 2026-07-22, os dois caminhos do S23 autenticaram e chegaram ao mesmo Termux.
Essa validação não remove a regra de failover: disponibilidade de WireGuard é
estado transitório. Preserve o erro do caminho direto e o resultado do fallback
no relatório. Os paths `https://ssh.atius.com.br/ssh-*` são exclusivos do
browser e não são comandos OpenSSH.

Phase 07 consolidou os três aliases Casa no mesmo Public IP
`137.131.140.20`/private `.238`, com seleção nft pela porta. As reservas
anteriores de WSL/S23 e `.236/.237` continuam `RESERVED/ASSIGNED` somente para
rollback; suas portas antigas ficam fechadas no perfil final. Rollback e
reapply reais passaram sem detach/release, mantendo o service de secondary
addresses. Os launchers canônicos são `/compute/<slug>`; `/ssh-*` permanece
alias browser.

The Casa SSH public IPs and the Horistic public IP are OCI `RESERVED`; the W11
IP is also the dedicated `dns-casa.atius.com.br` A record on DNS port 53. This
sharing is intentional and must remain represented as separate port bindings.
The 2026-07-19 validation reached native and browser SSH `GO` 4/4. The current
2026-07-23 readback is narrower: W11 and WSL passed native SSH plus browser
HTTP `200`, WebSocket `101` and `connected`; S23 returned launcher `200` and
WebSocket `101`, but stayed `disconnected`, while native `8322` closed before
KEX. The RDP headless readback passed the SSO/ATS redirects and reached the
canonical same-origin form with CSRF and an empty required Microsoft password
field. No POST was authorized because the correct credential is absent from
Vault, so WebSocket/NLA/desktop were `NOT RUN`, not PASS or FAIL.

| Native SSH (histórico, superseded) | Porta pública SRV-1 | Backend BE3 | Estado |
|---|---:|---:|---|
| W11 / PowerShell | 2222 | 22 | proposta; não live |
| WSL / Ubuntu | 8822 | 8822 | proposta; não live |
| S23 / Termux | 8022 | 8022 | proposta; não live |

As portas acima não são a interface pública atual. O contrato as-built usa
portas públicas `8122/8222/8322` e mantém `2222/8022/8822` apenas como
hops internos selecionados por nftables. Ver
`home-proxy/docs/operations/2026-07-19-casa-edge-address-port-map.md`.

PPTP exige TCP `1723` e GRE/protocolo `47`. Nao anunciar `192.168.1.0/24`
para DRG/wg100 sem uma fase propria de routed-site. A rede canonica de servicos
continua OCI/DRG; `wg100` continua reserve/fallback.

Nota K3s/etcd: o plano atual de InternalIP usa `wg100` em
`10.100.100.1`-`10.100.100.4`. A faixa `10.1.1.0/24` foi aposentada e não deve
ser tratada como alias vivo de etcd, DNS ou reachability administrativa.

Nota DRG/WireGuard 2026-07-06: o `oci-admin` no W11-PC e o dono do plano de
OCI DRG/readdress. O plano ativo de WireGuard e `wg100` em
`10.100.100.0/24`, com hub no SRV-1 (`137.131.190.161:51821`). O plano OCI
anterior (`atius1=10.1.0.0/16`) segue rejeitado porque colidia com a antiga
faixa WireGuard `10.1.1.0/24`, hoje aposentada. O replanejamento DRG deve usar CIDRs nao
sobrepostos: `atius1=10.51.0.0/16`, `atius2=10.52.0.0/16`,
`atius3=10.53.0.0/16`, `horistic=10.71.0.0/16`; ver
`docs/operations/drg-wireguard-readdress-plan.md`.

Atualizacao 2026-07-10: o W11 foi cortado para `10.100.100.8` e o S23 para
`10.100.100.9`, alinhando a VPN com a LAN `192.168.1.8/.9` do BE3. Os antigos
`10.100.100.5` e `10.100.100.6` ficam apenas como legado/historico de rollback.

DNS: a autoridade continua no SRV-1 em `10.11.1.11:53`, com `10.100.100.1:53`
como reserve listener, e desde a Phase 16 as respostas canônicas para os
servidores apontam para a malha OCI privada.
Validação 2026-07-08:
- `dig @10.11.1.11` e `dig @10.100.100.1` a partir de `srv-2`, `srv-3` e `horistic-srv` retornaram
  `atius-srv-1/2/3/horistic-srv -> 10.11.1.11/10.12.1.12/10.13.1.13/10.21.1.21`.
- `/etc/hosts` em `srv-1`, `srv-2`, `srv-3` e `horistic-srv` agora usa os IPs
  OCI privados para os hostnames canônicos e deixa `10.100.100.x` só em aliases
  explícitos `*-wg100` / `*-vpn`.
- `dig @10.1.1.2` no `srv-1` expirou timeout; `10.1.1.2:53` deve ser tratado
  apenas como referência legada, não como endpoint DNS ativo.
Resoluções `10.1.1.x` remanescentes fora desse mapa devem ser tratadas como
drift ou rollback explícito, não como verdade canônica.

WireGuard/DNS validation 2026-06-17 (historico `wg0`):
- Chaves WireGuard rotacionadas para `atius-srv-3`, `horistic-srv`,
  `GIOVANNI-W11-PC` e `GIOVANNI-S23`; chaves privadas ficam somente nos
  hosts/configs restritos, não em docs.
- CoreDNS resolve `atius-srv-3 -> 10.1.1.3`,
  `horistic-srv -> 10.1.1.4`, `GIOVANNI-W11-PC -> 10.1.1.5`,
  `GIOVANNI-S23 -> 10.1.1.6`, `atius-mt5-kvm-1 -> 10.1.1.16` e
  `atius-mt5-kvm-2 -> 10.1.1.17`.
- `wg-quick strip wg0` OK em SRV-2, SRV-3 e Horistic.
- W11 e S23 tinham peers novos no hub e configs gerados; esse estado foi
  superseded no replanejamento `wg100` de 2026-07-06, em que W11
  `10.100.100.5` e S23 `10.100.100.6` ja tiveram handshake validado no SRV-1.
  Esse estado foi superseded pelo cutover de 2026-07-10: W11 passou a
  `10.100.100.8` e S23 a `10.100.100.9`, então alinhados com a LAN
  `192.168.1.8/.9` do BE3; `.5/.6` ficaram como historico/cleanup. O cutover
  posterior de 2026-07-23 reservou WG `.9` para S20 e `.10` para S23, ainda
  sem handshake dos handsets no primeiro readback.

Cloudflare:
- `*.atius.com.br` → origem pública SRV-1/Apache2; validação 2026-07-05
  ainda encontrou listeners em 80/443, portanto não assumir migração
  concluída para 9080/9444 sem novo `ss` + vhost audit.
- `*.horistic.com` → origem 10.1.1.4 (Apache2 horistic-srv, proxy pra 10.1.1.1:3050/8050)
- `portainer.atius.com.br`, `docker.atius.com.br` → K3s Portainer (Phase 13)
- `jenkins.atius.com.br` → 10.1.1.1:8085 (SRV-1 podman)
- `cloudbeaver.atius.com.br` → 10.1.1.1:8978 (SRV-1 podman)
- `router.atius.com.br` → SRV-1 Podman `0.0.0.0:3000`; root e
  `/api/status` retornaram `200` em 2026-07-05.
- `router.atius.com.br/docs/` → Apache target `127.0.0.1:3003`; drift
  validado 2026-07-05: porta `3003` sem listener e rota pública retorna `503`.
- `casa.atius.com.br` → record `A` proxied para Apache SRV-1 `:443`; rotas
  `/ssh` e `/rdp` via ATS/Guacamole, painel BE3 em origin dinâmico `:8888`;
  sem Tunnel e sem WireGuard no caminho final.
- `wayland.atius.com.br` → runtime Wayland no SRV-3 `0.0.0.0:25725`;
  `/api/auth/status` local e público retornaram `200` em 2026-07-05.
- `mcp.atius.com.br/gbrain` → edge público para GBrain HTTP MCP no SRV-1,
  backend local-only `127.0.0.1:3131`; `/health` retornou `200`.
- `landscape.atius.com.br` → público retorna `302`; listener `6554` não foi
  observado em `ss` no SRV-1/SRV-3 em 2026-07-05 e requer reconciliação do
  runbook de Landscape antes de documentar porta ativa.

---

## 4. Convenção de Displays / VNC / noVNC

Regra de ouro (todos os 3 SRVs):

> **Display N → VNC 5900+N, noVNC 6080+N**
> Display 0 = lightdm console (sem VNC)
> **Displays 1..14 = XRDP humano / faixa baixa**. A resolução dessa faixa
>   deve ser controlada pelo cliente RDP que conecta. Não usar watcher
>   `xrandr` fixo aqui.
> **Displays 15..30 = pool "headless helpers"** (camofox, browsers,
>   automação browser-based). Aqui a resolução pode ser fixa pelo app/serviço,
>   por exemplo Camofox/noVNC em 1366x768.
> Displays 31..60 = xrdp legacy/overflow; não é alvo primário de XRDP humano
> Displays 61+ = overflow xrdp (rare)

### Layout SRV-1 (estado-alvo pós Phase 18)

| Display | VNC   | noVNC | Owner           | Status atual (2026-06-16) | Plano 18 |
|---------|-------|-------|-----------------|---------------------------|----------|
| :0      | -     | -     | lightdm         | ativo                     | manter   |
| **:1**  | **5901** | -   | **XRDP primário SRV-1** | conectado pelo operador; resolução 1920x1080 vinda do cliente RDP | **manter** |
| :2..14  | 5902..5914 | - | XRDP humano extra | livres/reservados; resolução pelo cliente RDP | reservar |
| **:15** | **5915** | **6095** | **camofox slot 1** | :5/5905/6085 atual      | **migrar em gate separado** |
| :16..30 | 5916..5930 | 6096..6110 | pool slots 2..16 | livres; resolução fixa por app/serviço | reservar |
| :31..60 | 5931..5960 | - | xrdp legacy/overflow | não é alvo primário | reservar |
| :61+    | 5961+ | -     | xrdp overflow   | livre                     | reservar |

### Layout SRV-2 (estado-alvo)

| Display | VNC  | noVNC | Owner           | Status atual | Plano 18 |
|---------|------|-------|-----------------|--------------|----------|
| :0      | -    | -     | lightdm         | ativo        | manter   |
| **:1**  | **5901** | - | **XRDP primário SRV-2** | confirmado pelo operador via Microsoft RDP; `xvfb.service` em `:1` desabilitada | **manter** |
| :2..14  | 5902..5914 | - | XRDP humano extra | livres/reservados; resolução pelo cliente RDP | reservar |
| :15..30 | 5915..5930 | 6095..6110 | pool | livres; resolução fixa por app/serviço | reservar |
| :31..60 | 5931..5960 | - | xrdp legacy/overflow | não é alvo primário | reservar |
| :99     | -    | -     | Xvfb legacy     | ativo fora da faixa humana | investigar separado |

**INCIDENTE SRV-2 (resolvido em 2026-06-16):** `x11vnc` rodou em
`0.0.0.0:5900` exposto na WAN (pid 1678706). Bots martelavam auth
desde 2025-10. Processo e units legacy foram removidos; manter 5900 fechado.

### Layout SRV-3 (estado-alvo)

| Display | VNC  | noVNC | Owner   | Status atual | Plano 18 |
|---------|------|-------|---------|--------------|----------|
| :0      | -    | -     | lightdm | ativo        | manter   |
| **:1**  | **5901** | - | **XRDP primário SRV-3** | confirmado pelo operador via Microsoft RDP | **manter** |
| :2..14  | 5902..5914 | - | XRDP humano extra | livres/reservados; resolução pelo cliente RDP | reservar |
| :15..30 | 5915..5930 | 6095..6110 | pool | livres; resolução fixa por app/serviço | reservar |
| :31..60 | 5931..5960 | - | xrdp legacy/overflow | não é alvo primário | reservar |

### Matriz Display → Port (regra)

| Categoria  | Range      | VNC range  | noVNC range | xrdp range  |
|------------|-----------|------------|-------------|-------------|
| Console    | :0        | -          | -           | -           |
| **XRDP humano** | **:1..14** | **5901..5914** | - | via 3389 + libvnc local; resolução do cliente RDP |
| **Pool headless / Camofox** | **:15..30** | **5915..5930** | **6095..6110** | sem XRDP; resolução fixa por app/serviço |
| xrdp legacy/overflow | :31..60 | 5931..5960 | - | 5931..5960 |
| Overflow   | :61..     | 5961+      | -           | 5961+       |

---

## 5. Inventário de Portas (canônico, estado 2026-07-05)

Base inicial criada em 2026-06-16; linhas com nota `validated 2026-07-05`
foram conferidas via SSH/`ss`/`curl`. Portas sem processo atual são mantidas
somente quando representam alvo de edge ou drift operacional documentado.

### SRV-1 (10.11.1.11 OCI primary; 10.100.100.1 reserve) — production

| Porta  | Serviço                    | Bind         | PID/User | Notas                              |
|--------|----------------------------|--------------|----------|-----------------------------------|
| 22     | sshd                       | 0.0.0.0      | root     | WAN, key-based                    |
| 80     | apache2                    | 0.0.0.0      | root     | legacy (migração 9080 pendente)   |
| 111    | rpcbind                    | 0.0.0.0      | root     | nfs-utils                          |
| 443    | apache2                    | 0.0.0.0      | root     | legacy (migração 9444 pendente)   |
| 3000   | router-ai-atius            | 0.0.0.0      | podman   | validated 2026-07-05; `router.atius.com.br` root/API `200` |
| 3003   | router docs edge target    | -            | -        | drift 2026-07-05: no listener; public `/docs/` `503` |
| 3005   | next-server                | 127.0.0.1    | ubuntu   | PM2 namespace=horistic             |
| 3015   | atius-web                  | 0.0.0.0      | ubuntu   | PM2 namespace=atius (legacy)      |
| 3050   | horistic-web               | 0.0.0.0      | ubuntu   | PM2 namespace=horistic             |
| 3350   | xrdp-sesman                | 127.0.0.1    | root     | RDP control                        |
| 3389   | xrdp                       | 0.0.0.0      | xrdp     | WAN                                |
| 4000   | ?                          | 0.0.0.0      | ?        | undocumented                       |
| 5173   | vite / camofox debug?      | 127.0.0.1    | ubuntu   | investigate                       |
| 51820  | wireguard                  | 0.0.0.0      | root     | VPN hub                            |
| 5900   | x11vnc.service             | -            | -        | **inactive, kill file**            |
| 5901   | Xvnc XRDP display :1       | 127.0.0.1/session | user | efêmero durante sessão XRDP; socket `/run/xrdp/sockdir/xrdp_display_1` |
| 5905   | x11vnc camofox             | 127.0.0.1    | ubuntu   | atual em :5; alvo novo :15/5915   |
| 5915   | camofox slot 1 target      | 127.0.0.1    | ubuntu   | reservado para display :15         |
| 6080   | websockify root→:5900      | -            | -        | mapping dead removido              |
| 6085   | websockify noVNC camofox   | 127.0.0.1    | ubuntu   | atual em :5; alvo novo :15/6095   |
| 6095   | noVNC camofox slot 1 target | 127.0.0.1   | ubuntu   | reservado para display :15         |
| 631    | cups                       | 127.0.0.1    | root     | printer (pending ESM upgrade)      |
| 2379   | etcd                       | 10.11.1.11 / 10.100.100.1 | root     | K3s control plane; OCI-private preferred |
| 2380   | etcd peer                  | 10.11.1.11 / 10.100.100.1 | root     | K3s; OCI-private preferred |
| 6432   | pgbouncer                  | 10.11.1.11 / 10.100.100.1 / 127.0.0.1 | postgres | central DB; OCI-private preferred, `wg100` kept as reserve |
| 6443   | kube-apiserver             | *            | root     | K3s                                |
| 7070   | anydesk                    | 0.0.0.0      | anydesk  | remote desktop                     |
| 8015   | atius-api                  | 0.0.0.0      | ubuntu   | PM2 namespace=atius                |
| 8089   | casa-rustguac              | 127.0.0.1    | rootless podman | backend canônico browser SSH/RDP; guacd bundled `4822` |
| 8182   | casa-guacamole legado      | 127.0.0.1    | rootless podman | fallback temporário até E2E RDP 1/1 |
| 8196   | casa-remote-auth-gateway   | 127.0.0.1    | ubuntu/systemd | ATS/ticket gate de `ssh.atius.com.br` |
| 8197   | casa-rdp-auth-gateway      | 127.0.0.1    | ubuntu/systemd | ATS/CSRF de `rdp.atius.com.br` |
| 8922   | casa-ssh-relay             | 127.0.0.1    | ubuntu/systemd | RustGuac -> Horistic `10.21.1.21:22` via OCI/DRG |
| 8050   | horistic-api               | 0.0.0.0      | ubuntu   | PM2 namespace=horistic             |
| 8099   | horistic-webhook-signals   | 0.0.0.0      | ubuntu   | PM2                                |
| 8100   | hermes-adapter             | 127.0.0.1    | ubuntu   | node                               |
| 8199   | atius-webhook-signals      | 0.0.0.0      | ubuntu   | PM2                                |
| 8310   | python script              | 0.0.0.0      | ubuntu   | undocumented (investigar)          |
| 8745   | postgresql direto          | 0.0.0.0      | postgres | validated 2026-07-05; clients devem usar pgbouncer 6432 |
| 8978   | cloudbeaver                | 0.0.0.0      | podman   | validated 2026-07-05               |
| 9090   | cockpit                    | *            | root     | break-glass; validar gate antes de expor |
| 9100   | node-exporter              | *            | root     | K3s/Prom                           |
| 9377   | camofox API                | *            | ubuntu   | Hermes browser tool                |
| 10000  | webmin                     | 0.0.0.0      | root     | admin panel                        |
| 10250  | kubelet                    | *            | root     | K3s                                |
| 12002  | nxnode                     | 127.0.0.1    | ubuntu   | NoMachine                          |
| 3131   | gbrain HTTP MCP            | 127.0.0.1    | ubuntu   | local-only backend; public URL `https://mcp.atius.com.br/gbrain` |
| 27124  | obsidian-local-rest-api    | 10.11.1.11   | ubuntu   | HTTPS REST + MCP via DRG primary path; wg100 peers secondary |
| 12004  | nxnode                     | 127.0.0.1    | ubuntu   | NoMachine                          |
| 12006  | nxnode                     | 127.0.0.1    | ubuntu   | NoMachine                          |
| 18080  | node (router ai?)          | 127.0.0.1    | ubuntu   | investigate                        |
| 21585  | electron                   | 127.0.0.1    | ubuntu   | AionUi (fork)                      |
| 22188  | ?                          | 127.0.0.1    | ?        | undocumented                       |
| 24342  | ?                          | 127.0.0.1    | ?        | undocumented                       |
| 25809  | electron (AionUi)          | 0.0.0.0      | ubuntu   | tray app                           |

### SRV-2 (10.12.1.12 OCI primary; 10.100.100.2 reserve) — development

| Porta  | Serviço                    | Bind         | PID/User | Notas                              |
|--------|----------------------------|--------------|----------|-----------------------------------|
| 22     | sshd                       | [::]         | root     | WAN                                |
| 25     | postfix                    | 0.0.0.0      | root     | SMTP out                           |
| 53     | systemd-resolved stubs     | 127.0.0.53 / 127.0.0.54 | systemd-resolved | DNS local; canonical upstream interno deve ser o SRV-1/10.11.1.11 |
| 80     | apache2                    | *            | root     | legacy                             |
| 111    | rpcbind                    | [::]         | root     |                                    |
| 139    | samba                      | 0.0.0.0      | root     | SMB                                |
| 443    | apache2                    | *            | root     | legacy                             |
| 445    | samba                      | [::]         | root     | SMB                                |
| 3389   | xrdp                       | *            | xrdp     |                                    |
| 3350   | xrdp-sesman                | 127.0.0.1    | root     |                                    |
| 5173   | vite / debug               | 0.0.0.0      | ubuntu   |                                    |
| 5432   | postgresql                 | 127.0.0.1    | postgres | NEW-API DB                         |
| 5900   | x11vnc legacy              | -            | -        | removido/killed 2026-06-16; manter fechado |
| 5901   | Xvnc XRDP display :1       | 127.0.0.1/session | user | efêmero durante sessão XRDP; smoke OK 2026-06-16 |
| 6080   | websockify/noVNC           | 0.0.0.0      | root     | validated 2026-07-05; revisar exposure/gate |
| 631    | cups                       | 127.0.0.1    | root     |                                    |
| 2379   | etcd                       | 10.12.1.12 / 10.100.100.2 | root     | K3s; OCI-private preferred |
| 2380   | etcd peer                  | 10.12.1.12 / 10.100.100.2 | root     | K3s; OCI-private preferred |
| 6443   | kube-apiserver             | *            | root     | K3s                                |
| 6444   | K3s                        | 127.0.0.1    | root     | K3s                                |
| 8000   | python (3 procs)           | 127.0.0.1    | ubuntu   | router-ai-zentrius                 |
| 8053   | systemd-resolved stub      | *            | systemd- | (disabled per Phase 1)             |
| 9100   | node-exporter              | *            | root     |                                    |
| 9230   | electron (AionUi)          | 127.0.0.1    | ubuntu   |                                    |
| 10010  | ?                          | 127.0.0.1    | ?        | K3s related?                       |
| 10250  | kubelet                    | *            | root     | K3s                                |
| 12063  | electron (AionUi)          | 127.0.0.1    | ubuntu   |                                    |
| 25809  | electron (AionUi)          | 0.0.0.0      | ubuntu   |                                    |
| 3000   | next-server                | *            | ubuntu   | PM2                                |

### SRV-3 (10.13.1.13 OCI primary; 10.100.100.3 reserve) — sandbox

| Porta  | Serviço                    | Bind         | PID/User | Notas                              |
|--------|----------------------------|--------------|----------|-----------------------------------|
| 22     | sshd                       | [::]         | root     |                                    |
| 25     | postfix                    | 0.0.0.0      | root     |                                    |
| 53     | systemd-resolved           | 127.0.0.54   | systemd- |                                    |
| 111    | rpcbind                    | [::]         | root     |                                    |
| 80     | apache2                    | *            | root     | validated 2026-07-05               |
| 443    | apache2                    | *            | root     | validated 2026-07-05               |
| 3389   | xrdp                       | *            | xrdp     |                                    |
| 3350   | xrdp-sesman                | 127.0.0.1    | root     |                                    |
| 5901   | Xvnc XRDP display :1       | 127.0.0.1/session | user | efêmero durante sessão XRDP; smoke OK 2026-06-16 |
| 631    | cups                       | 127.0.0.1    | root     | pending ESM upgrade (8 cups pkgs)  |
| 8080   | OCI Admin web/API          | 10.13.1.13   | ubuntu/PM2 | `oci-admin-web`, namespace `oci-admin`; `/healthz`; OCI/DRG primary |
| 8088   | Vaultwarden/private gateway | 10.13.1.13 / 10.100.100.3 | podman/systemd | OCI-private preferred via local proxy; `wg100` reserve |
| 8090   | OCI Admin MCP HTTP         | 10.13.1.13   | ubuntu/PM2 | `oci-admin-mcp-http`; public `/oci-admin`; OCI/DRG primary |
| 8202   | HashiCorp Vault HTTPS      | 10.13.1.13 / 10.100.100.3 | podman/systemd | OCI-private preferred via local proxy; `wg100` reserve |
| 8203   | HashiCorp Vault cluster    | 10.13.1.13 / 10.100.100.3 | podman/systemd | OCI-private preferred via local proxy; `wg100` reserve |
| 2379   | etcd                       | 10.13.1.13 / 10.100.100.3 | root     | K3s; OCI-private preferred |
| 2380   | etcd peer                  | 10.13.1.13 / 10.100.100.3 | root     | K3s; OCI-private preferred |
| 6443   | kube-apiserver             | *            | root     | K3s                                |
| 6444   | K3s                        | 127.0.0.1    | root     | K3s                                |
| 8310   | python script              | 0.0.0.0      | ubuntu   | undocumented                       |
| 9100   | node-exporter              | *            | root     |                                    |
| 10010  | ?                          | 127.0.0.1    | ?        | K3s related?                       |
| 10250  | kubelet                    | *            | root     | K3s                                |
| 25725  | Wayland runtime            | 0.0.0.0      | ubuntu   | validated 2026-07-12; local/public auth status `200` |


### horistic-srv (10.21.1.21 OCI primary; 10.100.100.4 reserve) — reverse proxy / k3s worker

| Porta  | Serviço                    | Bind         | PID/User | Notas                              |
|--------|----------------------------|--------------|----------|-----------------------------------|
| 22     | sshd                       | 0.0.0.0 / [::] | root   | SSH via VPN/public alias          |
| 80     | apache2                    | *            | root     | Horistic public reverse proxy      |
| 443    | apache2                    | *            | root     | Horistic public reverse proxy      |
| 111    | rpcbind                    | 0.0.0.0 / [::] | root   | system service                     |
| 631    | cups                       | 127.0.0.1 / [::1] | root | local printer service              |
| 3350   | xrdp-sesman                | [::1]        | root     | RDP control                        |
| 3389   | xrdp                       | *            | xrdp     | RDP                                |
| 6080   | websockify/noVNC           | 0.0.0.0      | root     | remote desktop bridge              |
| 6444   | K3s agent local endpoint   | 127.0.0.1 / [::1] | root | k3s worker                         |
| 8746   | local service              | 127.0.0.1    | -        | investigate                        |
| 9100   | node-exporter              | *            | root     | Prometheus                         |
| 10010  | K3s related                | 127.0.0.1    | root     | local agent service                |
| 10248  | kubelet healthz            | 127.0.0.1    | root     | K3s                                |
| 10249  | kube-proxy metrics         | 127.0.0.1    | root     | K3s                                |
| 10250  | kubelet                    | *            | root     | K3s                                |
| 10256  | kube-proxy healthz         | 127.0.0.1    | root     | K3s                                |
| 22061  | local service              | 127.0.0.1    | -        | investigate                        |
| 31115  | TEI GTE embeddings HA      | 10.21.1.21 NodePort | k3s/containerd | `ebeddings-local/tei-gte`, two pods on `horistic-srv` |
| 31216  | TEI GTE reranker FP16      | 10.21.1.21 NodePort | k3s/containerd | `ebeddings-local/tei-gte-reranker`, private router upstream |

Validated 2026-08-21: the OCI-primary private NodePort at `10.21.1.21:31115`
balances two ready TEI pods and returns health `200`; public `embedding-gte-v1`
through `https://router.atius.com.br/v1/embeddings` returns 768-dimensional vectors.

The former `10.21.1.21:3115` host-network listener is retired. The
`10.100.100.4:3115` path remains a reserve fallback only. Router channel `11`
is `Atius Local` with primary upstream `http://10.21.1.21:31115`.

Validated 2026-07-22: `10.21.1.21:31216` serves two ready FP16 reranker pods,
with HPA 2-4 and 500m per pod. The public alias
`reranker-gte-v1` remains behind the governed router route
`/v1/rerank`; there is no direct public Ingress for TEI.

### MT5 KVM execution VMs (sem K3s)

| Porta | Serviço | Bind | PID/User | Notas |
|---|---|---|---|---|
| 22 | sshd | 0.0.0.0 / [::] | root | key `/home/ubuntu/.ssh/id_oracle` |
| 9001 | SlaveEA signal receiver | 0.0.0.0 | ubuntu/python3 | `atius-mt5-kvm-1` |
| 9002 | SlaveEA signal receiver | 0.0.0.0 | ubuntu/python3 | `atius-mt5-kvm-2` |
| 9100 | prometheus-node-exporter | * | prometheus | monitoramento omni/prometheus |

Notas:
- `atius-mt5-kvm-1` e `atius-mt5-kvm-2` **não** entram no K3s neste momento.
- Runtime validado 2026-06-17: zsh default, Oh My Zsh, rustc/cargo 1.96.0, cargo-binstall 1.20.0, zellij 0.44.3.
- Prompt esperado: `ubuntu@atius-mt5-kvm-N:~/path ➜`.

---

## 6. Portas Reservadas (ranges por categoria)

| Categoria       | Range          | Bind          | Service                 |
|-----------------|----------------|---------------|--------------------------|
| Console/Lightdm | :0             | local         | lightdm                   |
| **XRDP humano** | **:1..14**     | **local via 3389** | **xrdp + Xvnc + libvnc; resolução pelo cliente RDP** |
| **Pool headless** | **:15..30**  | **127.0.0.1** | **camofox/headless; resolução fixa por app/serviço** |
| xrdp legacy/overflow | :31..60   | mixed         | não usar como alvo primário |
| WireGuard       | 51820          | 0.0.0.0       | SRV-2 hub                |
| SSH             | 22             | 0.0.0.0       | todos                    |
| RDP             | 3389, 3350     | 3389 WAN      | xrdp                     |
| Casa gateways   | 8196, 8197     | 127.0.0.1     | Node ATS/ticket/CSRF gates |
| Casa RustGuac   | 8089; bundled guacd 4822 | 127.0.0.1 / rootless | browser SSH/RDP |
| Casa residential NAT | 8122, 8222, 8322, 3389 | BE3 WAN, source SRV-1 only | W11/WSL/S23/RDP |
| Casa native SSH relay | 2222, 8822, 8022 | interno protegido por nft | live; não publicar diretamente |
| Cloudflare Origin | 9080, 9444   | 127.0.0.1     | Apache2 (Plane 2 mig)   |
| K3s API         | 6443, 6444     | mixed         | K3s                      |
| K3s etcd        | 2379, 2380     | 10.11/10.12/10.13/10.21 preferred, `wg100` reserve | K3s |
| K3s kubelet     | 10250          | *             | K3s                      |
| Prometheus node-exporter | 9100 | *             | K3s                      |
| Local TEI embeddings | 31115      | 10.21.1.21  | K3s `ebeddings-local/tei-gte`, two-pod Service |
| Local TEI reranker | 31216       | 10.21.1.21  | K3s `ebeddings-local/tei-gte-reranker` |
| PgBouncer       | 6432           | 10.11.1.11  | central DB               |
| Obsidian REST/MCP | 27124        | 10.11.1.11  | AiSecondBrain via OCI/DRG |
| GBrain HTTP MCP | 3131           | 127.0.0.1     | SRV-1 local backend; public edge `mcp.atius.com.br/gbrain` |
| OCI Admin web/MCP | 8080, 8090   | 10.13.1.13    | SRV-3 PM2 namespace `oci-admin`; public `/` and `/oci-admin` |
| Router Web/API  | 3000           | 0.0.0.0       | SRV-1 Podman `router-ai-atius` |
| Router docs target | 3003        | 127.0.0.1     | target esperado; drift atual sem listener |
| Wayland runtime | 25725          | 0.0.0.0       | SRV-3 `wayland.service` |
| Camofox API     | 9377           | 127.0.0.1     | Hermes                   |
| Camofox VNC     | 5915..5930     | 127.0.0.1     | display :15..30          |
| Camofox noVNC   | 6095..6110     | 127.0.0.1     | display :15..30          |
| Webmin          | 10000          | 0.0.0.0       | SRV-1 only               |
| AnyDesk         | 7070           | 0.0.0.0       | SRV-1 only               |

---

## 7. Procedimentos (operational)

### 7.1 Adicionar slot camofox (ex: slot 2 no display :16)

1. Editar `/home/ubuntu/.config/camofox-browser.env`:
   ```
   CAMOFOX_BROWSER_DISPLAY=:16
   VNC_PORT=5916
   NOVNC_PORT=6096
   CAMOFOX_API_KEY=<nova key>
   ```
2. Criar profile dir: `~/.local/state/camofox-browser/profiles/slot2/`
3. Copiar / criar unit novo: `~/.config/systemd/user/camofox-slot2-{display,browser}.service`
4. `systemctl --user daemon-reload && systemctl --user enable --now camofox-slot2-display.service camofox-slot2-browser.service`
5. Validar: `ls /tmp/.X11-unix/X16`; `ss -tlnp | grep -E ":5916|:6096"`
6. Smoke test noVNC: `curl -I http://127.0.0.1:6096/`

### 7.2 Remover slot camofox (cleanup)

1. `systemctl --user stop --now camofox-slot2-{display,browser}.service`
2. `systemctl --user disable camofox-slot2-{display,browser}.service`
3. Remover unit files
4. Remover profile dir (com backup)
5. Verificar sockets: `ls /tmp/.X11-unix/X16` (deve sumir)
6. Verificar port: `ss -tlnp | grep ":5916"` (deve sumir)

### 7.3 Fix XRDP humano (post Phase 18)

Sintoma: RDP login screen aparece, sesman autentica, mas Xorg não
sobe, cai em `VNC error 1 after security negotiation`, ou entra em display
`:31` em vez de `:1`.

Diagnóstico:
```bash
ss -tlnp | grep 5910
journalctl -u xrdp-sesman --since "10 minutes ago" -p err
tail -20 /var/log/xrdp-sesman.log
```

Causa original: porta 5910 colidindo com x11vnc (camofox legado em :97)
quando xrdp usava display :10. Depois do teste com `:31`, a frota ainda
ficava inconsistente e SRV-2/SRV-3 continuavam apontando para `:31`.

Fix atual nos 3 SRVs: XRDP humano usa display `:1`, `X11DisplayOffset=1`,
`lib=libvnc.so`, `port=-1`, `code=0`, `delay_ms=6000`; o `Xvnc` é
local-only, `SecurityTypes None`, `Protocol3.3`, e publica
`/run/xrdp/sockdir/xrdp_display_1` com mode `0660` para o grupo `xrdp`.
`/etc/xrdp/startwm.sh` inicia LXDE e não chama watcher `1366x768`.

Regra de resolução:

- Displays `:1..14`: resolução controlada pelo cliente RDP.
- Displays `:15..30`: resolução fixa permitida para Camofox/noVNC/headless.
- Não colocar `Xvfb` fixo em `:1`; no SRV-2 a unit `xvfb.service` foi
  desabilitada por bloquear o XRDP primário.

### 7.4 ESM Apps / Ubuntu Pro (Phase 18 escopo)

Target: 3 SRVs com `esm-apps` + `esm-infra` enabled, account
giovannimunizds@gmail.com, sources em formato `.sources` (DEB822).

Idempotent attach (rodar em cada SRV):
```bash
mkdir -p ~/secrets
# token já em ~/secrets/ubuntu-pro-token.txt (mode 600)
sudo pro detach || true
sudo pro attach --token-stdin < ~/secrets/ubuntu-pro-token.txt
sudo pro enable esm-apps
sudo pro enable esm-infra
# Validar
pro status --format json | python3 -c "import sys,json; d=json.load(sys.stdin); s=[x for x in d['services'] if x['name']=='esm-apps'][0]; assert s['status']=='enabled'; print('esm-apps OK')"
# Validar formato .sources
test -f /etc/apt/sources.list.d/ubuntu-esm-apps.sources && echo ".sources OK"
```

Pendentes ESM (pré-upgrade 2026-06-16):
- SRV-1: 5 freerdp2-x11/libfreerdp/libwinpr2 (esm-apps)
- SRV-3: 7zip, buildah (esm-apps) + 8 cups-* (noble-security)
- SRV-2: (nenhum ESM; só noble-security)

Upgrade gated em janela separada.

---

## 8. Cross-References

- Repo: `inventory/hosts/*.yaml` (fonte canônica de IPs/SSH)
- Repo: `/etc/omni-srv-admin/fleet-peers.json` (live)
- Repo: `.planning/STATE.md` (machines status)
- Repo: `.planning/MILESTONES.md`
- Repo: `.planning/phases/13-k3s-ha-portainer-oci/13-CONTEXT.md` (Ubuntu Pro gate)
- Repo: `.planning/phases/13-k3s-ha-portainer-oci/13-GATE-REVIEW-2026-06-14.md`
- Repo: `.planning/phases/14-resource-governor-pm2-boot-hardening/14-03-*.md` (xrdp watchdog)
- Repo: `docs/operations/local-ai-embeddings.md` (TEI/GTE `10.100.100.4:3115` + router alias)
- Repo: `docs/operations/gbrain-embedding-migration.md` (GBrain/Obsidian/Graphify embedding contract)
- Repo: `docs/operations/codex-mcp-startup-standard.md` (Codex MCP startup profiles and smoke checks)
- Repo: `docs/operations/oci-admin-pm2-runtime.md` (PM2, Vault, watchdog e recovery do OCI Admin no SRV-3)
- Repo: `docs/operations/wayland-managed-runtime.md` (Wayland SRV-3 managed runtime)
- Repo externo: `vpn-atius/home-proxy/docs/operations/2026-07-19-casa-ssh-rdp-gateway.md`
  (Casa Cloudflare/Apache/ATS/Guacamole/BE3 port map detalhado)
- Vault: `60-LOGS/2026-07-19-casa-ssh-rdp-gateway.md`
- Repo: **`modules/fleet/podman-network/`** (standard podman networking 3-SRV — **novo 2026-06-16**)
- Vault: `99-Referencias/atius-home-server-overview.md` (legado, redirecionar)
- Vault: `17-DevTools-Workflow/17.08-Obsidian-Local-REST-API-MCP-Setup.md` (RDP :10)
- Vault: `60-LOGS/2026-06-16-port-pool-rdp-camofox-network-doc.md` (a criar)
- Vault: **`60-LOGS/2026-06-16-fleet-podman-network-standardize.md`** (cutover fleet podman 2026-06-16)
- Vault: **`60-LOGS/2026-06-16-plane-app-podman-v131-cutover.md`** (cutover plane-app 2026-06-16)
- Skill: **`devops/podman-fleet-standardize/`** (canonical skill: drift-detect, apply, smoke-test)
- Skill: `devops/fleet-port-audit/` (cross-server ss scan)
- Skill: `devops/service-port-migration/` (port migration playbook)
- Skill: `notebooklm-bridge-camofox-install/` (camofox install, v1.1.0 a bumpar)
- Skill: `devops/abnt2-keyboard-fix/` (display :10 LXDE)

---

## 9. Operational Drift / Reconciliation Queue

Validado em 2026-07-05:

- `router.atius.com.br` Web/API esta saudavel em `3000`, mas
  `router.atius.com.br/docs/` retorna `503` porque `127.0.0.1:3003` nao esta
  ouvindo. Corrigir servico docs ou atualizar vhost para a rota real.
- `gbrain-http-mcp.service` esta ativo em `127.0.0.1:3131`; evitar
  `systemctl status` completo em logs compartilhados, porque o banner de boot
  pode conter token administrativo. Preferir `systemctl show` + `/health`.
- K3s tem 4 nos `Ready`; `atius-srv-3` ainda aparece com `INTERNAL-IP
  10.1.1.7` por compatibilidade de etcd.
- Pods de `monitoring`/`portainer` apareceram parcialmente degradados no
  inventario remoto; abrir validacao separada antes de declarar stack de
  observabilidade/Portainer saudavel.
- `landscape.atius.com.br` retorna `302`, mas a porta `6554` citada em docs
  auxiliares nao foi observada como listener live no SRV-1/SRV-3.

## 10. Changelog

- **1.7.9 (2026-07-23)** — validou em headless a cadeia RDP ate o formulario
  canonico autenticado, com CSRF e senha Microsoft obrigatoria vazia. Como a
  credencial correta nao existe no Vault, nenhum POST foi autorizado e
  WebSocket/NLA/desktop ficaram `NOT RUN`.
- **1.7.8 (2026-07-23)** — reconciliou o browser headless apos a correcao
  BE3: W11/WSL `200` + WebSocket `101` + `connected`; S23 launcher `200` +
  WebSocket `101`, mas `disconnected`. S20 segue sem card, aliases browser
  `404` e zero WebSocket.
- **1.7.7 (2026-07-23)** — apos backup nativo, corrigiu as quatro regras
  BE3 para `Remote Host=137.131.190.161`. Probes externos no SRV-3
  confirmaram banners e host keys de W11 `8122` e WSL `8222`; S23 `8322`
  ainda fechou antes do KEX. A automacao periodica de healthcheck por timeout
  foi rejeitada e removida por nao provar troca do WAN; promocao automatica
  continua `NO-GO`. S20 e RDP/browser continuam gates separados.
- **1.7.6 (2026-07-23)** — reconciliou S23/S20 com o estado live: reservas
  BE3 `.10`/`.9` e MACs atuais; hub WG `.10`/`.9` ainda sem handshake;
  S20 ainda em lease antigo `.62`; slots `8422/8522` apenas reservados.
  Registrou também o incidente DNS Casa por WAN novo `191.31.48.191` fora do
  allowlist e o drift das regras BE3/relay para IPs antigos/incorretos. A
  promoção governada corrigiu o allowlist DNS e o W11 voltou a resolver pelo
  DNS Casa; a correção NAT/relay posterior está registrada na 1.7.7.
- **1.7.5 (2026-07-23)** — backend LAN/BE3 do `GIOVANNI-S23` movido para
  `192.168.1.10:8022`; NAT `GIOVANNI-S23-SSH` preserva TCP externo `8322`,
  interno `8022`. Probe via WSL confirmou a host key ED25519 pinada do S23
  no novo backend. A afirmação WG `.9` foi superseded pela 1.7.6.
- **1.7.4 (2026-07-22)** — Phase 07 consolidou W11/WSL/S23 no shared IP
  `137.131.140.20` com portas `8122/8222/8322`; split-IP anterior foi mantido
  apenas como rollback retained e validado por drill/reapply completos.
- **1.7.3 (2026-07-22)** — ordem operacional de SSH registrada para W11, WSL,
  S23 e Horistic: após qualquer falha no caminho privado, testar a rota pública
  nativa sem WireGuard antes de declarar indisponibilidade. S23 validado em
  `10.100.100.9:8022` e em
  `ssh-giovanni-s23.atius.com.br:8322` com usuário `termux`; o estado atual do
  S23 é `GO`, superseding o `DEGRADED` registrado no delta histórico 1.7.2.
- **1.7.1 (2026-07-19)** — status Casa corrigido para runtime ativo/release
  externa `NO-GO`; blockers reproduzidos e portas HAProxy propostas
  `2222/8022/8822` separadas das portas NAT live. Nenhuma porta raw RDP.
- **1.7.0 (2026-07-19)** — Casa Remote Gateway promovido a produção no mapa:
  Cloudflare HTTPS/WSS -> Apache SRV-1 -> ATS/Guacamole -> NAT BE3, com portas
  internas `8015/8182/8080/8196/4822`, WAN residencial
  `22/8022/8822/3389`, LAN `192.168.1.8/.9`, usuários e source allowlist do
  SRV-1. Sem Cloudflare Tunnel e sem WireGuard no caminho final.
- **1.6.2 (2026-07-13)** — verdade local/remota reconciliada: W11
  `10.100.100.8` e S23 `10.100.100.9` sao os edge IPs live; `.5/.6` ficam
  somente como historico/cleanup, e as reservas LAN BE3 `.8/.9` permanecem
  separadas da identidade OCI/DRG e do fallback `wg100`.
- **1.6.1 (2026-07-10)** — cutover dos edge clients concluido e validado com
  handshake no SRV-1; W11 saiu de `.5` para `.8` e S23 de `.6` para `.9`.
- **1.5.2 (2026-07-12)** — runtime Wayland reconciliado com o estado live:
  `User=ubuntu`, `PORT=25725`, Apache SRV-1 para `10.13.1.13:25725`, e
  healthchecks local/public em `200`; referências operacionais `25808` foram
  mantidas apenas como histórico de 2026-07-05.
- **1.5.1 (2026-07-08)** — DNS interno canônico consolidado no SRV-1
  (`10.100.100.1:53`); `nslookup`/`dig` no W11, SRV-1 e Horistic devolveram a
  malha `10.100.100.x`, e `10.1.1.2:53` expirou timeout, ficando classificado
  como referência legada apenas.
- **1.5.0 (2026-07-05)** — consolidado delta live de MCP/edge/router:
  GBrain HTTP MCP `127.0.0.1:3131` com edge `mcp.atius.com.br/gbrain`,
  Wayland SRV-3 `0.0.0.0:25808`, router Web/API em `3000`, drift de docs em
  `3003`, Obsidian REST/MCP `10.11.1.11:27124` como caminho primario via DRG,
  K3s 4 nos Ready e fila de reconciliacao para Landscape/Portainer/monitoring.
- **1.4.1 (2026-06-29)** — Obsidian Local REST API + MCP centralizado no
  SRV-1 em `10.11.1.11:27124`, com acesso direto via VPN para SRV-2/SRV-3 e
  allowlist `OMNI-OBSIDIAN-REST`; padrão antigo por SSH tunnel local removido.
- **1.4.0 (2026-06-17)** — renomeado `horistic-srv-1` → `horistic-srv` (host + inventory + VPN/CoreDNS + docs); `horistic-srv-1` permanece como alias uppercase em CoreDNS para retrocompat; vhost Apache `remote.horistic-srv-1.atius.com.br.conf` preservado.
- **1.3.0 (2026-06-17)** — adicionados `atius-mt5-kvm-1` e `atius-mt5-kvm-2` como hosts gerenciados sem K3s: IPs 10.1.1.16/17, portas 9001/9002, node-exporter 9100, zsh/Oh My Zsh/Rust/zellij validados e inventory `inventory/hosts/atius-mt5-kvm-*.yaml`.

- **1.2.1 (2026-06-17)** — rotação de chaves WireGuard para SRV-3,
  Horistic, W11 e S23; SRV-2 ajustado para usar CoreDNS local via
  `systemd-resolved`; Horistic ajustado para resolver primeiro via
  `10.1.1.2`; `/etc/hosts` canônico aplicado em SRV-1/SRV-2/SRV-3/Horistic. Em 2026-06-17 o host `horistic-srv-1` foi renomeado para `horistic-srv` (WireGuard key e IP não mudam; vhost Apache `remote.horistic-srv-1.atius.com.br.conf` mantido por compatibilidade).
  Revalidado: K3s 3/3 Ready, ping `.3/.4`, Horistic ping `.2/.1/.3`,
  CoreDNS `.3/.4/.5/.6`, e `wg-quick strip wg0` em SRV-2/SRV-3/Horistic.
  W11/S23 aguardam importação local dos configs novos para handshake.
- **1.2.0 (2026-06-16)** — adicionado cross-ref ao módulo novo
  `modules/fleet/podman-network/` e à skill
  `devops/podman-fleet-standardize/`. Padronização do networking podman
  nos 3 SRVs (containers.conf + netavark + aardvark + systemd-resolved).
  Network `srv<N>-podman` com `dns_enabled=true`, subnet `10.10.<N>.0/24`.
  Aardvark-dns funcional nos 3 servers com forward DNS externo via
  systemd-resolved. Mailcow (SRV-2) recuperado do estado Exited 45h
  via `apt install systemd-resolved`.
- 1.1.3 (2026-06-16) — fechamento operacional do ajuste XRDP: operador
  confirmou Microsoft RDP funcional em SRV-1, SRV-2 e SRV-3. O ajuste XRDP
  fica concluído; `:1..14` permanece como faixa humana com resolução guiada
  pelo cliente, e `:15..30` como faixa headless/fixa.
- 1.1.2 (2026-06-16) — SRV-2/SRV-3 saíram de `:31` e foram alinhados ao
  padrão funcional do SRV-1: XRDP humano primário em `:1`, smoke RDP OK nos
  dois com resolução `1280x720` vinda do cliente. Regra de resolução
  consolidada: `:1..14` controlado pelo cliente RDP; `:15..30` pode ser fixo
  por app/serviço, especialmente Camofox/noVNC. SRV-2 `xvfb.service` em `:1`
  desabilitada.
- 1.1.1 (2026-06-16) — SRV-1 recebeu override operacional: XRDP primário
  fixo em display `:1`; `:31..60` virou expansion/overflow para SRV-1.
  Documentado fix `libvnc` + `Xvnc` com socket Unix
  `/run/xrdp/sockdir/xrdp_display_1`.
- 1.1.0 (2026-06-16) — reserva baixa ampliada de :1..4 para :1..14;
  pool headless ampliado/deslocado de :5..9 para :15..30; xrdp deslocado
  para :31..60 mantendo 30 sessoes simultaneas; overflow agora :61+.
- 1.0.0 (2026-06-16) — versão inicial. Consolida atius-fleet-specs +
  Atius-Spec-Servers + atius-home-server-overview + SERVER-AUDIT
  + 17.08 Obsidian. Adiciona pool :5..9 + matriz display/port.
  Inclui ESM Apps attach procedure + port pool :5..9 migration.
  Owner: giovanni. Validated against live ss on 3 SRVs.
