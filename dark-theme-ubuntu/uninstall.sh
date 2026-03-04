#!/bin/bash
# Script de desinstalação e restauração do backup

# Cores
GREEN='\033[0;32m'
NC='\033[0m'

# Encontra o diretório de backup mais recente no mesmo local do script
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKUP_DIR=$(find "$SCRIPT_DIR" -maxdepth 1 -type d -name "lxde-theme-backup-*" | sort -r | head -n 1)

if [ -z "${BACKUP_DIR}" ]; then
    echo "Erro: Nenhum diretório de backup 'lxde-theme-backup-*' encontrado no diretório: $SCRIPT_DIR"
    exit 1
fi

echo -e "${GREEN}Restaurando a partir do backup mais recente: ${BACKUP_DIR}${NC}"

# --- Restaurar arquivos do backup ---

# 1. Tema GTK
if [ -f "${BACKUP_DIR}/gtkrc-2.0" ]; then
    echo "Restaurando .gtkrc-2.0..."
    cp "${BACKUP_DIR}/gtkrc-2.0" ~/.gtkrc-2.0
fi

# 2. Sessão LXDE
if [ -f "${BACKUP_DIR}/lxsession/desktop.conf" ]; then
    echo "Restaurando desktop.conf..."
    cp "${BACKUP_DIR}/lxsession/desktop.conf" ~/.config/lxsession/LXDE/desktop.conf
fi

# 3. Painel
if [ -f "${BACKUP_DIR}/lxpanel/panel" ]; then
    echo "Restaurando a configuração do painel..."
    cp "${BACKUP_DIR}/lxpanel/panel" ~/.config/lxpanel/LXDE/panels/panel
fi

# 4. Openbox (Bordas da Janela)
if [ -f "${BACKUP_DIR}/lxde-rc.xml" ]; then
    echo "Restaurando lxde-rc.xml..."
    cp "${BACKUP_DIR}/lxde-rc.xml" ~/.config/openbox/lxde-rc.xml
fi

# 5. Zsh RC
if [ -f "${BACKUP_DIR}/.zshrc.backup" ]; then
    echo "Restaurando .zshrc..."
    cp "${BACKUP_DIR}/.zshrc.backup" ~/.zshrc
fi

echo ""
echo -e "${GREEN}Arquivos restaurados.${NC}"
echo "Aplicando mudanças imediatas..."

# Reinicia componentes
if command -v lxpanelctl &> /dev/null; then
    lxpanelctl restart
fi

if command -v openbox &> /dev/null; then
    openbox --reconfigure
fi

echo ""
echo "Restauração concluída."
echo "IMPORTANTE: Para reverter completamente (especialmente o shell padrão e temas), faça logout e login novamente."
echo "Nota: O Zsh e seus plugins NÃO foram desinstalados, apenas a configuração (.zshrc) foi revertida."
