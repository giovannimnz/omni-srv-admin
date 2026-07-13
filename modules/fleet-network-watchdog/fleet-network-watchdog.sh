#!/usr/bin/env bash
# fleet-network-watchdog.sh — Idempotente: restaura DNS pós-reboot em qualquer host
# da fleet ATIUS (SRV-1/2/3) que tenha Tailscale + risco de DNS hijack.
#
# Uso: sudo bash fleet-network-watchdog.sh [--no-restart] [--host-label <name>]
#
# Criado por Filippo em 2026-06-15 após incidente pós-reboot no SRV-1.
# Generalizado em 2026-06-15 para cobrir SRV-1/2/3 (ver GSD phase 15).
#
# Contexto: tailscale set --accept-dns=true sobrescreve /etc/resolv.conf
# apontando para 100.100.100.100, mas o tailnet não tem global DNS configured
# (MagicDNS sem resolvers). Resultado: SERVFAIL em todas as queries.
#
# Sistema-alvo:
#   - Hosts com systemd-resolved: rewrite resolv.conf com
#     127.0.0.53 (stub local) + DNS canônico OCI/DRG (`10.11.1.11`)
#     + Cloudflare fallback.
#     Ativa DNSStubListener=yes (Ubuntu default = no).
#   - Hosts sem systemd-resolved: só desabilita Tailscale accept-dns
#     + corrige xrdp key permission. NÃO mexe no sistema de DNS local.
#
# Estratégia:
#   1. tailscale set --accept-dns=false
#   2. tailscale set --operator=$USER (não pede mais sudo)
#   3. Se systemd-resolved presente:
#      a) Fixar DNS= com DNS canônico OCI/DRG + fallback externo
#      b) Garantir DNSStubListener=yes
#      c) Reescrever /etc/resolv.conf com stub + DNS canônico + Cloudflare
#      d) Restart systemd-resolved
#   4. Corrigir xrdp key.pem (640 root:xrdp)
#   5. Verificar DNS funcionando
#
# Idempotente: pode rodar N vezes, sempre chega no estado bom.

set -euo pipefail

RESTART=1
HOST_LABEL="${HOSTNAME:-$(hostname 2>/dev/null || echo unknown)}"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --no-restart) RESTART=0; shift ;;
    --host-label) HOST_LABEL="$2"; shift 2 ;;
    -h|--help)
      grep -E "^#( |$)" "$0" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    *) echo "Unknown arg: $1" >&2; exit 1 ;;
  esac
done

log() { echo "[$(date +%H:%M:%S)] [${HOST_LABEL}] $*"; }
fail() { echo "[$(date +%H:%M:%S)] [${HOST_LABEL}] FAIL: $*" >&2; exit 1; }

# 0. Detectar root/sudo
if [[ $EUID -eq 0 ]]; then
  SUDO=""            # já é root, sem prefix
  # runuser não requer auth (vs su que pede password) e funciona só como root
  AS_USER="runuser -u"
else
  SUDO="sudo"
  AS_USER="sudo -u"
fi
# Validar sudo NOPASSWD
if [[ -n "$SUDO" ]]; then
  $SUDO -n true 2>/dev/null || fail "precisa sudo NOPASSWD ou rodar como root"
fi

# 1. Detectar infraestrutura
HAS_TS=0
HAS_RESOLVED=0
HAS_XRDP=0
[[ -x /usr/bin/tailscale ]] || [[ -x /usr/sbin/tailscale ]] && HAS_TS=1
[[ -f /run/systemd/resolve/stub-resolv.conf ]] || \
  [[ -f /usr/lib/systemd/resolved.conf ]] || \
  [[ -f /etc/systemd/resolved.conf ]] && HAS_RESOLVED=1
[[ -f /etc/xrdp/key.pem ]] && HAS_XRDP=1

# DNS canônico do plano OCI/DRG: SRV-1 / 10.11.1.11.
CANONICAL_WIREGUARD_DNS_IP="${OMNI_CANONICAL_WIREGUARD_DNS_IP:-10.11.1.11}"
HAS_WG100=0
if ip -4 addr show 2>/dev/null | grep -q "inet 10\\.100\\.100\\."; then
  HAS_WG100=1
fi

WIREGUARD_DNS_IP="$CANONICAL_WIREGUARD_DNS_IP"
log "Detectado: tailscale=$HAS_TS systemd-resolved=$HAS_RESOLVED xrdp=$HAS_XRDP wg100=$HAS_WG100 dns-upstream=$WIREGUARD_DNS_IP"

# 2. Tailscale: desabilitar accept-dns e setar operator
if [[ $HAS_TS -eq 1 ]]; then
  # Detectar se Tailscale está rodando
  TS_RUNNING=0
  if $SUDO tailscale status 2>&1 | grep -qE "^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+"; then
    TS_RUNNING=1
  fi
  if [[ $TS_RUNNING -eq 1 ]]; then
    log "Tailscale: ativo. Desabilitando accept-dns"
    $SUDO tailscale set --accept-dns=false 2>&1 | head -2 || true

  # Operator: determinar usuário alvo
  # - Se rodando com sudo, SUDO_USER é o user original
  # - Se rodando como root sem sudo, usar o user logado (best-effort)
  OPERATOR_USER=""
  if [[ -n "$SUDO_USER" ]]; then
    OPERATOR_USER="$SUDO_USER"
  elif [[ $EUID -eq 0 ]] && [[ -n "$USER" ]] && [[ "$USER" != "root" ]]; then
    OPERATOR_USER="$USER"
  fi

  if [[ -n "$OPERATOR_USER" ]]; then
    # Verificar se já está setado
    CURRENT_OP=$($SUDO tailscale debug prefs 2>/dev/null | grep -A0 '"OperatorUser"' | head -1 | sed 's/.*"\(.*\)",/\1/' | tr -d ' "')
    if [[ "$CURRENT_OP" == "$OPERATOR_USER" ]]; then
      log "tailscale operator já é '$OPERATOR_USER' (skip)"
    else
      log "Definindo tailscale operator='$OPERATOR_USER'"
      $SUDO tailscale set --operator="$OPERATOR_USER" 2>&1 | head -1 || true
    fi
  else
    log "Não foi possível determinar o user para operator (skip)"
  fi
  else
    log "Tailscale: down (skipping set commands)"
  fi
fi

# 3. /etc/resolv.conf — só se systemd-resolved presente
if [[ $HAS_RESOLVED -eq 1 ]]; then
  # 3a. Garantir DNS= canônico do plano OCI/DRG
  RESOLVED_CHANGED=0
  DESIRED_DNS_LINE="DNS=$WIREGUARD_DNS_IP 1.1.1.1"
  CURRENT_DNS_LINE=$(grep -E "^DNS=" /etc/systemd/resolved.conf 2>/dev/null | tail -1 || true)
  if [[ "$CURRENT_DNS_LINE" != "$DESIRED_DNS_LINE" ]]; then
    log "Fixando systemd-resolved uplink DNS -> $WIREGUARD_DNS_IP + 1.1.1.1"
    $SUDO sed -i '/^DNS=/d' /etc/systemd/resolved.conf
    echo "$DESIRED_DNS_LINE" | $SUDO tee -a /etc/systemd/resolved.conf > /dev/null
    RESOLVED_CHANGED=1
  fi

  # 3b. Garantir DNSStubListener=yes
  STUB_CHANGED=0
  STUB_LINE=$(grep -E "^#?\s*DNSStubListener=" /etc/systemd/resolved.conf 2>/dev/null | head -1 || true)
  if [[ -z "$STUB_LINE" ]] || [[ "$STUB_LINE" == *"no"* ]] || [[ "$STUB_LINE" == *"#DNSStubListener="* ]]; then
    log "Habilitando DNSStubListener=yes"
    $SUDO sed -i '/^#\?\s*DNSStubListener=/d' /etc/systemd/resolved.conf
    echo "DNSStubListener=yes" | $SUDO tee -a /etc/systemd/resolved.conf > /dev/null
    STUB_CHANGED=1
  fi

  # 3c. /etc/resolv.conf → stub + DNS canônico + Cloudflare (só se mudou)
  EXPECTED_MARKER="Managed by fleet-network-watchdog.sh"
  DNS_LINE=""
  RESOLV_CHANGED=0
  if [[ -n "$WIREGUARD_DNS_IP" ]]; then
    DNS_LINE="nameserver $WIREGUARD_DNS_IP"
  fi
  if grep -qF "$EXPECTED_MARKER" /etc/resolv.conf 2>/dev/null &&
     grep -q "^nameserver 127\.0\.0\.53$" /etc/resolv.conf 2>/dev/null &&
     grep -q "^nameserver 1\.1\.1\.1$" /etc/resolv.conf 2>/dev/null &&
     { [[ -z "$DNS_LINE" ]] || grep -q "^$DNS_LINE$" /etc/resolv.conf 2>/dev/null; }; then
    log "/etc/resolv.conf já está gerenciado com DNS canônico (skip rewrite)"
  else
    RESOLV_CHANGED=1
    log "Reescrevendo /etc/resolv.conf"
    $SUDO tee /etc/resolv.conf > /dev/null <<EOF
# $EXPECTED_MARKER (Filippo 2026-06-15)
# 127.0.0.53 = systemd-resolved stub (queries forwarded to DNS interno/Cloudflare)
# ${DNS_LINE:-# sem upstream WireGuard explícito}
# 1.1.1.1 = Cloudflare direct fallback
nameserver 127.0.0.53
$DNS_LINE
nameserver 1.1.1.1
options edns0 trust-ad
EOF
  fi

  # 3d. Restart se algum ponto do resolved/resolv.conf mudou
  NEED_RESTART=0
  if [[ $RESTART -eq 1 ]] && [[ $((RESOLVED_CHANGED + STUB_CHANGED + RESOLV_CHANGED)) -gt 0 ]]; then
    NEED_RESTART=1
  fi
  if [[ $NEED_RESTART -eq 1 ]]; then
    log "Reiniciando systemd-resolved"
    $SUDO systemctl restart systemd-resolved
    sleep 2
  else
    log "systemd-resolved já em estado bom (skip restart)"
  fi

  # 3e. Verify
  log "Verificando DNS"
  if ! getent hosts google.com >/dev/null 2>&1; then
    fail "DNS ainda quebrado após correções"
  fi
  if resolvectl dns 2>/dev/null | grep -q "10\.1\.1\.2"; then
    fail "systemd-resolved ainda anuncia DNS legado 10.1.1.2"
  fi
  log "✓ DNS funcionando (google.com resolve)"

  if ! ss -tlnp 2>/dev/null | grep -qE "127\.0\.0\.53.*:53"; then
    log "AVISO: systemd-resolved não escuta em 127.0.0.53:53 — DNSStub pode estar errado"
  fi
else
  log "systemd-resolved ausente — pulando bloco DNS (sistema usa outro stack, ex: BIND/dnsmasq)"
  # Verificar que mesmo assim DNS funciona
  if ! getent hosts google.com >/dev/null 2>&1; then
    log "AVISO: getent google.com falhou. Sistema de DNS pode estar afetado por Tailscale. Verificar manualmente."
  else
    log "✓ DNS funcionando via stack local (google.com resolve)"
  fi
fi

# 4. xrdp key permission (preventivo)
# Estratégia Debian/Ubuntu: ssl-cert group owns /etc/ssl/private/ssl-cert-snakeoil.key
# e o xrdp user é adicionado a esse grupo. NÃO mudar o owner do key file (quebraria
# outros serviços como lightdm, apache2, postfix que dependem de ssl-cert group).
if [[ $HAS_XRDP -eq 1 ]]; then
  # /etc/xrdp/key.pem pode ser symlink para snakeoil default
  KEY_TARGET=$(readlink -f /etc/xrdp/key.pem 2>/dev/null || echo "/etc/xrdp/key.pem")
  KEY_GROUP=$(stat -c "%G" "$KEY_TARGET" 2>/dev/null || echo "?")

  # Estratégia: xrdp no grupo do key file (snakeoil = ssl-cert, custom = xrdp)
  if getent group "$KEY_GROUP" >/dev/null 2>&1; then
    # getent group <group> retorna a lista de users; verifica se xrdp está
    if ! getent group "$KEY_GROUP" | cut -d: -f4 | tr ',' '\n' | grep -qx xrdp; then
      log "Adicionando xrdp ao grupo '$KEY_GROUP' (necessário para ler $KEY_TARGET)"
      $SUDO usermod -a -G "$KEY_GROUP" xrdp
      # usermod -a não atualiza a sessão atual, mas o file é acessível via grupo
    else
      log "xrdp já está no grupo '$KEY_GROUP' (skip)"
    fi
  fi

  # Verificar read (xrdp user tem nologin shell, usar bash -c com -H)
  # SUDO ou AS_USER dependendo se somos root ou não
  if [[ -n "$SUDO" ]]; then
    # Não-root: usar sudo -u (suporta -H)
    XRDP_READ_TEST=1
    if ! $SUDO -u xrdp -H bash -c "test -r '$KEY_TARGET'" 2>/dev/null; then
      XRDP_READ_TEST=0
    fi
  else
    # Root: usar runuser com -c (sintaxe diferente do sudo)
    XRDP_READ_TEST=1
    if ! runuser -u xrdp -- bash -c "test -r '$KEY_TARGET'" 2>/dev/null; then
      XRDP_READ_TEST=0
    fi
  fi
  if [[ $XRDP_READ_TEST -eq 1 ]]; then
    log "xrdp user pode ler $KEY_TARGET ✓"
  else
    log "AVISO: xrdp user NÃO consegue ler $KEY_TARGET. Pode ser cert custom sem grupo apropriado."
  fi
fi

log "✓ Network fix completo"
