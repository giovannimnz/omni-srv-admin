# Phase 59 — Pre-Execution Autopilot Bootstrap

Este bootstrap ocorre **depois** da convergência/commit final dos planos e **antes** de qualquer chamada a `gsd-execute-autopilot`. Ele não pertence à Wave 0, não produz evidência de Wave 0 e não pode editar plano, source, config ou doctor para fabricar readiness.

## Inputs obrigatórios

- `59-PLAN-BUNDLE.json`, gerado após o planejamento final e fora do worktree de execução, com `schema_version`, `phase=59`, `workstream=qwen-local-ai`, `final_execution_commit`, repo remote/base esperados e uma entrada `{path, sha256}` única para cada arquivo assinado;
- o `final_execution_commit` registrado no bundle, nunca um hash fixado neste documento;
- os nove paths `59-01-PLAN.md` até `59-09-PLAN.md`;
- SHA-256 de cada PLAN, `59-CONTEXT.md`, `59-RESEARCH.md`,
  `59-PATTERNS.md`, `59-VALIDATION.md`, `59-REVIEWS.md` e deste bootstrap,
  calculado a partir de `git show FINAL_COMMIT:PATH`;
- repo remoto e branch dedicada esperada, por exemplo `phase59-qwen-cutover`; `main`/`master` são proibidas;
- path dedicado srv1 `/home/ubuntu/GitHub/worktrees/omni-srv-admin-phase59`;
- path externo do bundle no srv1 `/home/ubuntu/.local/state/gsd/phase59/59-PLAN-BUNDLE.json`.

O bundle não é sua própria fonte de hash: ele é gerado depois de
`final_execution_commit`, assina arquivos lidos desse commit e fica fora do
worktree dedicado. `repo_remote` e `repo_branch` devem resolver por
`git ls-remote` exatamente para esse commit; commit apenas local não passa.
Campos ausentes, path duplicado, hash não SHA-256, remote/ref divergente,
arquivo ausente ou conteúdo divergente bloqueiam.

`PROJECT.md`, `REQUIREMENTS.md`, `ROADMAP.md` e `STATE.md` não entram na lista
imutável porque o GSD os atualiza durante closeout. Suas mudanças são validadas
pelos schemas/gates de transição; os PLANs e contratos da Phase59 permanecem
byte-imutáveis.

## Helper versionado

O contrato executável é `scripts/embeddings-bench/phase59-autopilot-bootstrap.py`.
Ele gera/verifica o bundle com conteúdo lido por `git show`, prepara ou valida o
worktree dedicado sem alterar o checkout owner, executa o refresh/doctor
Graphify no profile `builds` em um segundo worktree detached de verificação e
emite um receipt externo. O helper não invoca skills Codex.

Depois do commit final, no coordenador:

```bash
python3 scripts/embeddings-bench/phase59-autopilot-bootstrap.py bundle \
  --repo /caminho/absoluto/omni-srv-admin \
  --commit FINAL_EXECUTION_COMMIT \
  --output /caminho/externo/59-PLAN-BUNDLE.json \
  --remote ORIGIN_URL --branch BRANCH
```

## Localização verificada da skill

Readback de 2026-07-24, sem copiar ou instalar nada:

- `atius-srv-1`: `gsd-execute-autopilot/SKILL.md` presente, SHA-256
  `349ef8fe3b24095c232660c15cb0d2a3ccc81868b846446bb1883aa9b6483dd4`;
  `gsd-autonomous` também presente.
- `atius-srv-2`: `gsd-execute-autopilot` ausente; `gsd-autonomous` presente.
- `atius-srv-3`: ambas ausentes.

Portanto o executor canônico da Phase 59 é exclusivamente o `atius-srv-1`.
Ausência nos outros hosts não autoriza replicar a skill durante esta fase; o
hash live do srv1 deve ser novamente ligado ao receipt do doctor.

No `atius-srv-1`, após instalar o bundle no path externo:

```bash
python3 scripts/embeddings-bench/phase59-autopilot-bootstrap.py doctor \
  --bundle /home/ubuntu/.local/state/gsd/phase59/59-PLAN-BUNDLE.json \
  --executor-mode autopilot \
  --executor-owner CODEX_TASK_ID
```

Antes de cada task e depois de cada commit de execução:

```bash
python3 scripts/embeddings-bench/phase59-autopilot-bootstrap.py verify-runtime \
  --bundle /home/ubuntu/.local/state/gsd/phase59/59-PLAN-BUNDLE.json \
  --bootstrap-receipt /home/ubuntu/.local/state/gsd/phase59/59-AUTOPILOT-BOOTSTRAP-RECEIPT.json \
  --executor-owner CODEX_TASK_ID
```

## Sequência fail-closed

1. No coordenador, gere `59-PLAN-BUNDLE.json` somente depois do commit final destinado à execução. Derive todos os hashes com `git show "$FINAL_EXECUTION_COMMIT:$PATH"`; não use arquivos do worktree dirty.
2. Copie o bundle para o path externo srv1 e valide sua integridade antes de criar/reusar worktree.
3. Inspecione `/home/ubuntu/GitHub/omni-srv-admin` apenas como git common-dir/objeto de origem. Não execute `switch`, `checkout`, `reset`, `clean`, `stash`, stage ou edição nesse checkout, mesmo que pareça limpo.
4. Exija uma branch remota dedicada à Phase 59, diferente de `main`/`master`, apontando exatamente para `final_execution_commit`. Crie o worktree dedicado nessa branch. Se o path já existir, exija: path absoluto, realpath idêntico, registro em `git worktree list --porcelain`, branch exata, HEAD base exato, nenhum symlink, nenhum arquivo dirty/untracked e nenhum processo de outra fase. Qualquer divergência bloqueia; não remova nem repare automaticamente.
5. Dentro do worktree dedicado, prove com `git ls-tree -r --name-only HEAD` que os nove PLANs estão visíveis. Recalcule cada hash com conteúdo do tree e compare byte a byte ao bundle. O commit histórico anteriormente questionado continha os nove PLANs, conforme `git ls-tree`; ele é apenas evidência histórica e nunca substitui `final_execution_commit` ou os hashes do bundle atual.
6. Antes do início, crie atomicamente
   `/home/ubuntu/.local/state/gsd/phase59/59-EXECUTOR-LOCK.json`, ligado ao
   bundle/base, `executor_mode` e `executor_owner` (ID do task Codex). Reuso só
   é aceito com conteúdo byte-idêntico; outro owner ou modo bloqueia. Verifique
   status limpo e HEAD igual à base. Depois, commits são permitidos somente como
   descendentes na mesma branch, com todos os paths assinados byte-idênticos.
   Antes de cada task execute `verify-runtime` com bundle, receipt e owner; ele
   exige lock exclusivo, ancestry, branch/worktree, boundary limpo e hashes
   assinados no HEAD corrente.
7. Crie/reuse o segundo worktree detached `/home/ubuntu/GitHub/worktrees/omni-srv-admin-phase59-bootstrap-graphify-SHA12`, no exato `final_execution_commit`, e execute ali `/home/ubuntu/.local/bin/graphify update .` sob o doctor/profile `builds`. Somente `graphify-out/**` e `.planning/graphs/**` podem mudar nesse worktree; o worktree de execução deve continuar limpo. Parseie `graphify status` exigindo `stale=false`, `commit_stale=false` e commit exato. Query vazia estruturalmente válida registra `query_route=focused_reads_required`; nunca fabrique nós.
8. Abra o task Codex dono do lock com root exato do worktree. Invoque
   `$gsd-execute-autopilot --doctor --ws qwen-local-ai` e faça seu doctor rodar
   um fixture descartável que prova: parser aceita `--resume`; resume da fase
   parcial usa o mesmo owner/root; completion cria Summary; reclassificação
   despacha o próximo plan uma única vez. Salve um transcript JSON externo e
   imutável com suite versionada, root/bundle/base/owner/lock, SHA-256 do
   `SKILL.md` e `execute-autopilot.md`, e exatamente dois resultados reais:
   `resume-existing-original-uid` preservando UID, `redispatch_count=0` e um
   handoff; `summary-then-dispatch-next-plan` criando Summary e um único
   dispatch. Cada check inclui exit code zero e hashes de argv/stdout. O JSON
   do doctor referencia path absoluto externo e SHA-256 desse transcript, além
   de `resume_capability=true`; booleans autodeclarados de fixture são
   rejeitados. `combine-skill-doctor` recalcula hashes locais/transcript e
   valida todo o resultado ligado ao owner lock. Skill ausente, Graphify stale,
   owner divergente, transcript adulterado ou fixture falho encerra o bootstrap.
9. Execute `phase59-autopilot-bootstrap.py combine-skill-doctor` com o receipt do bootstrap e o JSON do doctor. Ele produz `59-AUTOPILOT-COMBINED-RECEIPT.json`, ligando hashes, root e commit. Somente com esse receipt combinado PASS, no mesmo task/root, invoque `$gsd-execute-autopilot --only 59 --ws qwen-local-ai`. Não trate a skill como binário ou comando shell.

## Fallback autorizado

Se o doctor do autopilot continuar bloqueado, não execute autopilot e não
marque Wave 0 iniciada. O doctor deve primeiro gravar um receipt externo
`FAIL`/`BLOCK`, ligado ao mesmo root, bundle, base, owner e hashes exatos da
skill/workflow, com `wave0_started=false`. Então execute:

```bash
python3 scripts/embeddings-bench/phase59-autopilot-bootstrap.py \
  transition-fallback \
  --bundle /home/ubuntu/.local/state/gsd/phase59/59-PLAN-BUNDLE.json \
  --bootstrap-receipt /home/ubuntu/.local/state/gsd/phase59/59-AUTOPILOT-BOOTSTRAP-RECEIPT.json \
  --skill-doctor-failure /home/ubuntu/.local/state/gsd/phase59/59-AUTOPILOT-DOCTOR-FAIL.json \
  --executor-owner CODEX_TASK_ID
```

O helper aceita essa transição somente se o worktree ainda estiver limpo no
commit base, não existirem Gate 0, `59-01-SUMMARY.md` ou receipt combinado, e o
lock autopilot ainda for byte/hash-idêntico ao receipt original. Ele substitui
atomicamente o lock pelo modo `execute-phase-fallback` e emite um novo
`59-FALLBACK-BOOTSTRAP-RECEIPT.json`; falha intermediária deixa a execução
bloqueada. Só então, no mesmo task/root, use
`$gsd-execute-phase 59 --ws qwen-local-ai`.

Esse fallback consome os mesmos PLANs/gates e o mesmo receipt. Não é autorizado
executá-lo do WSL, do checkout owner ou de outro worktree.

O receipt exigido pelo fallback é o novo `BOOTSTRAP_PASS` ligado ao hash do
lock autopilot supersedido e ao receipt de falha. O receipt combinado é
proibido no fallback. Também é permitido escolher fallback diretamente antes
de qualquer lock, executando `doctor --executor-mode execute-phase-fallback`;
o caminho de transição acima é obrigatório quando o lock autopilot já existe.
Os modos permanecem mutuamente exclusivos e nunca mudam após o início da
Wave 0.
