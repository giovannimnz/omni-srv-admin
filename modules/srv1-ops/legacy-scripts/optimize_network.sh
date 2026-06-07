#!/usr/bin/env bash
#
# optimize_network.sh
# Script de otimização de rede para ambiente de trading de alta latência
# Otimizado para conexões OCI São Paulo → Bybit Singapura (340-480ms)
#
# Criado: 27/01/2026
# Requer: sudo/root privileges
#

set -euo pipefail

# ==========================================
# CONFIGURAÇÕES
# ==========================================

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# ==========================================
# FUNÇÕES
# ==========================================

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[✓]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[⚠]${NC} $1"
}

log_error() {
    echo -e "${RED}[✗]${NC} $1"
}

check_root() {
    if [[ $EUID -ne 0 ]]; then
        log_error "Este script precisa ser executado como root (sudo)"
        exit 1
    fi
}

backup_sysctl() {
    local backup_file="/etc/sysctl.conf.backup_$(date +%Y%m%d_%H%M%S)"
    
    if [[ -f /etc/sysctl.conf ]]; then
        log_info "Criando backup: $backup_file"
        cp /etc/sysctl.conf "$backup_file"
        log_success "Backup criado"
    fi
}

apply_setting() {
    local key="$1"
    local value="$2"
    local description="$3"
    
    log_info "$description"
    
    # Aplicar imediatamente
    if sysctl -w "${key}=${value}" > /dev/null 2>&1; then
        log_success "  ${key} = ${value}"
        
        # Adicionar ao /etc/sysctl.conf se não existir
        if ! grep -q "^${key}" /etc/sysctl.conf 2>/dev/null; then
            echo "${key} = ${value}" >> /etc/sysctl.conf
        else
            # Atualizar valor existente
            sed -i "s|^${key}.*|${key} = ${value}|" /etc/sysctl.conf
        fi
    else
        log_warning "  Falha ao aplicar: ${key}"
    fi
}

# ==========================================
# VALIDAÇÕES INICIAIS
# ==========================================

log_info "=== Otimização de Rede para Trading de Alta Latência ==="
echo

check_root

# Detectar distribuição
if [[ -f /etc/os-release ]]; then
    . /etc/os-release
    log_info "Detectado: $NAME $VERSION"
else
    log_warning "Não foi possível detectar a distribuição"
fi

# ==========================================
# BACKUP
# ==========================================

log_info "Criando backup das configurações atuais..."
backup_sysctl
echo

# ==========================================
# OTIMIZAÇÕES TCP
# ==========================================

log_info "=== Aplicando Otimizações TCP ==="
echo

# BBR Congestion Control (melhor para alta latência)
apply_setting "net.core.default_qdisc" "fq" "Habilitando FQ (Fair Queueing)"
apply_setting "net.ipv4.tcp_congestion_control" "bbr" "Habilitando BBR Congestion Control"

# Buffers TCP (para alta latência e throughput)
apply_setting "net.core.rmem_max" "134217728" "Buffer máximo de recepção: 128 MB"
apply_setting "net.core.wmem_max" "134217728" "Buffer máximo de envio: 128 MB"
apply_setting "net.ipv4.tcp_rmem" "4096 87380 67108864" "TCP read buffer (min/default/max): 64 MB"
apply_setting "net.ipv4.tcp_wmem" "4096 65536 67108864" "TCP write buffer (min/default/max): 64 MB"

# TCP keepalive agressivo (detectar conexões mortas rapidamente)
apply_setting "net.ipv4.tcp_keepalive_time" "60" "TCP keepalive: início após 60s"
apply_setting "net.ipv4.tcp_keepalive_intvl" "10" "TCP keepalive: intervalo de 10s"
apply_setting "net.ipv4.tcp_keepalive_probes" "6" "TCP keepalive: 6 tentativas"

# Fast Open (reduz latência no handshake)
apply_setting "net.ipv4.tcp_fastopen" "3" "TCP Fast Open habilitado (cliente + servidor)"

# Timeouts otimizados
apply_setting "net.ipv4.tcp_fin_timeout" "15" "FIN timeout: 15s"
apply_setting "net.ipv4.tcp_tw_reuse" "1" "Reutilizar TIME_WAIT sockets"

# SYN retries (importante para alta latência)
apply_setting "net.ipv4.tcp_syn_retries" "3" "SYN retries: 3 tentativas"
apply_setting "net.ipv4.tcp_synack_retries" "3" "SYN-ACK retries: 3 tentativas"

# Outros parâmetros TCP
apply_setting "net.ipv4.tcp_slow_start_after_idle" "0" "Desabilitar slow start após idle"
apply_setting "net.ipv4.tcp_mtu_probing" "1" "Habilitar MTU probing"
apply_setting "net.ipv4.tcp_window_scaling" "1" "Habilitar window scaling"
apply_setting "net.ipv4.tcp_timestamps" "1" "Habilitar timestamps"
apply_setting "net.ipv4.tcp_sack" "1" "Habilitar SACK"

echo

# ==========================================
# OTIMIZAÇÕES DE SOCKET
# ==========================================

log_info "=== Aplicando Otimizações de Socket ==="
echo

apply_setting "net.core.netdev_max_backlog" "5000" "Backlog máximo da interface de rede"
apply_setting "net.core.somaxconn" "1024" "Tamanho máximo da fila de conexões"
apply_setting "net.ipv4.tcp_max_syn_backlog" "8096" "Backlog máximo de SYN"

echo

# ==========================================
# OTIMIZAÇÕES DE MEMÓRIA
# ==========================================

log_info "=== Aplicando Otimizações de Memória ==="
echo

apply_setting "net.ipv4.tcp_mem" "786432 1048576 26777216" "TCP memory (páginas)"
apply_setting "net.core.optmem_max" "65536" "Memória máxima para opções de socket"

echo

# ==========================================
# OTIMIZAÇÕES DE INTERFACE (MTU para RDP/XRDP)
# ==========================================

log_info "=== Otimizando MTU da Interface ==="
echo

# Detectar interface de rede ativa (排除 loopback e tunnel)
PRIMARY_IF=$(ip -o route get 1.1.1.1 | awk '{print $5}' | head -1)
if [[ -z "$PRIMARY_IF" ]]; then
    PRIMARY_IF="enp0s3"
fi
CURRENT_MTU=$(ip link show "$PRIMARY_IF" 2>/dev/null | grep -oP 'mtu \K\d+' || echo "desconhecido")
log_info "Interface primaria: $PRIMARY_IF (MTU atual: $CURRENT_MTU)"

apply_setting "net.ipv4.$PRIMARY_IF.mtu" "1500" "MTU da interface $PRIMARY_IF: 1500 (RDP/XRDP)"
ip link set dev "$PRIMARY_IF" mtu 1500 2>/dev/null || true

echo

# ==========================================
# VERIFICAÇÃO E PERSISTÊNCIA
# ==========================================

log_info "=== Aplicando Configurações ==="
echo

if sysctl -p > /dev/null 2>&1; then
    log_success "Configurações aplicadas e persistidas em /etc/sysctl.conf"
else
    log_warning "Algumas configurações podem não ter sido aplicadas"
fi

echo

# ==========================================
# VERIFICAÇÃO BBR
# ==========================================

log_info "=== Verificando BBR ==="
echo

current_cc=$(sysctl net.ipv4.tcp_congestion_control 2>/dev/null | awk '{print $3}')
current_qdisc=$(sysctl net.core.default_qdisc 2>/dev/null | awk '{print $3}')

if [[ "$current_cc" == "bbr" ]]; then
    log_success "BBR Congestion Control ativo"
else
    log_warning "BBR não está ativo. Valor atual: $current_cc"
    log_info "Verifique se o módulo tcp_bbr está disponível: lsmod | grep tcp_bbr"
fi

if [[ "$current_qdisc" == "fq" ]]; then
    log_success "FQ Queueing Discipline ativo"
else
    log_warning "FQ não está ativo. Valor atual: $current_qdisc"
fi

echo

# ==========================================
# ESTATÍSTICAS
# ==========================================

log_info "=== Estatísticas de Rede ==="
echo

log_info "Buffers TCP:"
sysctl net.ipv4.tcp_rmem 2>/dev/null || true
sysctl net.ipv4.tcp_wmem 2>/dev/null || true

echo

log_info "TCP Keepalive:"
sysctl net.ipv4.tcp_keepalive_time 2>/dev/null || true
sysctl net.ipv4.tcp_keepalive_intvl 2>/dev/null || true
sysctl net.ipv4.tcp_keepalive_probes 2>/dev/null || true

echo

# ==========================================
# RECOMENDAÇÕES FINAIS
# ==========================================

log_success "=== Otimização Concluída ==="
echo

log_info "Recomendações adicionais:"
echo "  1. Reinicie as aplicações que usam conexões de rede"
echo "  2. Monitore a latência: ping -c 10 api.bybit.com"
echo "  3. Verifique BBR em ação: ss -ti | grep bbr"
echo "  4. Para reverter: sudo cp /etc/sysctl.conf.backup_* /etc/sysctl.conf && sudo sysctl -p"
echo

log_info "As configurações serão preservadas após reinicialização do sistema"

exit 0
