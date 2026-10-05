#!/usr/bin/env bash
# omni::xrdp-audit v1.0.0
# Auditoria de XRDP, sesman, portas X11/VNC e sessões ativas na frota.
set -u

echo "=== HOST: $(hostname -f 2>/dev/null || hostname) ==="

echo "--- SERVIÇOS SYSTEMD ---"
for s in xrdp xrdp-sesman x11vnc lightdm; do
  printf "%-15s : active=%-8s enabled=%s\n" "$s" "$(systemctl is-active $s 2>/dev/null)" "$(systemctl is-enabled $s 2>/dev/null)"
done

echo "--- PORTAS ESCUTANDO (3389, 3350, 5900-5915) ---"
ss -tlpn | grep -E ':(3389|3350|590[0-9]|591[0-5])\b' || echo "Nenhuma porta encontrada"

echo "--- PROCESSOS VNC / X11 / XRDP ---"
ps -ef | grep -E 'Xvnc|x11vnc|xrdp-chansrv|xrdp-sesman' | grep -v grep || echo "Nenhum processo VNC ativo"

echo "--- DISPLAYS EM /tmp/.X11-unix ---"
ls -la /tmp/.X11-unix/ 2>/dev/null || echo "/tmp/.X11-unix vazio ou inexistente"

echo "--- SESMAN.INI (CONFIGURAÇÃO DE SESSÕES) ---"
if [ -f /etc/xrdp/sesman.ini ]; then
  grep -E '^(X11DisplayOffset|MaxSessions|KillDisconnected|DisconnectedTimeLimit|IdleTimeLimit|Policy)=' /etc/xrdp/sesman.ini 2>/dev/null
else
  echo "/etc/xrdp/sesman.ini não encontrado"
fi

echo "--- PAM XRD-SESMAN ---"
if [ -f /etc/pam.d/xrdp-sesman ]; then
  cat /etc/pam.d/xrdp-sesman
fi
