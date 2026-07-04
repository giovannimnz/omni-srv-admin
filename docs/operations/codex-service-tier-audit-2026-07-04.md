# Codex service tier audit — 2026-07-04

## Objetivo

Garantir que a frota Codex use explicitamente `service_tier = "normal"`, que corresponde à velocidade **Padrão**, e não `priority`/rápido nem tiers ambíguos em configs ativas.

## Escopo verificado

Arquivos ativos `*.toml` sob os homes Codex abaixo, excluindo backups, cache, `.tmp` e sessões arquivadas:

- `GIOVANNI-W11-PC`: `C:\Users\muniz\.codex`
- `atius-srv-1`: `/home/ubuntu/.codex`
- `atius-srv-2`: `/home/ubuntu/.codex`
- `atius-srv-3`: `/home/ubuntu/.codex`
- `horistic-srv`: `/home/horistic/.codex`

## Resultado inicial

- `GIOVANNI-W11-PC` base config estava com `service_tier = "priority"` em `C:\Users\muniz\.codex\config.toml:13`.
- `atius-srv-1` base config estava com `service_tier = "default"` em `/home/ubuntu/.codex/config.toml:5`.
- `atius-srv-3` base config estava com `service_tier = "default"` em `/home/ubuntu/.codex/config.toml:5`.
- `atius-srv-2` e `horistic-srv` já estavam com `normal` no base config e perfis padrão.
- Alguns agents GSD em `GIOVANNI-W11-PC`, `atius-srv-1` e `atius-srv-2` estavam com `service_tier = "flex"`; como a política pedida é “sempre Padrão”, também foram normalizados para `normal`.

## Correções aplicadas

Todos os `service_tier` ativos encontrados foram normalizados para:

```toml
service_tier = "normal"
```

Backups criados antes das alterações:

- `C:\Users\muniz\.codex\config.toml.bak-service-tier-20260704-011414`
- `C:\Users\muniz\.codex\agents\*.toml.bak-service-tier-20260704-012812`
- `/home/ubuntu/.codex/config.toml.bak-service-tier-20260704-012418` em `atius-srv-1`
- `/home/ubuntu/.codex/config.toml.bak-service-tier-20260704-042421` em `atius-srv-3`
- `/home/ubuntu/.codex/agents/*.toml.bak-service-tier-20260704-012816` em `atius-srv-1`
- `/home/ubuntu/.codex/agents/*.toml.bak-service-tier-20260704-012839` em `atius-srv-2`

## Verificação final

Verificação final cross-host retornou `NON_NORMAL_COUNT = 0` para todos os arquivos ativos com `service_tier` no escopo.

Resumo por host:

| Host | Base config | Perfis quick/deep/frontier/xhigh-long | Agents GSD | Estado final |
| --- | --- | --- | --- | --- |
| `GIOVANNI-W11-PC` | `normal` | `normal` | `normal` | OK |
| `atius-srv-1` | `normal` | `normal` | `normal` | OK |
| `atius-srv-2` | `normal` | `normal` | `normal` | OK |
| `atius-srv-3` | `normal` | `normal` | sem agents GSD encontrados no escopo | OK |
| `horistic-srv` | `normal` | `normal` | sem agents GSD encontrados no escopo | OK |

## Omni Srv Admin

A política global foi registrada no DbOmniFleet via `omni-srv-admin` em `atius-srv-1`:

- `scope_type`: `global`
- `target_id`: `codex-service-tier`
- `canonical_product_id`: `codex-runtime`
- `lane`: `runtime-hook`
- `policy_type`: `runtime`
- `owner_module`: `modules/fleet`
- `entrypoint`: `docs/operations/codex-runtime-standard.md`
- `metadata.non_normal_count_after`: `0`

Comandos de controle local executados:

- `python3 -m omni fleet list`
- `python3 -m omni fleet validate-inventory`

A leitura local do registry DB no Windows exigiu `OMNI_FLEET_DB_ENV`, mas ficou bloqueada por ausência de `psql`/`pg8000`; o upsert foi feito no host canônico `atius-srv-1`, onde o registry estava operacional.

## Regra operacional

- `normal` = Padrão explícito e canônico.
- `priority` = rápido/prioritário, não usar como default.
- `default` = ambíguo para auditoria; normalizar para `normal`.
- `flex` = não é rápido, mas também não é Padrão; normalizar para `normal` quando a política é “sempre Padrão”.
