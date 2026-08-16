# Revisão visual independente — Atius SSO fleet

- Referência: `/home/ubuntu/Imagens/Prints/sso-ssh-base-model.png`
- Método: 12 contact sheets, oito estados por host, análise visual independente.
- Resultado: `12/12 PASS`.

| Host | Dois ciclos | Aplicação autenticada | Logout → app-local `/login` | Visual |
|---|---:|---|---:|---:|
| `sso.atius.com.br` | PASS | estado neutro `Sessão Atius ativa` | PASS | PASS |
| `ssh.atius.com.br` | PASS | painel SSH `/compute` | PASS | PASS |
| `rdp.atius.com.br` | PASS | formulário real `GIOVANNI-W11-PC · RDP` | PASS | PASS |
| `oci.atius.com.br` | PASS | dashboard OCI | PASS | PASS |
| `talk.atius.com.br` | PASS | shell Talk | PASS | PASS |
| `admin.talk.atius.com.br` | PASS | `Atius Master Admin` | PASS | PASS |
| `remote.atius.com.br` | PASS | desktop noVNC/LXDE renderizado nos dois ciclos | PASS | PASS |
| `grafana.atius.com.br` | PASS | CoreDNS, 12 painéis com dados, inclusive TCP | PASS | PASS |
| `portainer.atius.com.br` | PASS | Kubernetes `atius-k3s` com contagens | PASS | PASS |
| `docker.atius.com.br` | PASS | Portainer/Kubernetes com contagens | PASS | PASS |
| `vpn.atius.com.br` | PASS | painel WireGuard com dados | PASS | PASS |
| `adguard.atius.com.br` | PASS | AdGuard Home com estatísticas | PASS | PASS |

## Gates visuais que impediram falso PASS

- Grafana: `Sem dados`, `No data`, loading ou erro em qualquer painel visível falha o ciclo.
- Remote: shell autenticado não basta; framebuffer precisa ter diversidade visual e pixels não pretos.
- Remote final: `421` cores e `4,31%` de pixels não pretos em cada screenshot autenticada.
- RDP: detach do input só é aceito após URL same-origin e UI autenticada passarem.

Nenhuma credencial, cookie, token ou CSRF foi persistido.
