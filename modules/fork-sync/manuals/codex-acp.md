---
project: codex-acp
version: 2
created: 2026-07-12
last_updated: 2026-07-12
generator: manual
---

# Manual de Atualizacao - codex-acp

## Topologia

- Fork: `https://github.com/giovannimnz/codex-acp`
- Upstream: `https://github.com/zed-industries/codex-acp`
- Source of truth operacional: subtree `/home/ubuntu/GitHub/wayland/codex-acp`
- Lane standalone `projects/codex-acp/sync.yaml`: desabilitado; o runner exige
  um repo com `.git` proprio e nao administra subtrees diretamente
- Gateway: `wss://codex-acp.atius.com.br/gateway`
- Segredo: profile/path Vault `codex-acp` / `kv/atius/codex-acp/gateway`

O OpenClaw Gateway usa o plugin oficial ACPX e aponta o target `codex` para o
wrapper instalado estavel `/home/ubuntu/.local/bin/codex-acp-atius`. O dominio passa por Cloudflare e pelo Apache no
`atius-srv-1` pelo IP OCI/DRG `10.11.1.11`; o backend escuta somente no IP
OCI/DRG `10.13.1.13` do `atius-srv-3`. A rede `10.100.100.0/24` e apenas
fallback de reserva e nao deve ser usada como caminho primario quando o DRG
estiver disponivel.

## Atualizacao segura do subtree

```bash
cd /home/ubuntu/GitHub/wayland
git subtree pull --prefix=codex-acp \
  https://github.com/giovannimnz/codex-acp.git main
bash scripts/atius-build-codex-acp.sh --test --force
bash scripts/atius-verify-codex-acp.sh --live
PYTHONPATH=/home/ubuntu/GitHub/omni-srv-admin/modules/fork-sync/cli \
  python3 -m fork_sync --json sync wayland --dry-run
```

O subtree preserva o historico completo do fork e nao contem `.git` aninhado.
O `target/` permanece cache local ignorado. O auto-patcher do Wayland carrega
uma copia de recuperacao do subtree, e `protected_paths` protege `codex-acp/`
durante merge com `FerroxLabs/wayland`.

Antes de publicar, execute a bateria Rust pelo script limitado a 20% de CPU,
os testes Wayland focados, `/acp doctor` e um prompt real pelo agente remoto.
O antigo checkout `/home/ubuntu/GitHub/codex-acp` deve permanecer apenas como
backup arquivado fora desse path; nao e dependencia de runtime. Nunca grave o
token em git ou Markdown.
