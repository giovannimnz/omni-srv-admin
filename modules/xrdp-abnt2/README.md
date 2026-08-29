# XRDP ABNT2 Guard

Funcionalidade do `omni-srv-admin` para manter o host Ubuntu/XRDP fixo em `br(abnt2)` no fluxo:

```text
Windows 11 Microsoft Remote Desktop -> Ubuntu 24.04+ + XRDP + LXDE
```

## Lógica

O bug operacional é uma cadeia de fallback e tradução:

1. Windows RDP envia `keylayout` que o XRDP local nem sempre mapeia (`0x00010416`, `0x0000F010` e, quando o cliente cai em Latin America, `0x0000080A`).
2. Quando o XRDP não acha o keymap, cai em `/etc/xrdp/km-00000409.ini` (US).
3. A sessão X11 pode ainda ser alterada por autodetecção do cliente ou GUI tools.
4. Updates do pacote `xrdp` podem restaurar conffiles e desfazer a correção.
5. No XRDP `0.9.24`, `lang.c` traduz scancodes estendidos para índices
   `xfree86/base`, enquanto o XKB live usa `evdev`. Um keymap validado pelos
   índices live errados faz `Delete` virar `Print Screen` e quebra as setas.

O guard fecha as 4 camadas:

| Camada | Arquivo | Função |
|---|---|---|
| Sistema | `/etc/default/keyboard` | Esperado `br` + `abnt2` |
| XRDP map | `/etc/xrdp/xrdp_keyboard.ini` | `00010416`, `0000F010`, `0000080A`, `00000409` -> `br(abnt2)` |
| XRDP keymaps | `/etc/xrdp/km-*.ini` | US fallback e BR alternativos usam keymap ABNT2 idêntico, gerado por `xrdp-genkeymap` contra `evdev` e indexado para o tradutor `xfree86/base` do XRDP 0.9.24 |
| Sessão | `/etc/xrdp/startwm.sh` + `~/.local/bin/setxkbmap-abnt2.sh` | Aplica ABNT2 no login e corrige drift a cada 5s |
| Update guard | `/etc/apt/apt.conf.d/99xrdp-abnt2-keyboard` | Reaplica após `apt/dpkg` |
| Drift guard | `xrdp-abnt2-reconcile.timer` | Reaplica os assets a cada hora e após boot, sem reiniciar XRDP |

## Fleet contract

Este módulo é o patch persistente canônico do `omni-srv-admin` para o desktop
XRDP da fleet Ubuntu ARM64. Ele deve estar listado em `inventory/hosts/*.yaml`
de cada host que expõe LXDE/XRDP humano.

Regra de baseline:

- sempre que um servidor remoto novo for Ubuntu 24.04+ e precisar de desktop
  humano via XRDP, ele entra no padrão com `platform.desktop: lxde-xrdp` e
  `modules: [xrdp-abnt2]`
- não tratar isso como hotfix manual por host; tratar como patch persistente de
  fleet

Hosts alvo atuais:

- `atius-srv-1`
- `atius-srv-2`
- `atius-srv-3`
- `horistic-srv`

## Pacotes garantidos

`omni xrdp-abnt2 install --yes` garante os pré-requisitos do patch antes de
reaplicar os assets:

- `xrdp`
- `xorgxrdp`
- `tigervnc-common`
- `tigervnc-standalone-server`
- `tigervnc-tools`
- `dbus-x11`
- `freerdp2-x11`
- `lxde`
- `lxhotkey-plugin-openbox`

Nota operacional:

- `freerdp2-x11` faz parte do padrão para que qualquer host da fleet consiga
  executar smoke local/peer-to-peer via `xfreerdp`, não apenas o `srv1`.

## Comandos

```bash
omni xrdp-abnt2 status
omni xrdp-abnt2 validate
omni xrdp-abnt2 diff
sudo omni xrdp-abnt2 install --yes
```

## Assets canônicos

```text
modules/xrdp-abnt2/files/
  xrdp_keyboard.ini
  km-abnt2.ini
  startwm.sh
  setxkbmap-abnt2.sh
  fix-xrdp-abnt2-keyboard
  99xrdp-abnt2-keyboard
```

## Instalação

`install` sempre cria backup antes de sobrescrever:

```text
~/.backups/xrdp-abnt2-YYYYmmdd-HHMMSS/
```

Depois instala:

```text
/usr/local/share/xrdp-abnt2/xrdp_keyboard.ini
/usr/local/share/xrdp-abnt2/km-abnt2.ini
/usr/local/share/xrdp-abnt2/startwm.sh
/usr/local/sbin/fix-xrdp-abnt2-keyboard
/etc/apt/apt.conf.d/99xrdp-abnt2-keyboard
/etc/systemd/system/xrdp-abnt2-reconcile.service
/etc/systemd/system/xrdp-abnt2-reconcile.timer
/home/<user>/.local/bin/setxkbmap-abnt2.sh
/etc/xrdp/xrdp_keyboard.ini
/etc/xrdp/km-00000409.ini
/etc/xrdp/km-00010416.ini
/etc/xrdp/km-0000080a.ini
/etc/xrdp/km-0000f010.ini
/etc/xrdp/startwm.sh
```

Também normaliza line endings dos assets textuais para `LF` durante a
instalação, mesmo que o checkout local tenha vindo com `CRLF`.

Não reinicia `xrdp` automaticamente. O comando só garante:

- pacotes
- arquivos canônicos
- helper persistente em `/usr/local/sbin`
- payload persistente em `/usr/local/share/xrdp-abnt2`
- hook APT/DPKG
- `xrdp-abnt2-reconcile.timer` ativo: ele chama apenas o reparador de arquivos,
  nunca `restart xrdp` ou `restart xrdp-sesman`
  e aplica jitter de até 15 minutos. Se detectar arquivo XRDP divergente, o
  reparador salva uma cópia prévia em `/var/backups/xrdp-abnt2-reconcile/` e
  mantém no máximo 8 snapshots antes de reconciliar.
- `systemctl enable xrdp xrdp-sesman`

Reconecta via RDP para validar nova sessão.

## Validação manual

```bash
omni xrdp-abnt2 validate
setxkbmap -query
```

Critérios:

- Pacotes padrão do desktop XRDP (`xrdp`, `tigervnc`, `dbus-x11`,
  `freerdp2-x11`, `lxde`, `lxhotkey-plugin-openbox`) estão presentes.
- `dbus-launch`, `Xvnc`, `startlxde` e `xfreerdp` existem no PATH.
- `xrdp` e `xrdp-sesman` estão `enabled` e `active`.
- Assets canônicos e arquivos live estão em `LF`.
- `xrdp_keyboard.ini` contém `00010416`, `0000F010`, `0000080A`, `rdp_layout_us=br(abnt2)` e `rdp_layout_latam=br(abnt2)`.
- `km-00000409`, `km-00010416`, `km-0000080a`, `km-0000f010` têm o mesmo hash do `km-abnt2.ini` canônico.
- `km-00000416`, usado pelo cliente Windows PT-BR atual, também é gerido e tem o mesmo hash.
- O keymap tem 8 estados de modificadores e usa os índices efetivamente
  consumidos pelo XRDP 0.9.24: `Up=Key98`, `Left=Key100`, `Right=Key102`,
  `Down=Key104`, `Delete=Key107`, `Print=Key111`.
- A tecla física ABNT_C1 usa `Key123`: `/`, `?`, `°`, `¿` conforme o modificador.
- `[Globals]` em `/etc/xrdp/xrdp.ini` força `keyboard_type=0x04`,
  `keyboard_subtype=0x00` e `keylayout=0x00000416`, neutralizando clientes que
  anunciem incorretamente teclado Japanese `0x07`.
- Hook APT aponta para `/usr/local/sbin/fix-xrdp-abnt2-keyboard`.
- Helper do usuário existe em `~/.local/bin/setxkbmap-abnt2.sh`.
