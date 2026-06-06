# XRDP ABNT2 Guard

Funcionalidade do `omni-srv-admin` para manter o host Ubuntu/XRDP fixo em `br(abnt2)` no fluxo:

```text
Windows 11 Microsoft Remote Desktop -> Ubuntu 22.04 + XRDP + LXDE
```

## Lógica

O bug operacional é uma cadeia de fallback:

1. Windows RDP envia `keylayout` que o XRDP local nem sempre mapeia (`0x00010416` e `0x0000F010`).
2. Quando o XRDP não acha o keymap, cai em `/etc/xrdp/km-00000409.ini` (US).
3. A sessão X11 pode ainda ser alterada por autodetecção do cliente ou GUI tools.
4. Updates do pacote `xrdp` podem restaurar conffiles e desfazer a correção.

O guard fecha as 4 camadas:

| Camada | Arquivo | Função |
|---|---|---|
| Sistema | `/etc/default/keyboard` | Esperado `br` + `abnt2` |
| XRDP map | `/etc/xrdp/xrdp_keyboard.ini` | `00010416`, `0000F010`, `00000409` -> `br(abnt2)` |
| XRDP keymaps | `/etc/xrdp/km-*.ini` | US fallback e BR alternativos usam keymap ABNT2 idêntico |
| Sessão | `/etc/xrdp/startwm.sh` + `~/bin/setxkbmap-abnt2.sh` | Aplica ABNT2 no login e corrige drift a cada 5s |
| Update guard | `/etc/apt/apt.conf.d/99xrdp-abnt2-keyboard` | Reaplica após `apt/dpkg` |

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
/home/<user>/bin/setxkbmap-abnt2.sh
/etc/xrdp/xrdp_keyboard.ini
/etc/xrdp/km-00000409.ini
/etc/xrdp/km-00010416.ini
/etc/xrdp/km-0000f010.ini
/etc/xrdp/startwm.sh
```

Não reinicia `xrdp` automaticamente. Reconecta via RDP para validar nova sessão.

## Validação manual

```bash
omni xrdp-abnt2 validate
setxkbmap -query
```

Critérios:

- `xrdp_keyboard.ini` contém `00010416`, `0000F010`, `rdp_layout_us=br(abnt2)`.
- `km-00000409`, `km-00010416`, `km-0000f010` têm o mesmo hash do `km-abnt2.ini` canônico.
- Hook APT aponta para `/usr/local/sbin/fix-xrdp-abnt2-keyboard`.
- Helper do usuário existe em `~/bin/setxkbmap-abnt2.sh`.
