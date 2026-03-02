#!/bin/bash
# Script de Instalação Suprema: Tema + Zsh + Fontes + Sublime Text
# Autor: Gemini CLI

# Cores
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

CONFIG_DIR=$(dirname "$0")/config_files
THEME_DIR=$(dirname "$0")/themes
FONT_DIR=$(dirname "$0")/fonts
BACKUP_DIR=~/lxde-theme-backup-$(date +%Y%m%d_%H%M%S)

# ==============================================================================
# 0. INICIALIZAÇÃO E PERMISSÕES (SUDO AUTOMÁTICO)
# ==============================================================================
echo -e "${GREEN}Iniciando Instalação Suprema Automatizada...${NC}"

# Pede senha uma vez e mantém o cache
sudo -v
while true; do sudo -n true; sleep 60; kill -0 "$$" || exit; done 2>/dev/null &

# Função para executar comandos com sudo automático em caso de falha de permissão
smart_run() {
    if "$@"; then
        return 0
    else
        echo -e "${YELLOW}Tentando novamente com privilégios de superusuário...${NC}"
        sudo "$@"
    fi
}

# Função de instalação silenciosa
install_pkg() {
    PACKAGE=$1
    if ! dpkg -s "$PACKAGE" &> /dev/null && ! command -v "$PACKAGE" &> /dev/null; then
        echo -e "${YELLOW}Instalando $PACKAGE...${NC}"
        sudo DEBIAN_FRONTEND=noninteractive apt-get install -y "$PACKAGE" >/dev/null 2>&1
    else
        echo -e "${GREEN}$PACKAGE já instalado.${NC}"
    fi
}

# ==============================================================================
# 1. INSTALAÇÃO DO SUBLIME TEXT (ARM64)
# ==============================================================================
echo ""
echo -e "${GREEN}--- Etapa 1: Sublime Text (Editor Padrão) ---${NC}"

if ! command -v subl &> /dev/null; then
    smart_run wget -qO - https://download.sublimetext.com/sublimehq-pub.gpg | gpg --dearmor | sudo tee /etc/apt/trusted.gpg.d/sublimehq-archive.gpg > /dev/null
    echo "deb https://download.sublimetext.com/ apt/stable/" | sudo tee /etc/apt/sources.list.d/sublime-text.list
    sudo apt-get update -qq
    install_pkg "sublime-text"
fi

# Configura como padrão
xdg-mime default sublime_text.desktop text/plain >/dev/null 2>&1
sudo sed -i 's/Categories=TextEditor;Development;/Categories=Utility;TextEditor;Development;/g' /usr/share/applications/sublime_text.desktop

# ==============================================================================
# 2. INSTALAÇÃO DE FONTES (Apple, Microsoft, Tahoma)
# ==============================================================================
echo ""
echo -e "${GREEN}--- Etapa 2: Fontes ---${NC}"

echo "ttf-mscorefonts-installer msttcorefonts/accepted-mscorefonts-eula select true" | sudo debconf-set-selections
install_pkg "ttf-mscorefonts-installer"

if [ -d "$FONT_DIR" ]; then
    sudo mkdir -p /usr/local/share/fonts/apple
    sudo cp -r "${FONT_DIR}/"* /usr/local/share/fonts/apple/
    sudo fc-cache -f >/dev/null
    echo -e "${GREEN}Fontes Apple e Tahoma instaladas.${NC}"
fi

# ==============================================================================
# 3. AMBIENTE GRÁFICO (LXDE/Openbox)
# ==============================================================================
echo ""
echo -e "${GREEN}--- Etapa 3: Visual e Contraste ---${NC}"

if command -v lxpanel &> /dev/null; then
    install_pkg "gtk2-engines-pixbuf"
    mkdir -p "${BACKUP_DIR}/lxsession" "${BACKUP_DIR}/lxpanel" "${BACKUP_DIR}/openbox"

    # Backup e Aplicação
    [ -f ~/.gtkrc-2.0 ] && cp ~/.gtkrc-2.0 "${BACKUP_DIR}/"
    [ -f ~/.config/lxsession/LXDE/desktop.conf ] && cp ~/.config/lxsession/LXDE/desktop.conf "${BACKUP_DIR}/lxsession/"
    [ -f ~/.config/lxpanel/LXDE/panels/panel ] && cp ~/.config/lxpanel/LXDE/panels/panel "${BACKUP_DIR}/lxpanel/"
    [ -f ~/.config/openbox/lxde-rc.xml ] && cp ~/.config/openbox/lxde-rc.xml "${BACKUP_DIR}/openbox/"

    cp "${CONFIG_DIR}/gtkrc-2.0" ~/.gtkrc-2.0
    cp "${CONFIG_DIR}/desktop.conf" ~/.config/lxsession/LXDE/desktop.conf
    cp "${CONFIG_DIR}/panel" ~/.config/lxpanel/LXDE/panels/panel

    # Tema Openbox
    if [ -d "$THEME_DIR/Dark-Onyx" ]; then
        mkdir -p ~/.themes/Dark-Onyx/openbox-3
        cp -r "${THEME_DIR}/Dark-Onyx/openbox-3/"* ~/.themes/Dark-Onyx/openbox-3/
        cp "${CONFIG_DIR}/lxde-rc.xml" ~/.config/openbox/lxde-rc.xml
        smart_run openbox --reconfigure &> /dev/null
    fi
fi

# ==============================================================================
# 4. ZSH E OH MY ZSH
# ==============================================================================
echo ""
echo -e "${GREEN}--- Etapa 4: Terminal Zsh ---${NC}"

install_pkg "zsh"
install_pkg "git"
install_pkg "curl"

if [ ! -d "$HOME/.oh-my-zsh" ]; then
    sh -c "$(curl -fsSL https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh)" "" --unattended >/dev/null
fi

ZSH_CUSTOM=${ZSH_CUSTOM:-$HOME/.oh-my-zsh/custom}
[ ! -d "$ZSH_CUSTOM/plugins/zsh-syntax-highlighting" ] && git clone https://github.com/zsh-users/zsh-syntax-highlighting.git "$ZSH_CUSTOM/plugins/zsh-syntax-highlighting" >/dev/null 2>&1
[ ! -d "$ZSH_CUSTOM/plugins/zsh-autosuggestions" ] && git clone https://github.com/zsh-users/zsh-autosuggestions "$ZSH_CUSTOM/plugins/zsh-autosuggestions" >/dev/null 2>&1

if [ -f "${CONFIG_DIR}/.zshrc" ]; then
    [ -f ~/.zshrc ] && cp ~/.zshrc "${BACKUP_DIR}/.zshrc.backup"
    cp "${CONFIG_DIR}/.zshrc" ~/.zshrc
fi

# Configura o prompt customizado do Zsh (Caminho completo e Usuário)
grep -q "PROMPT='%{\$fg\[green\]%}%n@%m%{\$reset_color%}:%{\$fg\[blue\]%}%~%{\$reset_color%} \$(git_prompt_info)➜ '" ~/.zshrc || echo -e "\n# Configura o ZSH para exibir o caminho completo e o usuário (estilo Bash)\nPROMPT='%{\$fg[green]%}%n@%m%{\$reset_color%}:%{\$fg[blue]%}%~%{\$reset_color%} \$(git_prompt_info)➜ '" >> ~/.zshrc

[ "$(basename "$SHELL")" != "zsh" ] && sudo chsh -s "$(which zsh)" "$USER"

# ==============================================================================
# 5. FINALIZAÇÃO
# ==============================================================================
echo ""
echo -e "${GREEN}INSTALAÇÃO CONCLUÍDA COM SUCESSO!${NC}"
smart_run lxpanelctl restart
echo "O Sublime Text foi definido como editor padrão e adicionado ao painel."
echo "Tudo pronto! Faça logout e login para aplicar todas as mudanças."
