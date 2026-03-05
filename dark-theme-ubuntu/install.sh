#!/bin/bash
# Script de Instalação Suprema: Tema + Zsh + Fontes + Sublime Text + Ferramentas
# Autor: Gemini CLI

# Cores
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

CONFIG_DIR=$(dirname "$0")/config_files
THEME_DIR=$(dirname "$0")/themes
FONT_DIR=$(dirname "$0")/fonts
BACKUP_DIR="$(cd "$(dirname "$0")" && pwd)/lxde-theme-backup-$(date +%Y%m%d_%H%M%S)"

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

# Função de instalação silenciosa (com update e retry)
install_pkg() {
    PACKAGE=$1
    if ! dpkg -s "$PACKAGE" &> /dev/null && ! command -v "$PACKAGE" &> /dev/null; then
        echo -e "${YELLOW}Instalando $PACKAGE...${NC}"
        sudo DEBIAN_FRONTEND=noninteractive apt-get install -y "$PACKAGE" >/dev/null 2>&1
        if [ $? -ne 0 ]; then
            echo -e "${YELLOW}Falha na instalação. Atualizando repositórios e tentando novamente...${NC}"
            sudo apt-get update -qq
            sudo DEBIAN_FRONTEND=noninteractive apt-get install -y "$PACKAGE" >/dev/null 2>&1
            if [ $? -ne 0 ]; then
                echo -e "${RED}ERRO: Não foi possível instalar $PACKAGE.${NC}"
                return 1
            fi
        fi
        echo -e "${GREEN}$PACKAGE instalado com sucesso.${NC}"
        return 0
    else
        echo -e "${GREEN}$PACKAGE já está instalado.${NC}"
        return 0
    fi
}

# ==============================================================================
# 1. INSTALAÇÃO DO SUBLIME TEXT
# ==============================================================================
echo ""
echo -e "${GREEN}--- Etapa 1: Sublime Text (Editor Padrão) ---${NC}"

if ! command -v subl &> /dev/null; then
    sudo mkdir -p /etc/apt/trusted.gpg.d/
    install_pkg "apt-transport-https"
    install_pkg "wget"
    install_pkg "curl"
    install_pkg "gpg"

    smart_run wget -qO - https://download.sublimetext.com/sublimehq-pub.gpg | gpg --dearmor | sudo tee /etc/apt/trusted.gpg.d/sublimehq-archive.gpg > /dev/null
    echo "deb https://download.sublimetext.com/ apt/stable/" | sudo tee /etc/apt/sources.list.d/sublime-text.list
    sudo apt-get update -qq
    
    if ! install_pkg "sublime-text"; then
        echo -e "${YELLOW}Falha ao instalar o Sublime pelo repositório. Tentando via deb direto...${NC}"
        ARCH=$(dpkg --print-architecture)
        if [ "$ARCH" = "arm64" ] || [ "$ARCH" = "aarch64" ]; then
            wget -qO /tmp/sublime-text.deb https://download.sublimetext.com/sublime-text_build-3211_arm64.deb
        else
            wget -qO /tmp/sublime-text.deb https://download.sublimetext.com/sublime-text_build-3211_amd64.deb
        fi
        sudo dpkg -i /tmp/sublime-text.deb || sudo apt-get install -f -y
    fi
fi

# Configura como padrão se existir
if [ -f /usr/share/applications/sublime_text.desktop ]; then
    xdg-mime default sublime_text.desktop text/plain >/dev/null 2>&1
    sudo sed -i 's/Categories=TextEditor;Development;/Categories=Utility;TextEditor;Development;/g' /usr/share/applications/sublime_text.desktop
fi

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
# 3. UTILITÁRIOS DO PAINEL (Rede, Teclado, Área de Transferência)
# ==============================================================================
echo ""
echo -e "${GREEN}--- Etapa 3: Utilitários do Painel ---${NC}"
install_pkg "network-manager-gnome"
install_pkg "copyq"
install_pkg "alsa-utils"

AUTOSTART_FILE=~/.config/lxsession/LXDE/autostart
mkdir -p ~/.config/lxsession/LXDE
touch "$AUTOSTART_FILE"
grep -q "^@lxpanel --profile LXDE" "$AUTOSTART_FILE" || echo "@lxpanel --profile LXDE" >> "$AUTOSTART_FILE"
grep -q "^@pcmanfm --desktop --profile LXDE" "$AUTOSTART_FILE" || echo "@pcmanfm --desktop --profile LXDE" >> "$AUTOSTART_FILE"
grep -q "^@xscreensaver -no-splash" "$AUTOSTART_FILE" || echo "@xscreensaver -no-splash" >> "$AUTOSTART_FILE"
grep -q "^@nm-applet" "$AUTOSTART_FILE" || echo "@nm-applet" >> "$AUTOSTART_FILE"
# Garante comando de exibição correto
if grep -q "@copyq" "$AUTOSTART_FILE"; then
    sed -i 's/@copyq.*/@copyq --start-server show/' "$AUTOSTART_FILE"
else
    echo "@copyq --start-server show" >> "$AUTOSTART_FILE"
fi

# Teclado ABNT2 (Padrão)
sed -i '/@setxkbmap/d' "$AUTOSTART_FILE"
sed -i '/@xmodmap/d' "$AUTOSTART_FILE"
echo '@setxkbmap -model pc105 -layout br -variant abnt2 -option lv3:ralt_switch' >> "$AUTOSTART_FILE"

# Indicador de teclado em imagem com rótulo "PT"
if [ -d "/usr/share/lxpanel/images/xkb-flags" ]; then
    echo -e "${YELLOW}Ajustando indicador do teclado para PT...${NC}"
    install_pkg "imagemagick"
    convert -size 300x170 xc:'#2b2b2b' -font DejaVu-Sans-Bold -pointsize 96 -fill '#cccccc' -gravity center -annotate +0-6 "PT" -fill '#228B22' -draw 'rectangle 0,150 300,170' PNG24:/tmp/pt_flag.png
    sudo cp /tmp/pt_flag.png '/usr/share/lxpanel/images/xkb-flags/br(abnt.png'
    sudo cp /tmp/pt_flag.png '/usr/share/lxpanel/images/xkb-flags/br(abnt2).png'
    sudo cp /tmp/pt_flag.png /usr/share/lxpanel/images/xkb-flags/br.png
    rm -f /tmp/pt_flag.png
fi

# ==============================================================================
# 3.1 FIX ALTGR PARA ELECTRON (VSCode, Chromium) EM SESSÕES REMOTAS
# ==============================================================================
echo ""
echo -e "${GREEN}--- Etapa 3.1: Fix AltGr para apps Electron ---${NC}"

# VSCode: Configura keyboard.dispatch=keyCode para corrigir AltGr
VSCODE_SETTINGS=~/.config/Code/User/settings.json
mkdir -p ~/.config/Code/User
python3 - << 'PY'
import json, os
path = os.path.expanduser('~/.config/Code/User/settings.json')
try:
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
except Exception:
    data = {}
data['keyboard.dispatch'] = 'keyCode'
with open(path, 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)
    f.write('\n')
PY

# Chromium/Brave: Configura flag para corrigir dispatch de teclado
for FLAGS_FILE in ~/.config/chromium-flags.conf ~/.config/brave-flags.conf ~/.config/electron-flags.conf; do
    if [ ! -f "$FLAGS_FILE" ] || ! grep -q 'gtk-version' "$FLAGS_FILE" 2>/dev/null; then
        echo "--gtk-version=4" >> "$FLAGS_FILE"
    fi
done

# Aplicar configuração de teclado (ABNT2) na sessão atual
setxkbmap -model pc105 -layout br -variant abnt2 -option lv3:ralt_switch 2>/dev/null

# ==============================================================================
# 4. AMBIENTE GRÁFICO (LXDE/Openbox)
# ==============================================================================
echo ""
echo -e "${GREEN}--- Etapa 4: Visual e Contraste ---${NC}"

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
    mkdir -p ~/.config/lxpanel/LXDE/panels
    cp "${CONFIG_DIR}/panel" ~/.config/lxpanel/LXDE/panels/panel

    # Configura autostart para garantir itens do painel (Rede, CopyQ)
    AUTOSTART_FILE=~/.config/lxsession/LXDE/autostart
    if [ -f "$AUTOSTART_FILE" ]; then
        grep -q "@nm-applet" "$AUTOSTART_FILE" || echo "@nm-applet" >> "$AUTOSTART_FILE"
        if grep -q "@copyq" "$AUTOSTART_FILE"; then
            sed -i 's/@copyq.*/@copyq --start-server show/' "$AUTOSTART_FILE"
        else
            echo "@copyq --start-server show" >> "$AUTOSTART_FILE"
        fi
    fi

    # Tema Openbox
    if [ -d "$THEME_DIR/Dark-Onyx" ]; then
        mkdir -p ~/.themes/Dark-Onyx/openbox-3
        cp -r "${THEME_DIR}/Dark-Onyx/openbox-3/"* ~/.themes/Dark-Onyx/openbox-3/
        cp "${CONFIG_DIR}/lxde-rc.xml" ~/.config/openbox/lxde-rc.xml
        smart_run openbox --reconfigure &> /dev/null
    fi
fi

# ==============================================================================
# 5. ZSH E OH MY ZSH
# ==============================================================================
echo ""
echo -e "${GREEN}--- Etapa 5: Terminal Zsh ---${NC}"

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
# 6. FINALIZAÇÃO
# ==============================================================================
echo ""
echo -e "${GREEN}INSTALAÇÃO CONCLUÍDA COM SUCESSO!${NC}"
lxpanelctl restart >/dev/null 2>&1 || true
sleep 1
pgrep -x lxpanel >/dev/null || nohup lxpanel --profile LXDE >/dev/null 2>&1 &
echo "O Sublime Text foi definido como editor padrão e adicionado ao painel."
echo "Aplicativos do painel (Rede, Idioma e Copyq) foram configurados para iniciar e exibirem no tray permanentemente."
echo "Tudo pronto! Faça logout e login para aplicar todas as mudanças."