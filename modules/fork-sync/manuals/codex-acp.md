---
project: codex-acp
version: 1
created: 2026-07-12
last_updated: 2026-07-12
generator: manual
---

# Manual de Atualizacao - codex-acp

## Topologia

- Fork: `https://github.com/giovannimnz/codex-acp`
- Upstream: `https://github.com/zed-industries/codex-acp`
- Checkout: `/home/ubuntu/GitHub/codex-acp` no `atius-srv-3`
- Gateway: `wss://codex-acp.atius.com.br/gateway`
- Segredo: profile/path Vault `codex-acp` / `kv/atius/codex-acp/gateway`

O OpenClaw Gateway usa o plugin oficial ACPX e aponta o target `codex` para o
wrapper ATIUS deste fork. O dominio passa por Cloudflare e pelo Apache no
`atius-srv-1` pelo IP OCI/DRG `10.11.1.11`; o backend escuta somente no IP
OCI/DRG `10.13.1.13` do `atius-srv-3`. A rede `10.100.100.0/24` e apenas
fallback de reserva e nao deve ser usada como caminho primario quando o DRG
estiver disponivel.

## Sync seguro

```bash
PYTHONPATH=modules/fork-sync/cli python3 -m fork_sync --json sync codex-acp --dry-run
PYTHONPATH=modules/fork-sync/cli python3 -m fork_sync sync codex-acp
```

Antes de publicar, execute `cargo check`, `cargo test --lib`, `/acp doctor` e
um prompt real pelo agente remoto. Nunca grave o token em git ou Markdown.
