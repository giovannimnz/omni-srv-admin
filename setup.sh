#!/bin/bash

# ==============================================================================
# SCRIPT DE SETUP AUTOMATIZADO - ATIUS SRV
# ==============================================================================

# Garante privilégios de sudo logo no início e mantém o cache ativo
sudo -v
while true; do sudo -n true; sleep 60; kill -0 "$$" || exit; done 2>/dev/null &

echo "=============================================================================="
echo "  SELEÇÃO DE ETAPA"
echo "=============================================================================="
echo "1. ETAPA 1: Preparação do Sistema (Swap, LXDE, XRDP, Segurança)"
echo "   -> Selecione esta opção na primeira execução."
echo "   -> O sistema precisará ser reiniciado ao final."
echo ""
echo "2. ETAPA 2: Instalação de Aplicativos e Tema (Chromium, Scripts)"
echo "   -> Selecione esta opção APÓS reiniciar o servidor e logar via RDP/SSH."
echo "=============================================================================="
read -p "Digite o número da etapa (1 ou 2): " STAGE_SELECTION

case $STAGE_SELECTION in
  1)
    echo ""
    echo "--- INICIANDO ETAPA 1 ---"

    # Define a senha do usuário ubuntu automaticamente
    USER_PASS="bkfigt54"
    echo "Definindo senha do sistema para o padrão configurado..."

    # Configurações para instalação silenciosa (evita prompts do dpkg)
    export DEBIAN_FRONTEND=noninteractive
    APT_OPTS="-y -o Dpkg::Options::=--force-confdef -o Dpkg::Options::=--force-confold"

    echo "🔄 Atualizando repositórios e sistema..."
    sudo apt-get update -quiet
    sudo apt-get upgrade $APT_OPTS

    echo "📦 Instalando ferramentas básicas..."
    sudo apt-get install $APT_OPTS nano

    echo "🐘 Instalando PostgreSQL 18 (mesma versão padrão deste servidor)..."
    sudo apt-get install $APT_OPTS postgresql-18 postgresql-client-18

    echo "💾 Configurando SWAP (10GB)..."
    if grep -q "swapfile" /etc/fstab; then
        echo "⚠️ Swapfile já configurado no fstab, pulando criação."
    else
        sudo fallocate -l 10G /swapfile
        sudo chmod 600 /swapfile
        sudo mkswap /swapfile
        sudo swapon /swapfile
        echo '/swapfile swap defaults 0 0' | sudo tee -a /etc/fstab
        echo "✅ Swap configurada."
    fi

    echo "🖥️ Instalando ambiente gráfico LXDE e XRDP..."
    sudo apt-get install $APT_OPTS lxde xrdp

    echo "🔑 Atualizando senha do usuário 'ubuntu'..."
    echo "ubuntu:$USER_PASS" | sudo chpasswd

    echo "🛡️ Configurando Firewall (Iptables)..."
    # Pré-configura as respostas do iptables-persistent para não perguntar nada
    echo "iptables-persistent iptables-persistent/autosave_v4 boolean true" | sudo debconf-set-selections
    echo "iptables-persistent iptables-persistent/autosave_v6 boolean true" | sudo debconf-set-selections
    
    sudo apt-get install $APT_OPTS iptables iptables-persistent

    if [ -d "iptables" ]; then
        cd iptables || exit
        if [ -f "iptables-backup-v4.conf" ]; then
            sudo iptables-restore < iptables-backup-v4.conf
        fi
        if [ -f "iptables-backup-v6.conf" ]; then
            sudo ip6tables-restore < iptables-backup-v6.conf
        fi
        sudo netfilter-persistent save
        sudo netfilter-persistent reload
        cd ..
        echo "✅ Regras de firewall aplicadas."
    else
        echo "⚠️ Diretório 'iptables' não encontrado. Pulando restauração de regras."
    fi

    echo ""
    echo "✅ ETAPA 1 CONCLUÍDA COM SUCESSO."
    echo "⚠️  AGORA REINICIE O SERVIDOR."
    echo "➡️  Após reiniciar, conecte-se via RDP e execute este script novamente escolhendo a OPÇÃO 2."
    read -p "Pressione ENTER para reiniciar agora (ou Ctrl+C para cancelar)..."
    sudo reboot
    ;;

  2)
    echo ""
    echo "--- INICIANDO ETAPA 2 ---"
    
    # Configurações para instalação silenciosa
    export DEBIAN_FRONTEND=noninteractive
    APT_OPTS="-y -o Dpkg::Options::=--force-confdef -o Dpkg::Options::=--force-confold"

    echo "🌐 Instalando Chromium e limitador de banda (trickle)..."
    sudo apt-get install $APT_OPTS trickle chromium-browser

    echo "🔗 Criando atalho na Área de Trabalho..."
    mkdir -p ~/Desktop
    cat <<DESKTOP > ~/Desktop/chromium-browser.desktop
[Desktop Entry]
Version=1.0
Type=Application
Name=Chromium
GenericName=Web Browser
Comment=Navegador Chromium
Exec=trickle -d 31250 -u 18750 chromium-browser %U
Icon=chromium-browser
Terminal=false
Categories=Network;WebBrowser;
StartupNotify=true
DESKTOP
    chmod +x ~/Desktop/chromium-browser.desktop

    echo "🎨 Executando script de instalação do tema (Dark Theme Ubuntu)..."
    INSTALL_SCRIPT="./dark-theme-ubuntu/install.sh"
    
    if [ -f "$INSTALL_SCRIPT" ]; then
        chmod +x "$INSTALL_SCRIPT"
        # Executa o install.sh
        $INSTALL_SCRIPT
    else
        echo "❌ Erro: Script $INSTALL_SCRIPT não encontrado!"
        exit 1
    fi

    echo ""
    echo "✅ ETAPA 2 CONCLUÍDA. O AMBIENTE ESTÁ PRONTO."
    ;;

  *)

    echo "❌ Opção inválida. Escolha 1 ou 2."
    exit 1
    ;;
esac
