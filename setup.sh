#!/bin/bash

# Solicita a senha do usuário ubuntu
read -s -p "Digite a nova senha para o usuário 'ubuntu': " USER_PASS
echo
read -s -p "Confirme a nova senha: " USER_PASS_CONFIRM
echo

if [ "$USER_PASS" != "$USER_PASS_CONFIRM" ]; then
  echo "❌ As senhas não coincidem. Abortando."
  exit 1
fi

# Atualiza e prepara o sistema
sudo apt-get update -y && sudo apt-get upgrade -y
sudo apt install nano -y

# Criação do swap
sudo fallocate -l 10G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile swap defaults 0 0' | sudo tee -a /etc/fstab

# Instalação do ambiente gráfico LXDE e XRDP
sudo apt-get install lxde -y
sudo apt-get install xrdp -y

# Define a nova senha do usuário ubuntu
echo "ubuntu:$USER_PASS" | sudo chpasswd

# Aplica as regras de iptables já disponíveis no repositório clonado
sudo apt install iptables iptables-persistent -y
cd iptables || exit
sudo iptables-restore < iptables-backup-v4.conf
sudo ip6tables-restore < iptables-backup-v6.conf
sudo netfilter-persistent save
sudo netfilter-persistent reload
cd ..

# Pausa para o usuário se conectar via RDP e criar os diretórios do LXDE
echo ""
echo "🖥️ Conecte-se agora via RDP com o usuário 'ubuntu' para que os diretórios da interface gráfica sejam criados."
echo "Após se conectar e o ambiente de desktop carregar, volte aqui e pressione ENTER para continuar..."
read -p "Pressione ENTER para continuar após a conexão via RDP..."

# Instala o Chromium e trickle (limitador de banda)
sudo apt install trickle -y
sudo apt install chromium-browser -y

# Cria atalho na área de trabalho
mkdir -p ~/Desktop
cat <<EOF > ~/Desktop/chromium-browser.desktop
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
EOF

chmod +x ~/Desktop/chromium-browser.desktop

echo ""
echo "✅ Instalação finalizada com sucesso."