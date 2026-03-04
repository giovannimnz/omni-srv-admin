#!/bin/bash
# Script de Reparo: Tema + Zsh + Fontes + Sublime Text + Ferramentas
# Autor: Gemini CLI

# Cores
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}Iniciando Script de Reparo e Checagem...${NC}"

sudo -v

install_pkg() {
    PACKAGE=$1
    if ! dpkg -s "$PACKAGE" &> /dev/null && ! command -v "$PACKAGE" &> /dev/null; then
        echo -e "${YELLOW}Instalando $PACKAGE...${NC}"
        sudo DEBIAN_FRONTEND=noninteractive apt-get install -y "$PACKAGE" >/dev/null 2>&1
        return $?
    fi
    return 0
}

# 1. Checagem do Sublime Text
echo -e "${YELLOW}Checando Sublime Text...${NC}"
if ! command -v subl &> /dev/null; then
    echo -e "${RED}Sublime Text não encontrado. Tentando reparar instalação...${NC}"
    sudo mkdir -p /etc/apt/trusted.gpg.d/
    install_pkg "apt-transport-https"
    install_pkg "wget"
    install_pkg "curl"
    install_pkg "gpg"

    wget -qO - https://download.sublimetext.com/sublimehq-pub.gpg | gpg --dearmor | sudo tee /etc/apt/trusted.gpg.d/sublimehq-archive.gpg > /dev/null
    echo "deb https://download.sublimetext.com/ apt/stable/" | sudo tee /etc/apt/sources.list.d/sublime-text.list
    sudo apt-get update -qq
    
    if ! install_pkg "sublime-text"; then
        ARCH=$(dpkg --print-architecture)
        if [ "$ARCH" = "arm64" ] || [ "$ARCH" = "aarch64" ]; then
            wget -qO /tmp/sublime-text.deb https://download.sublimetext.com/sublime-text_build-3211_arm64.deb
        else
            wget -qO /tmp/sublime-text.deb https://download.sublimetext.com/sublime-text_build-3211_amd64.deb
        fi
        sudo dpkg -i /tmp/sublime-text.deb || sudo apt-get install -f -y
    fi
    
    if [ -f /usr/share/applications/sublime_text.desktop ]; then
        xdg-mime default sublime_text.desktop text/plain >/dev/null 2>&1
        sudo sed -i 's/Categories=TextEditor;Development;/Categories=Utility;TextEditor;Development;/g' /usr/share/applications/sublime_text.desktop
    fi
else
    echo -e "${GREEN}Sublime Text OK.${NC}"
fi

# 2. Checagem de Utilitários do Painel (Network, Copyq)
echo -e "${YELLOW}Checando Utilitários do Painel...${NC}"
install_pkg "network-manager-gnome"
install_pkg "copyq"

AUTOSTART_FILE=~/.config/lxsession/LXDE/autostart
if [ -f "$AUTOSTART_FILE" ]; then
    grep -q "^@nm-applet" "$AUTOSTART_FILE" || { echo "@nm-applet" >> "$AUTOSTART_FILE"; echo -e "${GREEN}Adicionado nm-applet ao autostart.${NC}"; }
    grep -q "^@copyq" "$AUTOSTART_FILE" || { echo "@copyq" >> "$AUTOSTART_FILE"; echo -e "${GREEN}Adicionado copyq ao autostart.${NC}"; }

    # Configuração de Teclado ABNT2 (Padrão)
    sed -i '/@setxkbmap/d' "$AUTOSTART_FILE"
    sed -i '/@xmodmap/d' "$AUTOSTART_FILE"
    echo '@setxkbmap -model pc105 -layout br -variant abnt2 -option lv3:ralt_switch' >> "$AUTOSTART_FILE"
    echo -e "${GREEN}Configuração de teclado ABNT2 atualizada no autostart.${NC}"
else
    mkdir -p ~/.config/lxsession/LXDE
    echo "@nm-applet" > "$AUTOSTART_FILE"
    echo "@copyq" >> "$AUTOSTART_FILE"
    echo '@setxkbmap -model pc105 -layout br -variant abnt2 -option lv3:ralt_switch' >> "$AUTOSTART_FILE"
fi

# Aplicar o fix do teclado imediatamente
setxkbmap -model pc105 -layout br -variant abnt2 -option lv3:ralt_switch 2>/dev/null

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

# 3. Checagem do Painel LXDE (xkb e tray)
echo -e "${YELLOW}Checando configuração do LXPanel...${NC}"
PANEL_FILE=~/.config/lxpanel/LXDE/panels/panel
if [ -f "$PANEL_FILE" ]; then
    if ! grep -q "type=tray" "$PANEL_FILE"; then
        echo -e "${RED}Plugin tray faltando. Restaurando painel completo...${NC}"
        cp "$(dirname "$0")/config_files/panel" "$PANEL_FILE"
    fi
    if ! grep -q "type=xkb" "$PANEL_FILE"; then
        echo -e "${RED}Plugin de teclado faltando. Inserindo no painel...${NC}"
        sed -i 's/Plugin {/Plugin {\n  type=cpu\n  Config {\n  }\n}\nPlugin {\n  type=xkb\n  Config {\n    Model=pc105\n    LayoutsList=br\n    VariantsList=abnt2\n    ToggleOpt=grp:shift_caps_toggle\n    KeepSysLayouts=1\n    DisplayType=0\n    FlagSize=4\n  }\n}\nPlugin {/1' "$PANEL_FILE"
    fi
    lxpanelctl restart
fi

# 4. Fix AltGr para apps Electron (VSCode, Chromium)
echo -e "${YELLOW}Checando fix AltGr para Electron...${NC}"

# VSCode: Configura keyboard.dispatch=keyCode
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
echo -e "${GREEN}VSCode keyboard.dispatch configurado.${NC}"

# Chromium/Brave: Configura flags
for FLAGS_FILE in ~/.config/chromium-flags.conf ~/.config/brave-flags.conf ~/.config/electron-flags.conf; do
    if [ ! -f "$FLAGS_FILE" ] || ! grep -q 'gtk-version' "$FLAGS_FILE" 2>/dev/null; then
        echo "--gtk-version=4" >> "$FLAGS_FILE"
    fi
done

# Iniciar se não estiver rodando
pgrep -x nm-applet > /dev/null || nm-applet &
pgrep -x copyq > /dev/null || copyq &

echo -e "${GREEN}Reparo Concluído!${NC}"
