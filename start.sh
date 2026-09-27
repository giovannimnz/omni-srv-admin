#!/usr/bin/env bash
# ==============================================================================
# start.sh — Atius CI/CD & Fleet Operations Unified Dual-Use CLI
# Modos de Uso:
#   1. Agentes / CI (Não Interativo): ./start.sh <comando> [argumentos...] [--json]
#   2. Analista Humano (Interativo / Menu): ./start.sh
# ==============================================================================
set -eo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export KUBECONFIG="${KUBECONFIG:-$HOME/.kube/config}"

# Cores e Formatação
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# ------------------------------------------------------------------------------
# Funções Utilitárias
# ------------------------------------------------------------------------------
log_info() { echo -e "${CYAN}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[OK]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1" >&2; }

probe_endpoint() {
  local url="$1"
  local code
  code=$(curl -s -k -o /dev/null -w "%{http_code}" -m 5 "$url" 2>/dev/null || echo "000")
  echo "$code"
}

# ------------------------------------------------------------------------------
# 1. Status Geral da Frota (DEV e PRD)
# ------------------------------------------------------------------------------
cmd_status() {
  local as_json=false
  for arg in "$@"; do [[ "$arg" == "--json" ]] && as_json=true; done

  local prd_br prd_io prd_pipe_br prd_pipe_io
  local dev_br dev_io dev_pipe_br dev_pipe_io
  local sso_code oidc_code
  local k3s_dev_pods k3s_prd_pods

  prd_br=$(probe_endpoint "https://gitlab.atius.com.br/users/sign_in")
  prd_io=$(probe_endpoint "https://gitlab.atius.io/users/sign_in")
  prd_pipe_br=$(probe_endpoint "https://pipeline.atius.com.br/users/sign_in")
  prd_pipe_io=$(probe_endpoint "https://pipeline.atius.io/users/sign_in")

  dev_br=$(probe_endpoint "https://gitlabdev.atius.com.br/users/sign_in")
  dev_io=$(probe_endpoint "https://gitlabdev.atius.io/users/sign_in")
  dev_pipe_br=$(probe_endpoint "https://pipelinedev.atius.com.br/users/sign_in")
  dev_pipe_io=$(probe_endpoint "https://pipelinedev.atius.io/users/sign_in")

  sso_code=$(probe_endpoint "https://sso.atius.com.br/login")
  oidc_code=$(probe_endpoint "https://auth.atius.com.br/realms/atius/.well-known/openid-configuration")

  k3s_dev_pods=$(kubectl -n pipeline-dev get pods --no-headers 2>/dev/null | awk '{print $1":"$3}' | paste -sd "," - || echo "none")
  k3s_prd_pods=$(kubectl -n pipeline-prd get pods --no-headers 2>/dev/null | awk '{print $1":"$3}' | paste -sd "," - || echo "none")

  if [ "$as_json" = true ]; then
    cat <<JSON
{
  "timestamp": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")",
  "environments": {
    "prd": {
      "gitlab_com_br": "$prd_br",
      "gitlab_io": "$prd_io",
      "pipeline_com_br": "$prd_pipe_br",
      "pipeline_io": "$prd_pipe_io",
      "k3s_pods": "$k3s_prd_pods"
    },
    "dev": {
      "gitlabdev_com_br": "$dev_br",
      "gitlabdev_io": "$dev_io",
      "pipelinedev_com_br": "$dev_pipe_br",
      "pipelinedev_io": "$dev_pipe_io",
      "k3s_pods": "$k3s_dev_pods"
    }
  },
  "auth": {
    "sso_portal": "$sso_code",
    "keycloak_oidc": "$oidc_code"
  }
}
JSON
    return 0
  fi

  echo -e "\n${BOLD}=================================================================${NC}"
  echo -e "${BOLD}       ATIUS FLEET CI/CD STATUS MONITOR (DEV & PRD)              ${NC}"
  echo -e "${BOLD}=================================================================${NC}"
  
  format_status() {
    local code="$1"
    if [[ "$code" == "200" || "$code" == "302" ]]; then
      echo -e "${GREEN}${code} OK${NC}"
    else
      echo -e "${RED}${code} FAIL${NC}"
    fi
  }

  echo -e "\n${CYAN}--- [Ambiente PRD / Produção] ---${NC}"
  printf "  %-35s : %b\n" "https://gitlab.atius.com.br" "$(format_status "$prd_br")"
  printf "  %-35s : %b\n" "https://gitlab.atius.io" "$(format_status "$prd_io")"
  printf "  %-35s : %b\n" "https://pipeline.atius.com.br" "$(format_status "$prd_pipe_br")"
  printf "  %-35s : %b\n" "https://pipeline.atius.io" "$(format_status "$prd_pipe_io")"
  printf "  %-35s : %s\n" "K3s Pods (pipeline-prd)" "${k3s_prd_pods}"

  echo -e "\n${CYAN}--- [Ambiente DEV / Desenvolvimento] ---${NC}"
  printf "  %-35s : %b\n" "https://gitlabdev.atius.com.br" "$(format_status "$dev_br")"
  printf "  %-35s : %b\n" "https://gitlabdev.atius.io" "$(format_status "$dev_io")"
  printf "  %-35s : %b\n" "https://pipelinedev.atius.com.br" "$(format_status "$dev_pipe_br")"
  printf "  %-35s : %b\n" "https://pipelinedev.atius.io" "$(format_status "$dev_pipe_io")"
  printf "  %-35s : %s\n" "K3s Pods (pipeline-dev)" "${k3s_dev_pods}"

  echo -e "\n${CYAN}--- [Serviços Centrais de Autenticação] ---${NC}"
  printf "  %-35s : %b\n" "Atius SSO Portal" "$(format_status "$sso_code")"
  printf "  %-35s : %b\n" "Keycloak OIDC Realm" "$(format_status "$oidc_code")"
  echo -e "${BOLD}=================================================================${NC}\n"
}

# ------------------------------------------------------------------------------
# 2. Deploy Governado (DEV / PRD)
# ------------------------------------------------------------------------------
cmd_deploy() {
  local env="${1:-dev}"
  log_info "Disparando deploy governado para ambiente: [${env^^}]"
  bash "$SCRIPT_DIR/scripts/ci/deploy-governed.sh" "$env"
}

# ------------------------------------------------------------------------------
# 3. Testes Automatizados Playwright E2E
# ------------------------------------------------------------------------------
cmd_test() {
  log_info "Executando suite completa de testes Playwright E2E..."
  bash "$SCRIPT_DIR/scripts/ci/run-playwright-tests.sh"
}

# ------------------------------------------------------------------------------
# 4. Testes de Performance Gatling
# ------------------------------------------------------------------------------
cmd_perf() {
  log_info "Executando benchmark de performance Gatling + Java 21..."
  bash "$SCRIPT_DIR/scripts/ci/run-gatling-performance.sh"
}

# ------------------------------------------------------------------------------
# 5. Auditoria de Segredos HashiCorp Vault
# ------------------------------------------------------------------------------
cmd_vault() {
  log_info "Validando integração e perfis do HashiCorp Vault..."
  bash "$SCRIPT_DIR/scripts/ci/vault-load-secrets.sh" pipeline
  log_success "HashiCorp Vault verificado com sucesso."
}

# ------------------------------------------------------------------------------
# 6. K3s Container Agent & Reconciliação
# ------------------------------------------------------------------------------
cmd_k3s() {
  local action="${1:-status}"
  case "$action" in
    status)
      log_info "Status dos Nós do Cluster K3s:"
      kubectl get nodes -o wide
      echo ""
      log_info "Workloads no namespace pipeline-dev:"
      kubectl -n pipeline-dev get pods,deployment,resourcequota
      echo ""
      log_info "Workloads no namespace pipeline-prd:"
      kubectl -n pipeline-prd get pods,deployment,resourcequota
      ;;
    rollout)
      log_info "Reconciliando rollouts em DEV e PRD..."
      kubectl -n pipeline-dev rollout restart deployment/atius-pipeline-runner-dev
      kubectl -n pipeline-prd rollout restart deployment/atius-pipeline-runner-prd
      kubectl -n pipeline-dev rollout status deployment/atius-pipeline-runner-dev --timeout=60s
      kubectl -n pipeline-prd rollout status deployment/atius-pipeline-runner-prd --timeout=60s
      log_success "Rollouts concluídos."
      ;;
    *)
      log_error "Ação K3s inválida: $action. Use 'status' ou 'rollout'."
      return 1
      ;;
  esac
}

# ------------------------------------------------------------------------------
# 7. Mosh & Tmux Helper (Mouse Scroll)
# ------------------------------------------------------------------------------
cmd_mosh() {
  local sub="${1:-attach}"
  case "$sub" in
    attach)
      log_info "Conectando / anexando à sessão tmux principal com suporte a rolagem de mouse..."
      exec tmux new-session -A -s atius-ci
      ;;
    fix)
      log_info "Garantindo configurações de rolagem de mouse no ~/.tmux.conf..."
      grep -q "WheelUpPane" ~/.tmux.conf 2>/dev/null || cat << 'EOF' >> ~/.tmux.conf

# >>> MOSH_MOUSE_SCROLL >>>
bind -n WheelUpPane if-shell -F -t = "#{mouse_any_flag}" "send-keys -M" "if -Ft= '#{pane_in_mode}' 'send-keys -M' 'copy-mode -e; send-keys -M'"
bind -n WheelDownPane select-pane -t= \; send-keys -M
bind -T copy-mode-vi WheelUpPane send-keys -X -N 3 scroll-up
bind -T copy-mode-vi WheelDownPane send-keys -X -N 3 scroll-down
bind -T copy-mode WheelUpPane send-keys -X -N 3 scroll-up
bind -T copy-mode WheelDownPane send-keys -X -N 3 scroll-down
# <<< MOSH_MOUSE_SCROLL <<<
EOF
      tmux source-file ~/.tmux.conf 2>/dev/null || true
      log_success "Configurações de mouse no tmux aplicadas com sucesso."
      ;;
    *)
      log_error "Uso: ./start.sh mosh [attach|fix]"
      return 1
      ;;
  esac
}

# ------------------------------------------------------------------------------
# 8. Menu Interativo (TUI para Analista)
# ------------------------------------------------------------------------------
cmd_interactive_menu() {
  while true; do
    echo -e "${BOLD}${BLUE}╔════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BOLD}${BLUE}║       ATIUS FLEET CI/CD & OPERATIONS INTERACTIVE CLI           ║${NC}"
    echo -e "${BOLD}${BLUE}╚════════════════════════════════════════════════════════════════╝${NC}"
    echo -e "  ${BOLD}1)${NC} Verificar Status da Frota (Health check DEV & PRD)"
    echo -e "  ${BOLD}2)${NC} Executar Deploy Governado em [DEV] (gitlabdev / pipelinedev)"
    echo -e "  ${BOLD}3)${NC} Executar Deploy Governado em [PRD] (gitlab / pipeline)"
    echo -e "  ${BOLD}4)${NC} Rodar Testes Automatizados E2E (Playwright Headless)"
    echo -e "  ${BOLD}5)${NC} Rodar Testes de Performance (Gatling + Java 21)"
    echo -e "  ${BOLD}6)${NC} Inspecionar Cluster K3s (Nós, Pods, Quotas DEV/PRD)"
    echo -e "  ${BOLD}7)${NC} Auditar Segredos no HashiCorp Vault"
    echo -e "  ${BOLD}8)${NC} Iniciar / Anexar Sessão Mosh + Tmux (Rolagem de Mouse OK)"
    echo -e "  ${BOLD}0)${NC} Sair"
    echo ""
    read -r -p "Escolha uma opção [0-8]: " choice

    case "$choice" in
      1) cmd_status ;;
      2) cmd_deploy dev ;;
      3) cmd_deploy prd ;;
      4) cmd_test ;;
      5) cmd_perf ;;
      6) cmd_k3s status ;;
      7) cmd_vault ;;
      8) cmd_mosh attach ;;
      0) echo "Saindo..."; exit 0 ;;
      *) log_warn "Opção inválida: $choice" ;;
    esac

    echo ""
    read -r -p "Pressione [Enter] para continuar..."
    clear || true
  done
}

# ------------------------------------------------------------------------------
# Ponto de Entrada (Entrypoint Dispatcher)
# ------------------------------------------------------------------------------
if [ "$#" -eq 0 ]; then
  # Se executado sem argumentos e em terminal interativo, abre o menu
  if [ -t 0 ]; then
    cmd_interactive_menu
  else
    cmd_status
  fi
  exit 0
fi

COMMAND="$1"
shift

case "$COMMAND" in
  status) cmd_status "$@" ;;
  deploy) cmd_deploy "$@" ;;
  test)   cmd_test "$@" ;;
  perf)   cmd_perf "$@" ;;
  vault)  cmd_vault "$@" ;;
  k3s)    cmd_k3s "$@" ;;
  mosh)   cmd_mosh "$@" ;;
  help|--help|-h)
    cat <<HELP
Uso do start.sh:
  ./start.sh                           # Menu interativo (para analistas)
  ./start.sh status [--json]           # Status completo DEV e PRD
  ./start.sh deploy [dev|prd]          # Executa deploy governado com CPU Guardrail
  ./start.sh test                      # Executa testes Playwright E2E
  ./start.sh perf                      # Executa testes de performance Gatling
  ./start.sh vault                     # Audita e exporta credenciais do Vault
  ./start.sh k3s [status|rollout]      # Gerencia containers e pods K3s
  ./start.sh mosh [attach|fix]         # Anexa sessão tmux com suporte a rolagem de mouse
HELP
    ;;
  *)
    log_error "Comando desconhecido: $COMMAND. Execute './start.sh help' para ajuda."
    exit 1
    ;;
esac
