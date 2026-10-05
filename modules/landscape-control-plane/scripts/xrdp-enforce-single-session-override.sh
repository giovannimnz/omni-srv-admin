#!/usr/bin/env bash
# omni::xrdp-enforce-single-session-override v1.0.0
# Enforces single-session override and auto-kill on disconnect for XRDP across the fleet.
# Ensures:
# 1. New XRDP connections always override/take over cleanly without display exhaustion or "login failed".
# 2. Disconnected sessions are terminated immediately (KillDisconnected=true, DisconnectedTimeLimit=0).
# 3. Maximum 1 concurrent session per server (MaxSessions=1).
# 4. Port 5901 collisions (e.g. from x11vnc) are moved to 5900.
# 5. Stale sockets and orphan Xvnc sessions are cleaned before sesman starts.
set -euo pipefail

HOST=$(hostname -f 2>/dev/null || hostname)
echo "============================================================"
echo "=== EXECUTANDO EM: $HOST ==="
echo "============================================================"

# 1. Corrigir colisão de portas x11vnc (5901 -> 5900) se existir
CHANGED_VNC=0
if [ -f /etc/systemd/system/x11vnc.service ]; then
    if grep -q "5901" /etc/systemd/system/x11vnc.service; then
        echo "[x11vnc] Atualizando porta em /etc/systemd/system/x11vnc.service (5901 -> 5900)..."
        sed -i 's/-rfbport 5901/-rfbport 5900/g' /etc/systemd/system/x11vnc.service
        CHANGED_VNC=1
    fi
fi

if [ -f /etc/systemd/system/websockify.service ]; then
    if grep -q "5901" /etc/systemd/system/websockify.service; then
        echo "[websockify] Atualizando target em /etc/systemd/system/websockify.service (5901 -> 5900)..."
        sed -i 's/localhost:5901/localhost:5900/g' /etc/systemd/system/websockify.service
        CHANGED_VNC=1
    fi
fi

if [ "$CHANGED_VNC" -eq 1 ]; then
    systemctl daemon-reload
    if systemctl is-active --quiet x11vnc; then
        systemctl restart x11vnc
    fi
    if systemctl is-active --quiet websockify; then
        systemctl restart websockify
    fi
fi

# 2. Configurar /etc/xrdp/sesman.ini
if [ -f /etc/xrdp/sesman.ini ]; then
    echo "[sesman.ini] Aplicando diretivas de sessão única e encerramento em disconnect..."
    sed -i 's/^X11DisplayOffset=.*/X11DisplayOffset=1/' /etc/xrdp/sesman.ini
    sed -i 's/^MaxSessions=.*/MaxSessions=1/' /etc/xrdp/sesman.ini
    sed -i 's/^KillDisconnected=.*/KillDisconnected=true/' /etc/xrdp/sesman.ini
    sed -i 's/^DisconnectedTimeLimit=.*/DisconnectedTimeLimit=0/' /etc/xrdp/sesman.ini
    sed -i 's/^IdleTimeLimit=.*/IdleTimeLimit=0/' /etc/xrdp/sesman.ini
    sed -i 's/^Policy=.*/Policy=Default/' /etc/xrdp/sesman.ini
else
    echo "[AVISO] /etc/xrdp/sesman.ini não encontrado neste host!"
fi

# 3. Limpar processos órfãos antigos de XRDP Xvnc / chansrv
echo "[cleanup] Encerrando instâncias órfãs de Xvnc associadas ao XRDP..."
XVNC_PIDS=$(pgrep -f 'Xvnc :[0-9]+.*rfbunixpath' || true)
if [ -n "$XVNC_PIDS" ]; then
    echo "  -> Finalizando PIDs Xvnc: $XVNC_PIDS"
    kill -TERM $XVNC_PIDS 2>/dev/null || true
    sleep 0.5
    for p in $XVNC_PIDS; do
        if kill -0 "$p" 2>/dev/null; then
            kill -KILL "$p" 2>/dev/null || true
        fi
    done
fi

CHANSRV_PIDS=$(pgrep -x 'xrdp-chansrv' || true)
if [ -n "$CHANSRV_PIDS" ]; then
    echo "  -> Finalizando PIDs chansrv: $CHANSRV_PIDS"
    kill -TERM $CHANSRV_PIDS 2>/dev/null || true
fi

# Limpar sockets órfãos
rm -f /tmp/.X11-unix/X[1-9]* /tmp/.X[1-9]*-lock 2>/dev/null || true
if [ -d /run/xrdp/sockdir ]; then
    rm -f /run/xrdp/sockdir/* 2>/dev/null || true
fi

# 4. Instalar script guardião /usr/local/sbin/xrdp-clean-stale-sockets.sh
cat << 'CLEAN_EOF' > /usr/local/sbin/xrdp-clean-stale-sockets.sh
#!/usr/bin/env bash
# /usr/local/sbin/xrdp-clean-stale-sockets.sh
# Purges stale X11/XRDP display sockets and locks before sesman starts.
set -u

if [ -d /run/xrdp/sockdir ]; then
    for s in /run/xrdp/sockdir/*; do
        [ -e "$s" ] || continue
        if ! fuser "$s" >/dev/null 2>&1; then
            rm -f "$s"
        fi
    done
fi

for d in /tmp/.X11-unix/X[1-9]*; do
    [ -e "$d" ] || continue
    dnum="${d##*/X}"
    if ! pgrep -f "Xvnc :${dnum}\b" >/dev/null 2>&1; then
        rm -f "$d" "/tmp/.X${dnum}-lock"
    fi
done

exit 0
CLEAN_EOF
chmod 755 /usr/local/sbin/xrdp-clean-stale-sockets.sh

# 5. Instalar systemd drop-in para xrdp-sesman.service
mkdir -p /etc/systemd/system/xrdp-sesman.service.d
cat << 'UNIT_EOF' > /etc/systemd/system/xrdp-sesman.service.d/override.conf
[Service]
ExecStartPre=/usr/local/sbin/xrdp-clean-stale-sockets.sh
UNIT_EOF

systemctl daemon-reload

# 6. Reiniciar serviços XRDP
echo "[systemd] Reiniciando xrdp-sesman e xrdp..."
systemctl restart xrdp-sesman xrdp

# 7. Validação e Relatório
echo "--- STATUS APÓS APLICAÇÃO ---"
echo "Serviços:"
for s in xrdp xrdp-sesman x11vnc; do
    printf "  %-15s : active=%-8s enabled=%s\n" "$s" "$(systemctl is-active $s 2>/dev/null || echo inactive)" "$(systemctl is-enabled $s 2>/dev/null || echo unknown)"
done

echo "Portas escutando:"
ss -tlpn | grep -E ':(3389|3350|590[0-9])\b' || echo "  Nenhuma porta encontrada"

echo "Configuração sesman.ini:"
grep -E '^(X11DisplayOffset|MaxSessions|KillDisconnected|DisconnectedTimeLimit|Policy)=' /etc/xrdp/sesman.ini 2>/dev/null || true

echo "SUCESSO: Host $HOST configurado com política de sessão única e auto-override."
