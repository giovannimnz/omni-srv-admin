# Revisão visual — Destino seguro hostname-only

Verdict: **12/12 PASS**.

Revisão independente dos 12 contact sheets, cada um com dois ciclos completos:

| Host | Valor visível em `Destino seguro` | Authenticated UI | Logout -> `/login` | Verdict |
|---|---|---|---|---|
| SSO central | `Nenhum destino selecionado` | sessão ativa neutra | PASS | PASS |
| SSH | `ssh.atius.com.br` | 5 destinos SSH | PASS | PASS |
| RDP | `rdp.atius.com.br` | formulário RDP | PASS | PASS |
| OCI | `oci.atius.com.br` | dashboard OCI | PASS | PASS |
| Talk | `talk.atius.com.br` | portal do cliente | PASS | PASS |
| Admin Talk | `admin.talk.atius.com.br` | master admin | PASS | PASS |
| Remote | `remote.atius.com.br` | desktop noVNC não preto | PASS | PASS |
| Grafana | `grafana.atius.com.br` | 12 painéis com dados | PASS | PASS |
| Portainer | `portainer.atius.com.br` | dashboard Kubernetes com dados | PASS | PASS |
| Docker | `docker.atius.com.br` | dashboard Kubernetes com dados | PASS | PASS |
| VPN | `vpn.atius.com.br` | dashboard WireGuard com dados | PASS | PASS |
| AdGuard | `adguard.atius.com.br` | dashboard DNS com dados | PASS | PASS |

Nenhum valor app-local contém protocolo, porta, barra, path, query ou fragmento.
SSH foi validado explicitamente como `ssh.atius.com.br`, nunca `/compute`.
