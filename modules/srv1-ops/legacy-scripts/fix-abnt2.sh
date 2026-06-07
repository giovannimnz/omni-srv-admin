#!/bin/bash
# ABNT2 CLI — Fix de teclado ABNT2 no xrdp
# Uso: fix-abnt2.sh [opcao]
#   1  = Aplicar fix agora (hotkey + setxkbmap)
#   2  = Instalar servico systemd completo
#   3  = Desinstalar servico
#   4  = Status do xbindkeys
#   5  = Testar hotkey (executa o fix sem mover teclado)
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
FIX_INTERNAL="$SCRIPT_DIR/.fix-abnt2-internal.sh"
XBINDRC="$HOME/.xbindkeysrc"
SERVICE_FILE="/etc/systemd/system/xbindkeys-abnt2.service"
DISPLAY_VAL=":10"

# Cores (funcao cross-shell)
RED='[RED]'; GREEN='[GREEN]'; YELLOW='[YELLOW]'; NC=''

log() { echo "[+] $1"; }
warn() { echo "[!] $1"; }
err() { echo "[X] $1"; }

# -------------------------------------------------------------------
# Script interno que o hotkey executa
# -------------------------------------------------------------------
create_fix_script() {
    cat > "$FIX_INTERNAL" << 'INNEREOF'
#!/bin/bash
export DISPLAY=:10
setxkbmap -option "" 2>/dev/null
setxkbmap -model pc105 -layout br -variant abnt2 -option lv3:ralt_switch 2>/dev/null
if command -v notify-send &>/dev/null; then
    LAYOUT=$(setxkbmap -query 2>/dev/null | grep layout | awk '{print $2}')
    notify-send "ABNT2" "Teclado: $LAYOUT" -i keyboard -t 2000
fi
INNEREOF
    chmod +x "$FIX_INTERNAL"
}

# -------------------------------------------------------------------
# Conteudo do servico systemd (embedado, nao e arquivo separado)
# -------------------------------------------------------------------
SERVICE_CONTENT='
[Unit]
Description=xbindkeys ABNT2 hotkey service
After=display-manager.service
PartOf=display-manager.service

[Service]
Type=simple
Environment=DISPLAY=:10
ExecStart=/usr/bin/xbindkeys
Restart=on-failure
RestartSec=3
StandardOutput=null
StandardError=null

[Install]
WantedBy=display-manager.service
'

# -------------------------------------------------------------------
# Opcao 1: Aplicar fix agora
# -------------------------------------------------------------------
apply_fix() {
    log "Instalando xbindkeys..."
    if ! command -v xbindkeys &>/dev/null; then
        sudo apt-get install -y xbindkeys || { err "Falha ao instalar xbindkeys"; exit 1; }
    fi

    create_fix_script

    cat > "$XBINDRC" << INNEREOF
"$FIX_INTERNAL"
  Control + Shift + k
INNEREOF

    pkill xbindkeys 2>/dev/null || true
    sleep 1
    export DISPLAY="$DISPLAY_VAL"
    nohup xbindkeys &>/dev/null &
    sleep 1

    if pgrep -x xbindkeys >/dev/null; then
        log "xbindkeys ativo (PID $(pgrep -x xbindkeys))"
        export DISPLAY="$DISPLAY_VAL"
        $FIX_INTERNAL
        log "Ctrl+Shift+K para corrigir ABNT2"
    else
        err "xbindkeys nao iniciou"
        exit 1
    fi
}

# -------------------------------------------------------------------
# Opcao 2: Instalar servico systemd
# -------------------------------------------------------------------
install_service() {
    create_fix_script

    cat > "$XBINDRC" << INNEREOF
"$FIX_INTERNAL"
  Control + Shift + k
INNEREOF

    echo "$SERVICE_CONTENT" | sudo tee "$SERVICE_FILE" > /dev/null

    sudo systemctl daemon-reload
    sudo systemctl enable xbindkeys-abnt2
    sudo systemctl start xbindkeys-abnt2

    if systemctl is-active --quiet xbindkeys-abnt2; then
        log "Servico instalado e rodando"
    else
        err "Servico falhou ao iniciar"
        sudo systemctl status xbindkeys-abnt2 --no-pager
        exit 1
    fi
}

# -------------------------------------------------------------------
# Opcao 3: Desinstalar
# -------------------------------------------------------------------
uninstall_service() {
    log "Removendo servico..."
    sudo systemctl stop xbindkeys-abnt2 2>/dev/null || true
    sudo systemctl disable xbindkeys-abnt2 2>/dev/null || true
    sudo rm -f "$SERVICE_FILE"
    pkill xbindkeys 2>/dev/null || true
    rm -f "$XBINDRC" "$FIX_INTERNAL"
    sudo systemctl daemon-reload
    log "Desinstalado"
}

# -------------------------------------------------------------------
# Opcao 4: Status
# -------------------------------------------------------------------
show_status() {
    echo "=== Status ==="
    if systemctl is-active --quiet xbindkeys-abnt2 2>/dev/null; then
        log "Servico: ATIVO"
    else
        warn "Servico: inativo"
    fi
    if pgrep -x xbindkeys >/dev/null; then
        log "xbindkeys: rodando (PID $(pgrep -x xbindkeys))"
    else
        warn "xbindkeys: NAO rodando"
    fi
    echo ""
    echo "Layout atual:"
    export DISPLAY="$DISPLAY_VAL"
    setxkbmap -query 2>/dev/null | grep -E "layout|variant" || warn "setxkbmap falhou"
    echo ""
    if [ -f "$XBINDRC" ]; then
        echo "Hotkey configurada:"
        grep -v "^#" "$XBINDRC" | grep -v "^$"
    fi
}

# -------------------------------------------------------------------
# Opcao 5: Testar hotkey
# -------------------------------------------------------------------
test_hotkey() {
    if [ ! -f "$FIX_INTERNAL" ]; then
        err "Script de fix nao existe. Rode opcao 1 ou 2 primeiro."
        exit 1
    fi
    export DISPLAY="$DISPLAY_VAL"
    $FIX_INTERNAL
}

# -------------------------------------------------------------------
# Menu
# -------------------------------------------------------------------
show_menu() {
    echo ""
    echo "=== ABNT2 CLI ==="
    echo "  1  Aplicar fix agora (hotkey + setxkbmap)"
    echo "  2  Instalar servico systemd completo"
    echo "  3  Desinstalar servico"
    echo "  4  Status"
    echo "  5  Testar hotkey (so executa o fix)"
    echo "  q  Sair"
    echo ""
}

# -------------------------------------------------------------------
# Main
# -------------------------------------------------------------------
if [ -n "$1" ] && [ "$1" = "q" ]; then
    exit 0
fi

if [ -n "$1" ] && [[ "$1" =~ ^[1-5]$ ]]; then
    OPT="$1"
else
    show_menu
    read -p "Escolha: " OPT
fi

case "$OPT" in
    1) apply_fix ;;
    2) install_service ;;
    3) uninstall_service ;;
    4) show_status ;;
    5) test_hotkey ;;
    q|Q) exit 0 ;;
    *) err "Opcao invalida: $OPT" ;;
esac
