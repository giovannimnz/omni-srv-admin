# Operação Landscape: Roteamento Privado DRG e Automação de Scripts em Frota

- **Data de Ativação:** 2026-09-27
- **Versão do Landscape Server:** `24.04.14-0landscape0` (Canonical LTS)
- **Servidores Gerenciados:** `atius-srv-1`, `atius-srv-2`, `atius-srv-3`, `atius-srv-4`, `horistic-srv`

---

## 1. Endpoints e Domínios

| Domínio | Função | Terminação SSL | Backend |
|---------|--------|----------------|---------|
| `https://landscape.atius.com.br` | URL Primária / Dashboard | Borda Apache (`atius-srv-1`) | LXD Container `landscape` (`10.13.1.13:443`) |
| `https://landscape.atius.io` | URL Alternativa / Dashboard | Borda Apache (`atius-srv-1`) | LXD Container `landscape` (`10.13.1.13:443`) |
| `https://10.13.1.13:443` | Rota Interna Direta DRG | Container Apache interno | Processos Landscape WSGI |

Ambos os domínios possuem certificados SSL válidos emitidos pelo Let's Encrypt através do plugin Cloudflare DNS (`certbot --dns-cloudflare`). O container interno em `atius-srv-3` também teve seu certificado autoassinado substituído pelo Let's Encrypt para garantir handshake TLS rigoroso sem skips de verificação.

---

## 2. Topologia de Rede OCI DRG

Para evitar tráfego de saída WAN e reduzir a latência das trocas de mensagens do `landscape-client`, todos os 5 nós da frota possuem mapeamento direto em `/etc/hosts`:

```text
10.13.1.13 landscape.atius.com.br landscape.atius.io
```

### Métricas de Comunicação

- **Caminho WAN (Cloudflare Proxy):** ~59 ms de RTT, dependente de tráfego de egress e rota externa.
- **Caminho DRG Privado (OCI):** **0.6 ms** de RTT (ICMP) e ~16 ms para o handshake HTTPS completo.
- **Resultado:** Redução de 99% na latência e estabilidade total das trocas de telemetria da frota.

---

## 3. Execução Simultânea de Scripts via CLI Omni

O CLI `omni` possui suporte nativo para orquestrar scripts na frota através da API do Landscape:

```bash
# Execução simultânea com polling e exibição de saída por nó:
python -m omni landscape run <script-id> --hosts all --wait --yes
```

### Scripts Disponíveis no Manifesto (`inventory/landscape-scripts.yaml`)

1. `fleet-status`: Coleta status básico do sistema operacional, uptime e memória.
2. `version-report`: Relatório de versões de pacotes e kernel instalados.
3. `pm2-root-cleanup`: Limpeza de logs e processos PM2 órfãos.
4. `apt-upgrade-plan`: Execução de simulação (`--dry-run`) de atualizações pendentes.
5. `reboot-required`: Verificação de necessidade de reboot (`/var/run/reboot-required`).

### Parâmetros Suportados

- `--hosts`: `all` ou lista separada por vírgula (`atius-srv-1,atius-srv-2`).
- `--wait`: Ativa polling contínuo da API até conclusão em todos os computadores.
- `--timeout`: Tempo limite em segundos (padrão: 180s).
- `--yes`: Confirma a execução imediata (sem `--yes`, executa apenas `plan-only`).
- `--json`: Saída formatada em JSON estruturado para pipelines de automação.

---

## 4. Testes e Validação

A integração do Landscape é coberta por testes automatizados em `cli/omni/tests/test_landscape.py`:

```powershell
pytest cli/omni/tests/test_landscape.py -v
```

Cobertura garantida:
- Resolução e validação de nomes de hosts autorizados.
- Geração da query de busca por `title:`.
- Validação e parsing do manifesto de scripts.
- Inclusão de User-Agent customizado nas requisições HTTP da API.
- Execução segura em modo `plan-only`.
