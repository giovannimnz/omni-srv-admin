#!/bin/bash
# Script de varredura antivírus e anti-malware (clamav, rkhunter, chkrootkit)

echo "Iniciando processo de verificação e limpeza..."
echo "Verificando instalação das ferramentas necessárias..."

# Instala ferramentas open-source de segurança (requer sudo)
sudo apt-get update -qq
sudo apt-get install -y clamav clamav-daemon rkhunter chkrootkit

# Atualiza a base de dados do ClamAV
echo "Atualizando base de dados do ClamAV..."
sudo systemctl stop clamav-freshclam 2>/dev/null
sudo freshclam
sudo systemctl start clamav-freshclam 2>/dev/null

TARGET_DIR="/home/ubuntu/GitHub/Dark_theme-Ubuntu"
LOG_DIR="/home/ubuntu/GitHub/antivirus"

echo "---------------------------------------------------"
echo "Executando ClamAV no diretório: $TARGET_DIR"
echo "Aviso: A flag --remove=yes excluirá os arquivos infectados."
echo "---------------------------------------------------"
sudo clamscan -r --remove=yes -i "$TARGET_DIR" | tee "$LOG_DIR/clamscan.log"

echo "---------------------------------------------------"
echo "Executando rkhunter (buscando por rootkits no sistema)..."
echo "---------------------------------------------------"
sudo rkhunter --update
sudo rkhunter -c --sk | tee "$LOG_DIR/rkhunter.log"

echo "---------------------------------------------------"
echo "Executando chkrootkit (buscando por rootkits no sistema)..."
echo "---------------------------------------------------"
sudo chkrootkit | tee "$LOG_DIR/chkrootkit.log"

echo "Varredura completa. Os logs foram salvos em: $LOG_DIR"
