# Revisão visual pós-reload Apache

Veredito: `4/4 PASS`.

| Host | Login app-local | Aplicação autenticada útil | Logout app-local | Veredito |
|---|---|---|---|---|
| Grafana | `grafana.atius.com.br` | painéis CoreDNS com dados; sem `No data`, loading ou query error | `/login` | PASS |
| Portainer | `portainer.atius.com.br` | dashboard Kubernetes `atius-k3s` com contadores | `/login` | PASS |
| Docker | `docker.atius.com.br` | dashboard Kubernetes `atius-k3s` com contadores | `/login` | PASS |
| VPN | `vpn.atius.com.br` | WireGuard online, peers e tráfego | `/login` | PASS |

Cada host teve dois ciclos independentes com `access`, `login`, `authenticated` e `logged-out`.
Os contact sheets estão em `_visual-contact-sheets/`.
