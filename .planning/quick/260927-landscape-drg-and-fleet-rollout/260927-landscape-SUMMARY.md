# Quick Task Summary: Landscape DRG Routing, Dual Domain (.io), and Fleet Script Rollout

- **Data:** 2026-09-27
- **Operador:** Antigravity / Omni Srv Admin
- **Escopo:** Frota Atius (`atius-srv-1`, `atius-srv-2`, `atius-srv-3`, `atius-srv-4`, `horistic-srv`)

## 1. Objetivos Alcançados

1. **Paridade de Commits:**
   - Consolidado repositório local e servidores remotos no commit canônico.
   - Removidos checkouts/perfis legados conforme solicitado.
2. **Novo Domínio `landscape.atius.io`:**
   - DNS Cloudflare: Registro A proxied apontando para `137.131.190.161`.
   - Certificado Let's Encrypt gerado em `atius-srv-1` via certbot DNS-01.
   - VHost Apache criado em `atius-srv-1` (`/etc/apache2/sites-available/landscape.atius.io.conf`).
   - `ServerAlias landscape.atius.io` e certificado Let's Encrypt instalado no container Landscape (`atius-srv-3`).
3. **Validação da Versão LTS do Landscape:**
   - Versão ativa: `24.04.14-0landscape0`.
   - Confirmado canal LTS estável oficial da Canonical via PPA `self-hosted-24.04` em Ubuntu 24.04 Noble.
4. **Otimização de Roteamento da Frota via OCI DRG:**
   - Adicionada entrada em `/etc/hosts` em todos os 5 nós:
     `10.13.1.13 landscape.atius.com.br landscape.atius.io`
   - Latência reduzida de ~59ms (Cloudflare WAN) para **0.6ms** (OCI DRG privado).
   - Elimina tráfego de egress para telemetria e heartbeat do agente.
5. **Execução Simultânea de Scripts via CLI:**
   - Comando `omni landscape run <script-id> --hosts all --wait --yes` com agregação de atividades e polling assíncrono.
   - Teste prático de frota: `reboot-required` executado com sucesso em 5/5 servidores simultaneamente.
6. **Testes e Qualidade:**
   - Criado `cli/omni/tests/test_landscape.py` com 6 testes unitários, todos passando.
   - Grafo de conhecimento Graphify atualizado e sincronizado.
