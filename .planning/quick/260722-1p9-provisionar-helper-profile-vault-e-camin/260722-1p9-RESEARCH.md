# Quick 260722-1p9 Research

## Outcome

Preparar o `horistic-srv` para o full gate da Phase 52 sem criar valores
secretos: corrigir readiness para o usuário remoto real, instalar um caminho
gerenciado de Backup B state-only/copy-only e repetir o gate fail-closed.

## Live facts

- O alias `horistic-srv-1` autentica como `horistic`; não existe usuário
  `ubuntu` no host.
- `/home/horistic/.local/bin/atius-vault-env` já existe, é executável, usa
  `ssh -n` e passou smoke sem exposição de valor.
- `validate_phase52.py` fixa `/home/ubuntu` no probe remoto, gerando o falso
  blocker `vault-export-helper-missing`.
- `rclone`, a config rclone e `modules/fleet-backup` não estão instalados no
  Horistic; `omni-builds.slice` está ativo com quota de CPU de 20%.
- Os seis paths Vault RustDesk aprovados existem apenas como contrato: o check
  metadata-only confirmou que todos ainda estão ausentes. A autorização deste
  task não amplia a aprovação anterior de paths sem valores.
- O exporter genérico não implementa o protocolo JSON exato de sete refs do
  `RUSTDESK_VAULT_PROVIDER`.
- O Backup B atual apenas recebe o rótulo GDrive; não faz upload nem rehash
  remoto. O módulo fleet-backup existente cobre `~/docker`, executa rotação e
  não é adequado para retenção Phase 57 PASS + 30 dias.
- Um probe de pesquisa criou por engano somente
  `/home/horistic/.cache/nonexistent-path` (regular, 43 bytes). A correção deve
  remover exatamente esse arquivo depois de revalidar metadata.

## Design boundaries

- Derivar home remoto dinamicamente e exigir o provider dedicado, sem duplicar
  o helper genérico em `/home/ubuntu`.
- Versionar provider/install/rollback; aceitar exatamente as sete refs
  aprovadas; nenhum valor em argv, arquivo persistente, log ou evidência.
- Criar Backup B state-only com `rclone copyto` e rehash via `rclone cat`,
  `transfers=1`, `checkers=1`, destino allowlisted e nenhum `delete`, `purge`,
  `move`, `sync`, rotação ou timer.
- Config rclone deve ser hidratada em tmpfs e removida por trap. O segredo da
  config permanece Vault-authoritative e também não será criado nesta rodada.
- srv2/srv3 são estritamente read-only; qualquer capacidade PASS inesperada
  interrompe a cadeia antes de writes.
- Horistic só recebe writes delimitados já autorizados. O gate continua
  BLOCKED se os valores RustDesk ou rclone estiverem ausentes.
- Backups e objetos parciais remotos nunca são apagados sem nova aprovação.

## Verification

- Testes negativos e positivos focados sob o profile `builds` (20% CPU).
- `bash -n` nos scripts; testes de allowlist, home dinâmico, ausência de verbos
  destrutivos, hash remoto e retenção.
- Dry-run do instalador antes do apply; timer amplo deve permanecer ausente.
- Full gate serial com evidência corrente; promoção só se todos os stages forem
  PASS. Caso contrário, persistir blockers exatos sem promover Phase 53.
