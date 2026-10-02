#!/bin/bash
# antigravity-ui-dimension-fix.sh
# Aplica correção fleet-wide para bug de dimensionamento e corte no topo da janela do Antigravity
set -euo pipefail

TARGET_USER="ubuntu"
USER_HOME=$(getent passwd "$TARGET_USER" | cut -d: -f6 || echo "/home/$TARGET_USER")

echo "=== [Antigravity UI Dimension & Window Clipping Fix] ==="
echo "Host: $(hostname -f 2>/dev/null || hostname)"
echo "Target User: $TARGET_USER ($USER_HOME)"

# 1. Configurar Antigravity User settings.json
SETTINGS_DIR="$USER_HOME/.config/Antigravity/User"
SETTINGS_FILE="$SETTINGS_DIR/settings.json"

mkdir -p "$SETTINGS_DIR"
if [ ! -f "$SETTINGS_FILE" ]; then
    cat << 'EOF' > "$SETTINGS_FILE"
{
  "window.titleBarStyle": "native",
  "window.customTitleBarVisibility": "never",
  "window.menuBarVisibility": "classic",
  "window.zoomLevel": 0
}
EOF
    echo "[OK] Criado $SETTINGS_FILE com titleBarStyle=native."
else
    # Mesclar com python mantendo configurações existentes
    python3 - << 'EOF'
import json, os

path = os.environ.get("SETTINGS_FILE", "")
if not path or not os.path.exists(path):
    import sys
    sys.exit(0)

try:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
except Exception:
    data = {}

data["window.titleBarStyle"] = "native"
data["window.customTitleBarVisibility"] = "never"
data["window.menuBarVisibility"] = "classic"
if "window.zoomLevel" not in data:
    data["window.zoomLevel"] = 0

with open(path, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
EOF
    echo "[OK] Atualizado $SETTINGS_FILE com titleBarStyle=native."
fi
chown -R "$TARGET_USER:$TARGET_USER" "$USER_HOME/.config/Antigravity"

# 2. Configurar Openbox lxde-rc.xml
OPENBOX_DIR="$USER_HOME/.config/openbox"
OPENBOX_FILE="$OPENBOX_DIR/lxde-rc.xml"

if [ -f "$OPENBOX_FILE" ]; then
    if ! grep -q '<application class="\*ntigravity\*" name="\*ntigravity\*">' "$OPENBOX_FILE"; then
        sed -i 's|</applications>|  <application class="*ntigravity*" name="*ntigravity*">\n    <decor>yes</decor>\n  </application>\n</applications>|' "$OPENBOX_FILE"
        echo "[OK] Regra <decor>yes</decor> adicionada ao $OPENBOX_FILE."
    else
        echo "[OK] Regra <decor>yes</decor> já presente no $OPENBOX_FILE."
    fi
    chown "$TARGET_USER:$TARGET_USER" "$OPENBOX_FILE"
else
    echo "[INFO] Openbox rc não encontrado em $OPENBOX_FILE (host sem LXDE configurado para usuário)."
fi

# 3. Reconfigurar Openbox se em execução
if pgrep -u "$TARGET_USER" openbox >/dev/null 2>&1; then
    for disp in /tmp/.X11-unix/X*; do
        if [ -e "$disp" ]; then
            dnum=":${disp##*/X}"
            su - "$TARGET_USER" -c "DISPLAY=$dnum openbox --reconfigure" 2>/dev/null && echo "[OK] Openbox reconfigurado no display $dnum." || true
        fi
    done
fi

# 4. Status de binários
echo "--- Verificação de Binários ---"
which antigravity 2>/dev/null || echo "antigravity: not in PATH"
which antigravity-ide 2>/dev/null || echo "antigravity-ide: not in PATH"

echo "=== Concluído com sucesso ==="
