# Seal pós-cleanup — VPN Atius

- Escopo: reconciliação tardia do smoke Next órfão `proc_9db50fade3fc`.
- Classificação: processo fora de PM2/systemd/Apache, cwd de rollback deletado, listener `127.0.0.1:3200`.
- Produção preservada: `vpn-frontend.service`, porta `3100`, sem restart.
- Cleanup: SIGTERM graceful, porta `3200` liberada, zero processos com cwd deletado.
- Runtime: Apache `Syntax OK`, VPN pública `https://vpn.atius.com.br/login` HTTP `200`.
- Lifecycle: `2/2 PASS_SUBSET`, `8/8` screenshots, zero failure artifacts.
- Vision: `PASS`; login Atius uniforme, painel WireGuard operacional nos dois ciclos, logout para `/login`.
- Harness: `E2E_OUTPUT_DIR` agora é honrado; regression test real confirmou isolamento e ausência do diretório default.
- Autoridade do fleet permanece o pack `../2026-07-31-full-fleet-final-strict-20260731-202636/` com `24/24`.
- Commit/push: nenhum.
