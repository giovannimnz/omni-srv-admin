# Seal complementar — Apache source/live SSO

Veredito: `PASS_SUBSET`.

Este pack complementa, sem substituir, o fleet integral `2026-07-31-destination-hostname-lifecycle-20260731-213807`.

## Correção

- Configurações live aprovadas promovidas para `sites-available`.
- Cinco cópias standalone em `sites-enabled` substituídas por symlinks padrão.
- Vhosts versionados nos repos donos.
- Checkers anti-drift read-only adicionados.
- Apache validado com `apache2ctl -t` e recarregado com graceful reload.

## Gates

- Source versionada ↔ `sites-available`: `5/5` byte-exact.
- `sites-enabled`: `5/5` symlinks.
- `sites-available` ↔ config habilitada: `5/5` byte-exact.
- HTTP app-local: PASS nos quatro hosts.
- Lifecycle: `4/4` sites, `8/8` ciclos, `32/32` screenshots.
- Auth cookie emitido e removido: `8/8`.
- Logout por controle visível: `8/8`.
- Foreign visible origin: `0`.
- Revisão visual independente: `4/4 PASS`.
- Secrets gravados: não.

## Escopo

`completeFleetEvidence=false` e `centralOidcFlow=false` são intencionais. O pack prova apenas a revalidação pós-reload de Grafana, Portainer, Docker e VPN.

## Graphify

- Omni: rebuild inicial `12.637/18.690`; settle após o closeout documental
  `12.638/18.691`, fresh/current. O delta `+1/+1` é o heading
  `Ownership Apache e gate anti-drift` indexado; query do heading `11/10`.
  As duas units governadas terminaram success/status `0`, swap novo `0B`.
- VPN: `16.457` nodes, `19.069` edges, query `verify-apache-drift` `2/1`; unit governada success/status `0`, swap novo `0B`.
- Vault: os rebuilds intermediários `37.690/63.341` e `37.698/63.349`
  continham autoreferência de `.planning/graphs/GRAPH_REPORT.md`.
  `.graphifyignore` passou a preservar todas as exclusões anteriores e a
  excluir `.planning/graphs/` e `graphify-out/` do corpus.
- O rebuild clean removeu exatamente `2.010` nodes, todos derivados do próprio
  report; `0` nodes reais foram removidos. Autoridade final: `35.688/61.340`,
  `17.904` arquivos reais detectados, `0` artifacts derivados detectados e `0`
  nodes derivados no grafo.
- Rebuild normal pós-cleanup retornou `No code-graph topology changes detected`,
  manteve hashes published/output iguais e preservou a query
  `Drift Apache SSO eliminado` em `28/27`. Units success/status `0`, swap novo
  `0B`.
- Os três grafos estão fresh/current e sem arquivos non-`ubuntu`.

## Backups

- Runtime Apache: `/home/ubuntu/backups/atius-sso-apache-source-live-drift-pre-20260731-221646`.
- Owner files: `/home/ubuntu/backups/atius-sso-apache-owner-files-pre-20260731-222116`.
- Docs: `/home/ubuntu/backups/atius-sso-apache-drift-closeout-docs-pre-20260731-222756`.

Nenhum commit ou push foi executado.
