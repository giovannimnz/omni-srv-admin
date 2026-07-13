#!/usr/bin/env bash
# srv1-fix-network.sh — Idempotente: restaura DNS no SRV-1 após Tailscale sobrescrever resolv.conf
# Criado por Filippo em 2026-06-15 após incidente pós-reboot
#
# Uso: sudo bash srv1-fix-network.sh [--no-restart]
#
# Contexto: tailscale set --accept-dns=true sobrescreve /etc/resolv.conf apontando
# para 100.100.100.100, mas o tailnet não tem global DNS configured (MagicDNS sem
# resolvers). Resultado: SERVFAIL em todas as queries. systemd-resolved entra em modo
# "foreign" e o Link 4 (tailscale0) fica com Scopes=none → DNS completamente quebrado.
#
# Estratégia:
# 1. tailscale set --accept-dns=false (desabilita escrita no resolv.conf)
# 2. tailscale set --operator=$USER (não pede mais sudo)
# 3. Fixar DNS= em /etc/systemd/resolved.conf com 10.11.1.11 + 1.1.1.1
# 4. Reescrever /etc/resolv.conf com 127.0.0.53 (systemd-resolved stub) + 10.11.1.11 (DNS canônico OCI/DRG) + 1.1.1.1 (fallback externo)
# 5. Garantir DNSStubListener=yes em /etc/systemd/resolved.conf (Ubuntu default = no)
# 6. Restart systemd-resolved
# 7. Verificar dig/getent funcionando
#
# Idempotente: pode rodar N vezes, sempre chega no estado bom.

set -euo pipefail

RESTART=1
[[ "${1:-}" == "--no-restart" ]] && RESTART=0

log() { echo "[$(date +%H:%M:%S)] $*"; }
fail() { echo "[$(date +%H:%M:%S)] FAIL: $*" >&2; exit 1; }

# 0. Detectar root/sudo
if [[ $EUID -ne 0 ]]; then
  SUDO="sudo"
  $SUDO -n true 2>/dev/null || fail "precisa sudo NOPASSWD ou rodar como root"
else
  SUDO=""
fi

# 1. tailscale set --accept-dns=false
if command -v tailscale >/dev/null 2>&1; then
  log "Tailscale: desabilitando accept-dns"
  $SUDO tailscale set --accept-dns=false 2>&1 | head -2 || true

  # 2. operator (uma vez só)
  if ! $SUDO tailscale set --help 2>&1 | grep -q "operator"; then
    $SUDO tailscale set --operator="${SUDO_USER:-${USER}}" 2>&1 | head -1 || true
  fi
fi

# 3. Fixar DNS= canônico no systemd-resolved
CURRENT_DNS_LINE=$(grep -E "^DNS=" /etc/systemd/resolved.conf 2>/dev/null | tail -1 || true)
if [[ "$CURRENT_DNS_LINE" != "DNS=10.11.1.11 1.1.1.1" ]]; then
  log "Fixando systemd-resolved uplink DNS -> 10.11.1.11 + 1.1.1.1"
  $SUDO sed -i '/^DNS=/d' /etc/systemd/resolved.conf
  echo "DNS=10.11.1.11 1.1.1.1" | $SUDO tee -a /etc/systemd/resolved.conf > /dev/null
fi

# 4. /etc/resolv.conf → 127.0.0.53 (systemd-resolved stub) + 1.1.1.1
log "Reescrevendo /etc/resolv.conf"
$SUDO tee /etc/resolv.conf > /dev/null <<'EOF'
# Managed by srv1-fix-network.sh (Filippo 2026-06-15)
# 127.0.0.53 = systemd-resolved stub (queries forwarded to 10.11.1.11 / Cloudflare)
# 10.11.1.11 = DNS interno canônico no SRV-1 para o plano OCI/DRG
# 1.1.1.1 = Cloudflare direct fallback
nameserver 127.0.0.53
nameserver 10.11.1.11
nameserver 1.1.1.1
options edns0 trust-ad
search vcn01281103.oraclevcn.com
EOF

# 5. Garantir DNSStubListener=yes (Ubuntu default = no, queremos yes)
STUB_LINE=$(grep -E "^#?\s*DNSStubListener=" /etc/systemd/resolved.conf 2>/dev/null | head -1 || true)
if [[ -z "$STUB_LINE" ]] || [[ "$STUB_LINE" == *"no"* ]] || [[ "$STUB_LINE" == *"#DNSStubListener="* ]]; then
  log "Habilitando DNSStubListener=yes"
  # Remove qualquer linha DNSStubListener e adiciona=yes
  $SUDO sed -i '/^#\?\s*DNSStubListener=/d' /etc/systemd/resolved.conf
  echo "DNSStubListener=yes" | $SUDO tee -a /etc/systemd/resolved.conf > /dev/null
fi

# 6. Restart
if [[ $RESTART -eq 1 ]]; then
  log "Reiniciando systemd-resolved"
  $SUDO systemctl restart systemd-resolved
  sleep 2
fi

# 7. Verify
log "Verificando DNS"
if ! getent hosts google.com >/dev/null 2>&1; then
  fail "DNS ainda quebrado após correções"
fi
if resolvectl dns 2>/dev/null | grep -q "10\.1\.1\.2"; then
  fail "systemd-resolved ainda anuncia DNS legado 10.1.1.2"
fi
log "✓ DNS funcionando (google.com resolve)"

if ! ss -tlnp 2>/dev/null | grep -qE "127\.0\.0\.53.*:53"; then
  log "AVISO: systemd-resolved não escuta em 127.0.0.53:53 — verificar DNSStubListener"
fi

# 7. xrdp cert permission (preventivo)
if [[ -f /etc/xrdp/key.pem ]]; then
  if ! stat -c "%U %G %a" /etc/xrdp/key.pem | grep -q "root xrdp 6"; then
    log "Corrigindo permissão /etc/xrdp/key.pem → root:xrdp 640"
    $SUDO chown root:xrdp /etc/xrdp/key.pem
    $SUDO chmod 640 /etc/xrdp/key.pem
  fi
fi

log "✓ Network fix completo"
