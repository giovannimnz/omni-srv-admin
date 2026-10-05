# SRV-1 GDrive backup offload recovery — 2026-09-04

## Resultado

O acúmulo de `/home/ubuntu/.backups` e `/home/ubuntu/backups` foi enviado aos
destinos correspondentes no Google Drive e removido localmente após gates de
upload/readback. A rotina passou a cobrir as duas roots, usar Vault/tmpfs,
serializar writers e falhar fechada antes de qualquer delete.

## Causa raiz

- o offload conhecia somente `.backups`; `omni backup create` gravava em
  `~/backups`, sem map/timer/destino;
- `retry_rclone` perdia o exit code real e enumerações sem permissão viravam
  `0/0`, criando falso verify;
- o service user não lia/removia backups root-owned;
- archives eram aceitos apenas por `size > 0`;
- `backup-srv1-daily` estava preso desde 2026-08-20, sem timeout;
- uma unit system-wide duplicada tentou remontar `~/GDrive` 75.868 vezes;
- o OAuth não estava expirado. O client público rclone, sem `client_id` próprio,
  atingiu quota global do projeto `202264815644`.

## Recuperação live

- mount system-wide duplicado parado e mascarado em runtime; mount user RO
  permaneceu ativo;
- backup diário travado e child rclone exato encerrados; timers voltaram a ter
  próximo trigger finito;
- seis itens foram drenados individualmente pelo novo fluxo rclone, com
  SHA-256/tamanho por `rclone cat` e manifest aceito;
- o restante foi consolidado por root e enviado pelo conector Google Drive,
  que usa outro client, porque o projeto OAuth público continuava saturado.

Bundles emergenciais:

| Root | Objeto | Bytes | SHA-256 local |
|---|---|---:|---|
| `.backups` | `_bulk/dotbackups-bulk-20260904T2105BRT-2568ec18f5fb7a6b62ec.tar.gz` | 130.739 | `34911c3fa4596ee46181677c46ba2f5b69afec1083fc6bb6127da559f1a9ae7a` |
| `backups` | `_bulk/backups-bulk-20260904T2105BRT-de341466afe327b5d8d2.tar.gz.part00..05` | 529.853.124 | archive completo `a8d9c5a6790ae894e37c4c92df8189c0f1fc322764c08c6ce897bff173217285` |

Os seis parts medem `94.371.840` bytes para `00..04` e `57.993.924` bytes
para `05`. O manifest remoto registra ordem, SHA-256 e MD5 por part. Todos os
nove objetos tiveram upload ACK, parent ID correto, bytes exatos e referência
de download emitida pelo Drive. Os fingerprints das duas roots foram idênticos
antes/depois da criação do bundle; somente então 17 + 36 itens foram removidos.

Limite honesto: o checksum metadata remoto dos bundles não pôde ser lido pelo
client rclone público durante a saturação. A prova usada no fallback foi ACK de
upload do conector + tamanho/parent por API + referência de download + hashes
locais nos manifests. Os itens processados diretamente pelo novo script tiveram
rehash remoto completo.

## Correções permanentes

- `offload-dotbackups-to-gdrive.sh`: duas roots allowlisted, archive streaming,
  source fingerprint, suporte root-owned, SHA-256/bytes por readback, manifest,
  delete exato, age gate e `_quarantine` para `.partial` antigo;
- auth Vault em tmpfs; cache persistente só por override explícito;
- lock comum `/tmp/rclone-fleet.lock`, pacing, retries limitados e timeouts;
- units em `omni-transfers.slice`, `TimeoutStartSec`, `KillMode=control-group` e
  timers sem `Requires=`;
- backup diário e fleet queue propagam exit codes reais e não rotacionam depois
  de cópia incompleta;
- installer/reconciler com rollback, testes negativos e skill Codex
  `atius-srv1-gdrive-backup-offload`.

## Estado final observado

- `/home/ubuntu/backups`: vazio;
- `/home/ubuntu/.backups`: drenado; qualquer backup novo respeita age gate;
- offload real vazio: `Result=success`, `ExecMainStatus=0`;
- timer backup: próximo trigger finito em 2026-09-05 ~04:17 BRT;
- timer offload: próximo trigger finito em 2026-09-05 ~05:39 BRT;
- mount user ativo, mount system-wide inativo, nenhum writer rclone órfão.

## Risco residual

Provisionar um OAuth client ATIUS próprio e atualizar
`kv/atius/fleet-backup/rclone/giovanni-drive#rclone_conf`. Reautorizar o mesmo
client público não resolve `rateLimitExceeded` global. Até essa migração, os
retries permanecem fail-closed: quota nunca autoriza delete.
