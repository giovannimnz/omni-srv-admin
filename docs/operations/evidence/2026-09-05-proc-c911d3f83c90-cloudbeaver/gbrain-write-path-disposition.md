# GBrain write-path disposition

- `add_timeline_entry` passou e teve readback pelo MCP.
- `gbrain capture --file` targeted falhou antes do write porque o provider de embedding retornou `Invalid token`.
- Nenhum retry cego e nenhum full sync foram executados.
- `gbrain sync --src-subpath ... --dry-run --json` retornou texto `Already up to date`; o failure observado foi somente o parser local que esperava JSON.
- O body foi atualizado por `gbrain import <temporary-single-file-tree> --no-embed`.
- Resultado: `1` page importada, `0` skips, `0` errors, `6` chunks.
- Readback confirmou o heading `Reconciliação CloudBeaver proc_c911d3f83c90`, o runtime contract corrigido e a timeline.
- Paths write-through não canônicos testados: todos ausentes.
- Residual externo ao t28: credencial do provider de embedding local inválida; embeddings foram deliberadamente diferidos.
