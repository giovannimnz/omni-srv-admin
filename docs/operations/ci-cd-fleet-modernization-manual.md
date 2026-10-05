# Manual Operacional: Modernização de CI/CD da Frota Atius (GitHub Actions & GitLab K3s)

- **Data da Operação**: 2026-09-27
- **Ambientes Governados**: Produção (PRD) e Desenvolvimento (DEV)
- **Nó de Execução CI/CD**: `atius-srv-4` (K3s Node / Role: `ci`)
- **Gateway & Proxy Reverso**: `atius-srv-1` (Apache + Cloudflare)
- **Cofre Central de Segredos**: `atius-srv-3` (HashiCorp Vault em `https://10.13.1.13:8202`)

---

## 1. Visão Geral da Arquitetura

A infraestrutura de automação e entrega contínua da frota Atius foi totalmente modernizada com as seguintes diretrizes:

1. **Erradicação Completa do Jenkins**: Remoção definitiva de containers, imagens, units systemd, vhosts, DNS e manifests do cluster K3s, eliminando o legado e liberando recursos de CPU e storage.
2. **Implementação Híbrida Self-Hosted (GitHub Actions + GitLab CE)**:
   - **GitHub Actions**: Runner auto-hospedado (`actions-runner 2.322.0`) em `/opt/actions-runner` no `atius-srv-4`.
   - **GitLab CE**: Instância nativa `gitlab-ce 19.4.1` (ARM64) no nó `atius-srv-4`, otimizada para o guardrail de CPU (<20% com Puma 2 workers / 4 threads e PostgreSQL buffers 256MB).
3. **Isolamento de Ambientes DEV e PRD**:
   - Domínios, namespaces no K3s, quotas de recursos e pods de runners segregados.
4. **Governança de Segredos**: Injeção estrita a partir do HashiCorp Vault via script stdin-safe (`atius-vault-env`), sem credenciais hardcoded.
5. **Autenticação Unificada (SSO)**: Keycloak OIDC corporativo em `https://auth.atius.com.br/realms/atius` cobrindo todos os domínios.

---

## 2. Topologia de Domínios e Namespaces K3s

### 2.1 Ambiente de Produção (PRD)
| Serviço | Domínio (.com.br) | Domínio (.io) | Destino Interno | Namespace K3s |
| :--- | :--- | :--- | :--- | :--- |
| **GitLab PRD** | `https://gitlab.atius.com.br` | `https://gitlab.atius.io` | `http://10.14.1.14:8929` | `pipeline-prd` |
| **Pipeline PRD** | `https://pipeline.atius.com.br` | `https://pipeline.atius.io` | `http://10.14.1.14:8929` | `pipeline-prd` |

- **Deployment K3s**: `atius-pipeline-runner-prd` (imagem: `ubuntu:24.04`)
- **ResourceQuota**: `1000m CPU` (máximo 2 pods de 500m), `2Gi RAM`, `4 pods` máximo.

### 2.2 Ambiente de Desenvolvimento (DEV)
| Serviço | Domínio (.com.br) | Domínio (.io) | Destino Interno | Namespace K3s |
| :--- | :--- | :--- | :--- | :--- |
| **GitLab DEV** | `https://gitlabdev.atius.com.br` | `https://gitlabdev.atius.io` | `http://10.14.1.14:8929` | `pipeline-dev` |
| **Pipeline DEV** | `https://pipelinedev.atius.com.br` | `https://pipelinedev.atius.io` | `http://10.14.1.14:8929` | `pipeline-dev` |

- **Deployment K3s**: `atius-pipeline-runner-dev` (imagem: `ubuntu:24.04`)
- **ResourceQuota**: `1000m CPU` (máximo 2 pods de 500m), `2Gi RAM`, `4 pods` máximo.

---

## 3. Integração com HashiCorp Vault

Os segredos da pipeline residem exclusivamente no HashiCorp Vault (`https://10.13.1.13:8202` em `atius-srv-3`).

### 3.1 Paths Cadastrados
- `kv/atius/pipeline/service-account`:
  - `SERVICE_USER`: `svc-agent-pipeline`
  - `SERVICE_TOKEN`: token com permissões `deploy,test-e2e,performance-gatling,vault-read`
  - `ROLE`: `pipeline-runner`
- `kv/atius/gitlab/admin`:
  - `USERNAME`: `root`
  - `PASSWORD`: senha inicial de administração do GitLab
- `kv/atius/gitlab/oidc`:
  - `GITLAB_CLIENT_ID`: `gitlab`
  - `GITLAB_CLIENT_SECRET`: segredo OIDC cadastrado no Keycloak
  - `GITLAB_ISSUER`: `https://auth.atius.com.br/realms/atius`
- `kv/atius/gitlab/runner-token`:
  - `TOKEN`: token de registro para novos runners

### 3.2 Carregamento em Runtime
Nas pipelines e scripts, o carregamento ocorre via:
```bash
./scripts/ci/vault-load-secrets.sh pipeline
```
O helper extrai as variáveis sem gravá-las em disco, exportando-as diretamente para o ambiente da execução.

---

## 4. Integração SSO / Keycloak OIDC

O client OIDC `gitlab` foi criado no realm `atius` com suporte a fluxos Standard Authorization Code (PKCE):
- **Redirect URIs Autorizadas**:
  - `https://gitlab.atius.com.br/*` e `https://gitlab.atius.io/*`
  - `https://gitlabdev.atius.com.br/*` e `https://gitlabdev.atius.io/*`
  - `https://pipeline.atius.com.br/*` e `https://pipeline.atius.io/*`
  - `https://pipelinedev.atius.com.br/*` e `https://pipelinedev.atius.io/*`
- **OmniAuth Provider**: Configurado em `/etc/gitlab/gitlab.rb` no `atius-srv-4`. O botão "Sign in with Atius SSO" é exibido nas telas de login de todos os domínios.

---

## 5. Pipelines CI/CD

As pipelines foram estruturadas tanto no GitLab CI (`.gitlab-ci.yml`) quanto no GitHub Actions (`.github/workflows/`):

1. **`vault-secrets-audit`**: Validação de conectividade e integridade do cofre HashiCorp Vault.
2. **`lint-and-validate`**: Checagem de sintaxe e conformidade de quotas do Kubernetes.
3. **`test-playwright`**: Testes E2E headless que navegam em todos os domínios DEV e PRD, validando renderização do botão Atius SSO e gerando screenshots em `/home/ubuntu/Prints/`.
4. **`test-gatling-performance`**: Benchmark de latência e concorrência com Java 21 OpenJDK.
5. **`deploy-dev` / `deploy-prd`**: Execução de deploy governado via `scripts/ci/deploy-governed.sh`, aplicando CPU Guardrail (<20%), reconciliação de pods e healthchecks.
6. **`k3s-container-agent`**: Orquestração e reconciliação dos pods nos namespaces `pipeline-dev` e `pipeline-prd`.

---

## 6. Manual do CLI Unificado (`start.sh`)

O arquivo `/home/ubuntu/GitHub/omni-srv-admin/start.sh` foi projetado para uso duplo: **automações de agentes** e **analistas humanos**.

### 6.1 Modo Não-Interativo (Agentes e Automações)
Ideal para scripts, jobs cron e chamadas diretas de agentes IA:

```bash
# 1. Health check rápido de todos os endpoints DEV e PRD
./start.sh status

# 2. Status estruturado em JSON para parsers de automação
./start.sh status --json

# 3. Disparar deploy em DEV
./start.sh deploy dev

# 4. Disparar deploy em PRD
./start.sh deploy prd

# 5. Executar suite Playwright E2E
./start.sh test

# 6. Executar benchmark de performance Gatling
./start.sh perf

# 7. Auditar e testar segredos do Vault
./start.sh vault

# 8. Inspecionar status de nós e pods K3s
./start.sh k3s status

# 9. Forçar reconciliação de pods K3s nos dois ambientes
./start.sh k3s rollout
```

### 6.2 Modo Interativo (Analista Humano)
Basta executar sem parâmetros a partir de um terminal:
```bash
./start.sh
```
O sistema apresentará um menu interativo colorido com as opções numeradas:
- `1) Verificar Status da Frota (Health check DEV & PRD)`
- `2) Executar Deploy Governado em [DEV]`
- `3) Executar Deploy Governado em [PRD]`
- `4) Rodar Testes Automatizados E2E (Playwright)`
- `5) Rodar Testes de Performance (Gatling)`
- `6) Inspecionar Cluster K3s (Nós, Pods, Quotas)`
- `7) Auditar Segredos no HashiCorp Vault`
- `8) Iniciar / Anexar Sessão Mosh + Tmux (Rolagem de Mouse)`
- `0) Sair`

---

## 7. Guia: Rolagem de Mouse no Mosh / Tmux

### 7.1 Causa Técnica do Problema
O Mosh utiliza o protocolo SSP (*State Synchronization Protocol*) sobre UDP e gerencia exclusivamente a matriz da tela visível no terminal cliente. Ele coloca o terminal no modo de tela alternativa (*alternate screen buffer*). Por design, o Mosh **não possui buffer de scrollback próprio**. 

### 7.2 Solução Implementada no Servidor
Configuramos o `~/.tmux.conf` para capturar a roda do mouse e entrar automaticamente no modo de rolagem (`copy-mode`):
```tmux
set -g mouse on
bind -n WheelUpPane if-shell -F -t = "#{mouse_any_flag}" "send-keys -M" "if -Ft= '#{pane_in_mode}' 'send-keys -M' 'copy-mode -e; send-keys -M'"
bind -n WheelDownPane select-pane -t= \; send-keys -M
bind -T copy-mode-vi WheelUpPane send-keys -X -N 3 scroll-up
bind -T copy-mode-vi WheelDownPane send-keys -X -N 3 scroll-down
```

### 7.3 Como Usar no Dia a Dia

1. **Método Recomendado (Mosh + Tmux)**:
   Ao conectar via Mosh a partir do cliente (Windows Terminal, Termux, etc.), execute:
   ```bash
   mosh muniz@10.11.1.11 -- tmux new -A -s 0
   ```
   Ou após conectar no shell, use o helper do `start.sh`:
   ```bash
   ./start.sh mosh attach
   ```
   Ao rolar a roda do mouse para cima, a tela rola suavemente através do histórico. Ao rolar de volta para o final, o modo cópia fecha automaticamente.

2. **Atalho do Emulador de Terminal (Client-Side)**:
   No Windows Terminal, PuTTY ou xterm, segurar a tecla **`Shift`** enquanto rola o mouse força o emulador a rolar o buffer local da janela, ignorando a captura da aplicação.
