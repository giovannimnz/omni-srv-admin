---
type: gate-closure
date: 2026-06-16
phase: 18
milestone: M007-ext
gate: XRDP humano SRV-1/SRV-2/SRV-3
status: closed
---

# XRDP Fleet Closure — 2026-06-16

> [!WARNING]
> **Registro histórico/evidence-only, não um runbook operacional atual.** Para
> teclado XRDP ABNT2 na frota, use `$xrdp-abnt2-fleet` e consulte
> `modules/agent-content-packs/packs/codex-skills/items/xrdp-abnt2-fleet/SKILL.md`,
> `modules/xrdp-abnt2/README.md` e
> `docs/operations/ubuntu-arm64-xrdp-desktop-standard.md`. Comandos antigos com
> `DISPLAY=:10`, edição direta por `sed`/`tee`/`nano`, `xbindkeys`,
> `dpkg-reconfigure`, `pkill`, restart de `xrdp` ou instalação APT implícita
> não são o fluxo vigente. A closure abaixo é preservada como evidência datada
> de 2026-06-16.

Closes the XRDP adjustment track inside Phase 18.

## Final operator validation

1. `ATIUS-SRV-1` — Microsoft RDP OK
2. `ATIUS-SRV-2` — Microsoft RDP OK
3. `ATIUS-SRV-3` — Microsoft RDP OK

## Final rule

- `:1..14` = XRDP humano
- Resolution in `:1..14` comes from the RDP client
- `:15..30` = headless/Camofox/noVNC
- Fixed `1366x768` belongs only to the headless range
- `:31..60` = legacy/overflow only

## Live config basis

- `X11DisplayOffset=1`
- `lib=libvnc.so`
- `port=-1`
- `code=0`
- `delay_ms=6000`
- `Xvnc -SecurityTypes None -Protocol3.3`
- `-rfbunixpath /run/xrdp/sockdir/xrdp_display_1`
- LXDE `startwm.sh` without `1366x768` watcher

## Notes

- SRV-2 `xvfb.service` on `:1` was disabled because it blocked XRDP humano
- Camofox fixed-resolution behavior stays separate from XRDP humano
- Remaining Phase 18 scope is no longer XRDP
