# Validação de Roteamento DRG Horistic -> atius-srv-1

- **Data:** 2026-11-02
- **Escopo:** Cutover de IP DRG e alinhamento de rotas Apache2 no `horistic-srv`.
- **Status:** CONCLUÍDO & VALIDADO

## 1. Conectividade DRG
- Rota no `horistic-srv`: `10.1.0.11 via 10.21.1.1 dev enp1s0 src 10.21.1.21`
- Latência média: 0.67 ms (0% packet loss)

## 2. Apache2 Sites no `horistic-srv`
- `api.horistic.com.conf` -> `http://10.1.0.11:8050/` (HTTP 404 / Express Backend)
- `trade.horistic.com.conf` -> `http://10.1.0.11:3050/` (HTTP 307 / Atius SSO Redirect)
- `webhook.horistic.com.conf` -> `http://10.1.0.11:8099/` (HTTP 200 / Webhook)
- `painel.horistic.com.conf` -> `http://10.1.0.11:3050/` (HTTP 307 / Atius SSO Redirect)
- `dashboard.horistic.com.conf` -> `http://10.1.0.11:3050/` (HTTP 307 / Atius SSO Redirect)
- `backtest.horistic.com.conf` -> `http://10.1.0.11:3050/` (HTTP 307 / Atius SSO Redirect)
- `remote.horistic-srv-1.atius.com.br.conf` -> `http://127.0.0.1:6080/` (noVNC Local)

## 3. Limpeza & Estabilização no `atius-srv-1`
- Desativados vhosts legados `paperclip-http.conf` e `paperclip.atius.com.br-ssl.conf` (porta 31810 inacessível).
- Executado `pm2 update` no `atius-srv-1`:
  - 35 processos PM2 100% online.
  - Resolvido warning de daemon out-of-date que quebrava o JSON do `pm2 jlist`.
  - CPU: 0%, RAM: 40.8%.
- `/var/log/apache2/error.log` estabilizado com zero erros.
