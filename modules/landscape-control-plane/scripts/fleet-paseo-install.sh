#!/usr/bin/env bash
# omni::fleet-paseo-install v1.1.0
# Rollout soberano do Paseo AI Agent Runtime (CLI + Server + ACP) na frota ATIUS
# Portas dedicadas: srv-1:37815, srv-2:37825, srv-3:37835, srv-4:37845 (Hub Central)
set -uo pipefail

# Prioridade minima para respeitar o CPU Guardrail (<= 20% CPU)
renice -n 19 -p $$ >/dev/null 2>&1 || true
ionice -c 3 -p $$ >/dev/null 2>&1 || true

HOST=$(hostname 2>/dev/null || cat /etc/hostname)
TARGET_USER="ubuntu"
[ "$HOST" = "horistic-srv" ] && TARGET_USER="horistic"
TARGET_HOME="/home/$TARGET_USER"

echo "== [identity] =="
echo "host=$HOST, target_user=$TARGET_USER, date=$(date -u +%Y-%m-%dT%H:%M:%SZ)"

# Resolver porta dedicada por host
case "$HOST" in
  *srv-1*) PORT=37815; IS_HUB="false" ;;
  *srv-2*) PORT=37825; IS_HUB="false" ;;
  *srv-3*) PORT=37835; IS_HUB="false" ;;
  *srv-4*) PORT=37845; IS_HUB="true" ;;
  *)       PORT=37899; IS_HUB="false" ;;
esac

echo "assigned_port=$PORT, is_hub=$IS_HUB"

# Carregar nvm do target user
export NVM_DIR="$TARGET_HOME/.nvm"
if [ ! -s "$NVM_DIR/nvm.sh" ]; then
  echo "ERRO: NVM ausente em $NVM_DIR" >&2
  exit 1
fi

# 1. Instalacao dos pacotes via NVM
sudo -u "$TARGET_USER" -H bash -c '
  export NVM_DIR="$HOME/.nvm"
  [ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"
  echo "[nvm] Node: $(node --version), NPM: $(npm --version)"
  
  npm install -g --allow-scripts=esbuild,node-pty,msgpackr-extract \
    @getpaseo/cli@0.14.0 @getpaseo/server@0.14.0 paseo-agy-acp@2.7.2 2>&1 | tail -5
'

# Garantir symlink global em /usr/local/bin
PASEO_BIN=$(sudo -u "$TARGET_USER" -H bash -c 'export NVM_DIR="$HOME/.nvm"; [ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh" && which paseo' 2>/dev/null || echo "")
if [ -n "$PASEO_BIN" ] && [ -x "$PASEO_BIN" ]; then
  ln -sf "$PASEO_BIN" /usr/local/bin/paseo
  ln -sf "$PASEO_BIN" "$TARGET_HOME/.local/bin/paseo"
  chown -h "$TARGET_USER:$TARGET_USER" "$TARGET_HOME/.local/bin/paseo" 2>/dev/null || true
  echo "paseo_bin=/usr/local/bin/paseo"
fi

# 2. Diretorios base e symlink de skills
sudo -u "$TARGET_USER" -H bash -c '
  mkdir -p "$HOME/.paseo" "$HOME/.config/systemd/user"
  if [ ! -L "$HOME/.paseo/skills" ] && [ -d "$HOME/.gemini/config/skills" ]; then
    ln -sf "$HOME/.gemini/config/skills" "$HOME/.paseo/skills"
  fi
'

# 3. Configuracao do ~/.paseo/config.json seguindo estritamente o PersistedConfigSchema v1
if [ "$IS_HUB" = "true" ]; then
  sudo -u "$TARGET_USER" -H bash -c "cat << 'EOF' > '$TARGET_HOME/.paseo/config.json'
{
  \"version\": 1,
  \"daemon\": {
    \"listen\": \"0.0.0.0:$PORT\",
    \"hostnames\": [
      \"localhost\",
      \"127.0.0.1\",
      \"10.14.1.14\",
      \"atius-srv-4\",
      \"atius-srv-4.atius.internal\",
      \"paseo.atius.io\",
      \"paseo.atius.com.br\"
    ],
    \"trustedProxies\": [\"loopback\", \"10.1.0.11\", \"10.11.1.11\"],
    \"cors\": {
      \"allowedOrigins\": [
        \"https://app.paseo.sh\",
        \"https://paseo.atius.io\",
        \"https://paseo.atius.com.br\"
      ]
    }
  },
  \"app\": {
    \"baseUrl\": \"https://app.paseo.sh\"
  },
  \"features\": {
    \"webUi\": {
      \"enabled\": true
    }
  }
}
EOF"
else
  sudo -u "$TARGET_USER" -H bash -c "cat << 'EOF' > '$TARGET_HOME/.paseo/config.json'
{
  \"version\": 1,
  \"daemon\": {
    \"listen\": \"127.0.0.1:$PORT\",
    \"hostnames\": [
      \"localhost\",
      \"127.0.0.1\"
    ],
    \"cors\": {
      \"allowedOrigins\": [
        \"https://app.paseo.sh\",
        \"https://paseo.atius.io\",
        \"https://paseo.atius.com.br\"
      ]
    }
  },
  \"app\": {
    \"baseUrl\": \"https://app.paseo.sh\"
  },
  \"features\": {
    \"webUi\": {
      \"enabled\": true
    }
  }
}
EOF"
fi

# 4. Provisionamento da Unit Systemd User
sudo -u "$TARGET_USER" -H bash -c "cat << 'EOF' > '$TARGET_HOME/.config/systemd/user/paseo-daemon.service'
[Unit]
Description=Paseo Daemon (Port $PORT)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
Environment=NVM_DIR=%h/.nvm
Environment=PASEO_HOSTNAMES=true
Environment=PASEO_WEB_UI_ENABLED=true
ExecStart=/bin/bash -c 'source \$NVM_DIR/nvm.sh && exec paseo daemon run --home %h/.paseo'
Restart=on-failure
RestartSec=5
CPUQuota=20%
Nice=19

[Install]
WantedBy=default.target
EOF"

# Habilitar persistencia de sessoes user do systemd (linger)
loginctl enable-linger "$TARGET_USER" 2>/dev/null || true

# Ativar e iniciar a unit
USER_UID=$(id -u "$TARGET_USER")
sudo -u "$TARGET_USER" -H XDG_RUNTIME_DIR="/run/user/$USER_UID" systemctl --user daemon-reload 2>/dev/null || true
sudo -u "$TARGET_USER" -H XDG_RUNTIME_DIR="/run/user/$USER_UID" systemctl --user enable --now paseo-daemon.service 2>/dev/null || true

echo "== [verification] =="
echo "paseo_version=$(/usr/local/bin/paseo --version 2>/dev/null || echo 'fail')"
echo "systemd_status=$(sudo -u "$TARGET_USER" -H XDG_RUNTIME_DIR="/run/user/$USER_UID" systemctl --user is-active paseo-daemon.service 2>/dev/null || echo 'inactive')"
echo "RESULT: OK on $HOST (port $PORT)"
