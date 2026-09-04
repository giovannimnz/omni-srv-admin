---
name: git-worktree-fleet-closeout
description: Consolida worktrees e branches Git em uma frota ATIUS, preserva heads úteis no GitHub, recupera storage e deixa cada checkout canônico em main. Use para limpeza multi-host de ~/GitHub; não use para apagar branches remotas sem autorização explícita.
---

# Git Worktree Fleet Closeout

Use para uma limpeza Git distribuída em que o resultado é um checkout por repositório, na branch canônica (`main` quando existir), sincronizado com o remoto e sem worktrees registrados desnecessários.

## Preparação

- Defina os hosts e os repositórios exatos. Para ATIUS, tente a rota SSH privada e depois a pública antes de declarar um host indisponível.
- Antes de mutar, em cada raiz de repositório rode `git fetch --all --prune`, `git status --short --branch`, `git worktree list --porcelain`, `git branch -vv --all`, `git stash list` e `git fsck --full --no-reflogs`.
- Não imprima segredos de diffs, `.env`, logs, backups ou dados temporários. Hidrate somente o profile Vault necessário para MCP HTTP.

## Classificação e preservação

- Para cada head local fora da canônica, compare ancestralidade, commits exclusivos e upstream contra `origin/main`.
- Head já contida em `main`: pode ser removida localmente após liberar worktrees que a usam.
- Head única: primeiro faça push para a branch remota já pretendida ou para `archive/<host>-<slug>-<data>`. Não force-push.
- Use a ref completa `refs/heads/...` ao enumerar/remover. `%(refname:short)` pode ser ambíguo quando uma tag usa o mesmo nome.
- Trate árvore suja separadamente: arquive apenas código, migrações, testes e documentação fonte após `git diff --check` e um scan de segredo. Não publique outputs Playwright, bancos temporários, logs, transcrições, `tmp/` ou Graphify regenerado sem revisão.

## Consolidação e limpeza

- Só atualize a árvore canônica após preservação: `git switch main` e `git merge --ff-only origin/main`.
- Remova worktrees limpos pelo Git: `git worktree remove <path>`; depois execute `git worktree prune -v`.
- Se o Git desregistrar um worktree mas não conseguir apagar o diretório, confirme que ele não aparece mais em `git worktree list --porcelain` e que não tem `.git`. Meça-o e remova somente esse caminho validado, sem cruzar filesystem (`find <path> -xdev -depth -delete`).
- Diretórios de evidência com owner correto porém sem bit de escrita podem impedir `git restore`. Ajuste permissões apenas do subdiretório identificado, restaure os arquivos rastreados e registre a causa.
- Para recuperar objects, rode `reflog expire` e `git gc --prune=now` sob o profile `builds`/cgroup do host. Se `git repack` ficar bloqueado sem filho produtor, encerre somente a cadeia iniciada pela operação, valide `status` e não tente limpeza ampla.

## Hooks, Graphify e CPU

- Um commit de archive não deve disparar Graphify, bundlers ou testes pesados fora do limite de CPU. Se um hook iniciar essa carga, interrompa apenas a cadeia do hook.
- Execute `git diff --cached --check` e a verificação de segredos antes de um commit de archive. Só então `git commit --no-verify` é aceitável para impedir a reexecução do hook já classificado; ele não substitui gates de segurança específicos do projeto.
- Toda atualização/rebuild Graphify ou `git gc` CPU-intensivo deve passar pelo wrapper de recursos do host.

## MCP HTTP Streamable e documentação

- Use GBrain e Obsidian via `https://mcp.atius.com.br/gbrain` e `https://mcp.atius.com.br/obsidian`, com `ATIUS_MCP_TOKEN` hidratado pelo profile Vault `atius-mcp`.
- GBrain é stateless para as chamadas usuais. Obsidian exige `initialize`, preservar `Mcp-Session-Id`, enviar `notifications/initialized` e então chamar ferramentas como `vault_write`.
- Registre no GBrain: estado final, heads arquivadas, bytes recuperados, bloqueios e próximo gate. Registre no Obsidian: comandos, evidências, limites e rollback.

## Encerramento

Prove em cada host/repositório: `git status --short --branch`, `git worktree list --porcelain`, `git branch -vv`, SHA de `main` igual ao upstream e espaço livre do filesystem. Liste hosts não alcançáveis e não contorne falhas de chave ou host key.
