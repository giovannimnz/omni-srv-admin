# Git Worktree Fleet Closeout

## Objetivo

Consolidar checkouts Git distribuídos sem perder commits ou alterações locais:

- uma árvore canônica por repositório;
- `main` alinhada ao GitHub quando a branch existir;
- worktrees/refs locais dispensáveis removidos;
- heads únicas preservadas em branches `archive/` no GitHub;
- recuperação de storage comprovada.

Este procedimento não autoriza apagar branches remotas por padrão. Uma limpeza remota exige ordem explícita e revisão da política de retenção.

## 1. Inventário sem mutação

No host e repositório reais:

```bash
git fetch --all --prune
git status --short --branch
git worktree list --porcelain
git branch -vv --all
git stash list
git fsck --full --no-reflogs
df -h .
```

Para hosts ATIUS, registre o resultado da rota SSH privada e da rota pública. Não use uma falha da rota privada como prova de indisponibilidade.

## 2. Decisão para branches e árvores sujas

Classifique cada branch local fora de `main`:

| Estado | Ação |
| --- | --- |
| Contida em `main` | Pode remover localmente após soltar o worktree. |
| Atrás de `main` | Pode remover localmente. |
| Exclusiva/diferente | Revisar; fazer push da branch pretendida ou `archive/<host>-<data>` antes da poda. |
| Worktree sujo | Separar fonte de outputs; preservar código revisável antes de qualquer remoção. |

Não envie automaticamente bancos efêmeros, dados de navegador, logs, transcrições, diretórios `tmp/`, backups ou Graphify regenerado. Faça `git diff --check` e um scan de segredo na seleção staged antes do commit.

Ao manipular refs, use `refs/heads/<nome>` em vez de confiar em
`%(refname:short)`: nomes podem ficar ambíguos quando uma tag coincide com a
branch.

## 3. Atualização e poda segura

Depois que toda head única estiver preservada:

```bash
git switch main
git merge --ff-only origin/main
git worktree remove /caminho/do/worktree
git worktree prune -v
```

Se `git worktree remove` desregistrar a árvore mas sobrar um diretório físico,
valide primeiro que ele não aparece mais no registro e que `.git` não existe.
Somente então remova o caminho exato, sem cruzar mounts:

```bash
find /caminho/validado -xdev -depth -delete
```

Nunca aplique uma remoção recursiva no diretório pai de `~/GitHub`.

## 4. Storage e contenção de recursos

Após retirar referências desnecessárias, rode a compactação pelo wrapper do
host:

```bash
omni srv1-ops resources doctor --admission
omni srv1-ops resources run builds -- \
  bash -lc 'git -C /repo reflog expire --expire=now --all && git -C /repo gc --prune=now'
```

Se o `git repack` ficar bloqueado sem processo filho produtor, encerre apenas
a árvore de processos iniciada pelo closeout. Depois leia `git status` e faça
uma validação Git antes de tentar outra compactação.

## 5. Hooks e Graphify

Um `pre-commit` pode iniciar Graphify ou outra carga pesada. Isso não deve
ocorrer fora da quota do profile `builds`.

1. Interrompa apenas o hook/filhos iniciados pelo closeout.
2. Faça `git diff --cached --check` e o scan de segredo da seleção.
3. Para um commit de preservação, use `git commit --no-verify` somente após
   essas validações; não use isso para burlar gates de segurança específicos.
4. Rebuild Graphify em operação separada e contida, quando necessário.

## 6. GBrain e Obsidian via MCP HTTP Streamable

Hidrate o token efêmero do Vault:

```bash
source <("$HOME/.local/bin/atius-vault-env" atius-mcp)
```

Endpoints canônicos:

- `https://mcp.atius.com.br/gbrain`
- `https://mcp.atius.com.br/obsidian`

Use `Authorization: Bearer $ATIUS_MCP_TOKEN`; não persista ou imprima o
valor. O GBrain aceita operações stateless usuais. Para o Obsidian, a sequência
é obrigatória: `initialize` → guardar `Mcp-Session-Id` →
`notifications/initialized` → ferramenta (`vault_write`, `vault_append`,
etc.).

O registro mínimo deve conter: hosts/repositórios, SHA final, heads arquivadas,
bytes recuperados, mudanças excluídas por serem geradas, bloqueios e próximo
gate. Nunca registrar tokens, cookies, credenciais, PII ou payloads brutos.

## 7. Critério de encerramento

Em cada host e repositório alvo, capture:

```bash
git status --short --branch
git worktree list --porcelain
git branch -vv
df -h .
```

O encerramento exige `main` alinhada ao upstream, uma árvore canônica, heads
únicas preservadas/removidas de forma explícita e qualquer host inacessível
declarado com a rota e a causa observadas.
