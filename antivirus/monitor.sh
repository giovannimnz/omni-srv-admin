#!/bin/bash
# Script de monitoramento de alto consumo de CPU e PM2

LOG_FILE="/home/ubuntu/GitHub/antivirus/monitor.log"

echo "=============================================" | tee -a "$LOG_FILE"
echo "Relatório de Monitoramento - $(date)" | tee -a "$LOG_FILE"
echo "=============================================" | tee -a "$LOG_FILE"

echo -e "
[1] Top 10 processos consumindo mais CPU:" | tee -a "$LOG_FILE"
ps aux --sort=-%cpu | head -n 11 | awk '{print $1, $2, $3"%", $4"%", $11}' | tee -a "$LOG_FILE"

echo -e "
[2] Status do PM2:" | tee -a "$LOG_FILE"
# Procura pelo PM2 no PATH ou usa npx
if command -v pm2 &> /dev/null; then
    pm2 list | tee -a "$LOG_FILE"
elif command -v npx &> /dev/null; then
    npx --no-install pm2 list 2>/dev/null | tee -a "$LOG_FILE"
else
    echo "Comando PM2 não foi encontrado." | tee -a "$LOG_FILE"
fi

echo -e "
[3] Buscando processos com nomes suspeitos (mineradores):" | tee -a "$LOG_FILE"
SUSPICIOUS=$(ps aux | grep -iE 'stratum|monero|xmrig|minerd|cryptonight|kdevtmpfsi' | grep -v grep)
if [ -n "$SUSPICIOUS" ]; then
    echo "$SUSPICIOUS" | tee -a "$LOG_FILE"
    echo "ALERTA: Processos suspeitos encontrados!" | tee -a "$LOG_FILE"
else
    echo "Nenhum processo suspeito óbvio encontrado neste momento." | tee -a "$LOG_FILE"
fi

echo -e "
Monitoramento concluído. Salvo em $LOG_FILE"
