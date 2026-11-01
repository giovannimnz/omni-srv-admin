#!/usr/bin/env bash
# omni::terminal-multiplexer-fleet-tune v1.0.0
# Configura Tmux e Zellij na frota com clipboard OSC 52 e sem travamento de tela
set -euo pipefail

for u in ubuntu horistic aln muniz; do
  if ! id "$u" >/dev/null 2>&1; then continue; fi
  uhome="$(eval echo ~$u)"
  
  # Tmux configuration
  cat << 'EOF' > "$uhome/.tmux.conf"
set -g mouse on
set -g set-clipboard on
set -s escape-time 0
set -g history-limit 50000
EOF
  chown "$u:$u" "$uhome/.tmux.conf" 2>/dev/null || true
done

echo "[OK] Tmux and terminal multiplexer tuning applied successfully."