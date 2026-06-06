# Omni Srv Admin (omni-srv-admin)

Repositório central de configuração e provisionamento multi-tenant do servidor omni (10.1.1.1 Oracle Cloud). Contém scripts de instalação padrão, configurações de rede (iptables, WireGuard), antiviral, tema desktop, e o módulo de Infraestrutura de Domínio Linux (FreeIPA + Keycloak + Samba) para autenticação centralizada e SSO web.

**Core Value:** Servidor Atius sempre provisionado, documentado e operante — com identidade centralizada para login unificado de todas as máquinas Linux e SSO web funcionando em paralelo.

---

## Stack

- **OS:** Ubuntu 22.04 (Oracle Cloud Infrastructure, ARM64)
- **Node.js:** v24.13.1 via NVM
- **Python:** 3.11 via `uv`
- **Database:** PostgreSQL 17 (porta 8745), MongoDB (porta 27017)
- **Reverse Proxy:** Apache2 com 60+ vhosts
- **Container Runtime:** Docker + containerd (~25 containers)
- **Process Manager:** PM2 (API, frontend, webhooks, bots de trading)
- **Domain:** atius.com.br via Cloudflare
- **Rede:** WireGuard VPN 10.1.1.0/24

---

## Módulos

### domain-infrastructure/
FreeIPA + Keycloak + Samba para autenticação centralizada e SSO web.

- FreeIPA rodando em container Docker (AlmaLinux 9) — LDAP + Kerberos + CA
- Keycloak nativo no OS, federado no LDAP do FreeIPA
- Samba com autenticação via FreeIPA/Kerberos
- SSO web funcional em `auth.atius.com.br`
- Compartilhamentos de arquivos acessíveis por máquinas no domínio
- Migração de WireGuard e Samba do servidor 10.1.1.2 para 10.1.1.1

**Estrutura:**
```
domain-infrastructure/
├── CLAUDE.md       # Documentação detalhada do projeto
├── configs/        # Configurações de FreeIPA, Keycloak, Samba
├── docker/         # Dockerfiles e compose para FreeIPA
└── scripts/        # Scripts de provisionamento
```

### iptables/
Regras de firewall salvas e restauráveis.

- `iptables-backup-v4.conf` — Regras IPv4
- `iptables-backup-v6.conf` — Regras IPv6
- Aplicadas automaticamente pelo `setup.sh` e persistidas com `netfilter-persistent`

### antivirus/
Scripts de monitoramento e verificação antiviral.

- `monitor.sh` — Monitoramento contínuo
- `scan.sh` — Verificação sob demanda

### dark-theme-ubuntu/
Tema dark personalizado para LXDE + Zsh + Fontes Apple + Sublime Text.

- Sublime Text ARM64 como editor padrão
- Modo escuro completo com alto contraste
- Fontes Apple (SF Pro, SF Mono, etc.) e Microsoft Core Fonts
- Oh My Zsh com plugins de syntax highlighting

**Estrutura:**
```
dark-theme-ubuntu/
├── install.sh      # Script de instalação
├── repair.sh       # Script de reparo
├── uninstall.sh    # Script de desinstalação
├── themes/         # Arquivos de tema LXDE/Openbox
├── fonts/          # Fontes Apple e Microsoft
└── config_files/   # Configurações do sistema
```

### modules/xrdp-abnt2/
Guard operacional para manter XRDP + LXDE em Português Brasil ABNT2 no fluxo Windows 11 RDP → Ubuntu.

- Mapeia `00010416`, `0000F010` e fallback `00000409` para `br(abnt2)`
- Instala keymaps XRDP ABNT2 idênticos para todos os layouts críticos
- Aplica `setxkbmap br abnt2` no início da sessão e mantém watchdog a cada 5s
- Reaplica a correção após updates via hook APT/DPKG
- Integrado ao CLI: `omni xrdp-abnt2 status|validate|diff|install`

**Estrutura:**
```
modules/xrdp-abnt2/
├── README.md        # Runbook canônico
├── files/           # Assets instaláveis em /etc, /usr/local e ~/bin
├── scripts/         # Wrappers install/validate
└── docs/            # Histórico original migrado
```

### vscode-profile/
Perfil e extensões do VSCode para o ambiente de desenvolvimento.

- `Giovanni (ubuntu).code-profile` — Backup do perfil
- `Extensions/` — Extensões pré-instaladas
- `atius-1.code-workspace`, `atius-2.code-workspace` — Workspaces

---

## Instalação

### Requisitos

- Ubuntu 22.04 (Oracle Cloud Infrastructure, ARM64)
- Acesso sudo
- Git

### Passos

```bash
# Clone o repositório
git clone https://github.com/giovannimnz/omni-srv-admin.git
cd omni-srv-admin

# Torne o script executável
chmod +x setup.sh

# Execute (necessário rodar como sudo)
sudo ./setup.sh
```

### Instalação em 2 Etapas

O script `setup.sh` é dividido em duas etapas:

**Etapa 1 — Preparação do Sistema:**
- Atualização do sistema
- Instalação de tooling básico (nano)
- PostgreSQL 18
- Configuração de SWAP (10GB)
- Instalação de LXDE + XRDP (ambiente gráfico)
- Instalação e configuração de iptables + iptables-persistent
- Restauração das regras de firewall salvas em `iptables/`
- **Ao final, o servidor será reiniciado automaticamente**

**Etapa 2 — Aplicativos e Tema:**
- Chromium + trickle (limitador de banda)
- CopyQ (gerenciador de clipboard)
- Atalho na área de trabalho
- Instalação do tema dark (dark-theme-ubuntu/install.sh)

```bash
# Após reiniciar, conecte-se via RDP/SSH e execute novamente
sudo ./setup.sh
# Selecione a opção 2
```

---

## Ambiente Atual

| Servidor | Função |
|----------|--------|
| 10.1.1.1 | Este servidor: Atius apps (PM2), ~25 containers Docker, PostgreSQL 17, MongoDB, Apache2 |
| 10.1.1.2 | WireGuard VPN + CoreDNS + Samba (será migrado para 10.1.1.1) |
| 10.1.1.3 | Apache2 para Horistic |

---

## Validações

| ID | Descrição | Status |
|----|-----------|--------|
| SRV-01 | Script `setup.sh` executa provisionamento base | ✓ |
| SRV-02 | Regras iptables salvas em `/etc/iptables/` | ✓ |
| SRV-03 | Apache2 com 60+ vhosts funcionando como reverse proxy | ✓ |
| SRV-04 | ~25 containers Docker rodando | ✓ |
| SRV-05 | PostgreSQL 17 (8745) e MongoDB (27017) operacionais | ✓ |
| SRV-06 | PM2 gerenciando API, frontend, webhooks e bots | ✓ |

---

## Restrições

- **FreeIPA:** Não existe `freeipa-server` no Ubuntu 22.04 (bug #1875114). Solução: container Docker AlmaLinux 9
- **Apache2:** Movido para portas 9080/9443 para liberar 80/443 ao FreeIPA
- **Hostname:** FreeIPA requer FQDN — deve ser `atius-srv-1.atius.com.br`
- **DNS:** CoreDNS existente precisa coexistir com DNS do FreeIPA (BIND interno)
- **SSO existente:** Apache2 SSO em `~/GitHub/atius` NÃO pode ser afetado — coexistência obrigatória

---

## Estrutura do Repositório

```
atius-srv/
├── README.md                  # Este arquivo
├── AGENTS.md                  # GSD agents marker
├── LICENSE
├── RECOVERY_LOG.md            # Log de recuperação
├── setup.sh                   # Script de instalação em 2 etapas
├── .gitignore
├── .planning/                  # Planejamento do projeto
│   └── PROJECT.md
├── antivirus/                  # Módulo: Scripts antivirais
│   ├── monitor.sh
│   └── scan.sh
├── dark-theme-ubuntu/          # Módulo: Tema dark para LXDE
│   ├── install.sh
│   ├── repair.sh
│   ├── uninstall.sh
│   ├── themes/
│   ├── fonts/
│   └── config_files/
├── domain-infrastructure/       # Módulo: FreeIPA + Keycloak + Samba
│   ├── CLAUDE.md
│   ├── configs/
│   ├── docker/
│   └── scripts/
├── iptables/                   # Módulo: Firewall
│   ├── iptables-backup-v4.conf
│   └── iptables-backup-v6.conf
├── modules/
│   └── xrdp-abnt2/             # Guard XRDP ABNT2 integrado ao omni CLI
│       ├── README.md
│       ├── files/
│       ├── scripts/
│       └── docs/
└── vscode-profile/             # Módulo: Perfil VSCode
    ├── Giovanni (ubuntu).code-profile
    └── Extensions/
```
