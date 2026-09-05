# Source map — XRDP ABNT2 migration

> [!WARNING]
> **Mapa de migração histórico/evidence-only.** Não execute os artefatos de
> origem listados abaixo. O fluxo atual é `$xrdp-abnt2-fleet`, com fonte em
> `modules/agent-content-packs/packs/codex-skills/items/xrdp-abnt2-fleet/SKILL.md`;
> as autoridades operacionais são `modules/xrdp-abnt2/README.md` e
> `docs/operations/ubuntu-arm64-xrdp-desktop-standard.md`. Comandos antigos com
> `DISPLAY=:10`, edição direta por `sed`/`tee`/`nano`, `xbindkeys`,
> `dpkg-reconfigure`, `pkill`, restart de `xrdp` ou instalação APT implícita
> não são o procedimento vigente. O mapeamento permanece como proveniência da
> migração original.

Canonical target:
- `/home/ubuntu/GitHub/omni-srv-admin/modules/xrdp-abnt2/`

Input sources:
- `/home/ubuntu/Documentos/Solucao-Teclado-Xrdp-Br/`
- `/home/ubuntu/xrdp-abnt2-update-guard/`

Backup before migration:
- `/home/ubuntu/.backups/xrdp-abnt2-omni-integration-20260606-000631/`

## File mapping

| Source | Canonical |
|---|---|
| `Solucao-Teclado-Xrdp-Br/configs/xrdp_keyboard.ini` | `files/xrdp_keyboard.ini` |
| `Solucao-Teclado-Xrdp-Br/configs/km-00000416.ini` | `files/km-abnt2.ini` |
| `Solucao-Teclado-Xrdp-Br/configs/startwm.sh` | `files/startwm.sh` |
| `Solucao-Teclado-Xrdp-Br/configs/99xrdp-abnt2-keyboard` | `files/99xrdp-abnt2-keyboard` |
| `Solucao-Teclado-Xrdp-Br/scripts/fix-xrdp-abnt2-keyboard` | `files/fix-xrdp-abnt2-keyboard` |
| `Solucao-Teclado-Xrdp-Br/scripts/setxkbmap-abnt2.sh` | `files/setxkbmap-abnt2.sh` |
| `Solucao-Teclado-Xrdp-Br/README.md` | `docs/original-readme.md` |
| `Solucao-Teclado-Xrdp-Br/SOLUCAO-PASSO-A-PASSO.md` | `docs/original-runbook.md` |
| `Solucao-Teclado-Xrdp-Br/TRANSCRICAO-DA-CONVERSA.md` | `docs/original-transcript.md` |

## Validation

`/home/ubuntu/xrdp-abnt2-update-guard/*` was byte-compared against `modules/xrdp-abnt2/files/*` after copy:

- `xrdp_keyboard.ini`: match
- `km-abnt2.ini`: match
- `startwm.sh`: match
- `fix-xrdp-abnt2-keyboard`: match
- `99xrdp-abnt2-keyboard`: match

Legacy source dirs were preserved after backup. Canonical maintenance target is now the Omni module.
