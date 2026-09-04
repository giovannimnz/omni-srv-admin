# Dark Theme Ubuntu para LXDE/XRDP

Tema operacional para o desktop remoto dos servidores Ubuntu 24.04 ARM64 gerenciados por `omni-srv-admin` com LXDE + XRDP.

## Proposta

- Desktop remoto escuro, legível e estável em RDP.
- Openbox `Dark-Onyx` para bordas/janelas.
- GTK2/GTK3 com `Greybird-dark`, sem CSS legado quebrando parsing.
- GSettings/portal com `color-scheme=prefer-dark`, para apps em `System` abrirem em dark automaticamente.
- Env persistente em `.xsessionrc`, `.profile` e `~/.config/environment.d/10-omni-dark.conf`.
- Fontes SF/New York/Tahoma instaladas em `/usr/local/share/fonts/apple`.
- Indicador `Omni Network` no tray, com icone dark custom, substituindo `nm-applet` quando NetworkManager marca OCI/WireGuard como `unmanaged`.
- Mini monitor de CPU no `status-right`, na mesma posicao usada nos SRV-2/SRV-3: antes do idioma do teclado.
- Painel LXDE dividido em tres arquivos:
  - `00-background`: fundo full-width da barra inferior e reserva da area de trabalho.
  - `panel`: menu, launchers, pager e taskbar à esquerda.
  - `status-right`: ABNT2, tray, volume, relógio, lock/logout à direita.
- Guard de ABNT2 e guard de geometria do painel no autostart.
- Backup antes de qualquer alteração em `~/.backups/omni-dark-theme/`.

## Comandos

```bash
cd /home/ubuntu/GitHub/omni-srv-admin/dark-theme-ubuntu

./scripts/dark-themectl.sh status
./scripts/dark-themectl.sh validate
./scripts/dark-themectl.sh repair --install-packages --restart-session
./scripts/dark-themectl.sh apply --install-packages --with-sublime --with-zsh --restart-session
./scripts/dark-themectl.sh restore-latest --restart-session
```

Wrappers:

```bash
./install.sh    # apply completo
./repair.sh     # repair seguro para LXDE/XRDP
./uninstall.sh  # restore do ultimo backup
```

Para rollout em fleet, use `repair --install-packages --restart-session` como padrao. Reserve `apply --with-sublime --with-zsh` para hosts que precisam dessas opcoes explicitamente.

Runbook canonico: `docs/operations/ubuntu-arm64-xrdp-desktop-standard.md`.

O guard de sessão `setxkbmap` deste tema não substitui os keymaps e o
reconciliador XRDP. Para teclado ABNT2 em fleet, use `$xrdp-abnt2-fleet`,
versionada em
`modules/agent-content-packs/packs/codex-skills/items/xrdp-abnt2-fleet/SKILL.md`.

## Arquivos Aplicados

```text
~/.gtkrc-2.0
~/.config/gtk-3.0/settings.ini
~/.config/gtk-3.0/gtk.css
~/.config/environment.d/10-omni-dark.conf
~/.config/xdg-desktop-portal/lxde-portals.conf
~/.config/autostart/nm-applet.desktop
~/.config/lxsession/LXDE/desktop.conf
~/.config/lxsession/LXDE/autostart
~/.config/lxpanel/LXDE/panel-background.xpm
~/.config/lxpanel/LXDE/panels/00-background
~/.config/lxpanel/LXDE/panels/panel
~/.config/lxpanel/LXDE/panels/status-right
~/.config/openbox/lxde-rc.xml
~/.config/pcmanfm/LXDE/desktop-items-0.conf
~/.xsessionrc
~/.local/bin/setxkbmap-abnt2.sh
~/.local/bin/omni-dark-system-env.sh
~/.local/bin/omni-network-tray.py
~/.local/bin/omni-lxde-panel-guard.sh
~/.local/share/icons/omni-dark-theme/omni-network-ok.svg
~/.local/share/icons/omni-dark-theme/omni-network-wired.svg
~/.local/share/icons/omni-dark-theme/omni-network-error.svg
```

## Observacoes do Ubuntu 24.04

- `volumealsa` nao existe neste host; usar `volume`.
- Arquivos `panel.bak*` dentro de `~/.config/lxpanel/LXDE/panels/` viram painéis reais e bugam a barra. O controller move esses arquivos para backup.
- `lxpanelctl restart` pode deixar estado velho; o controller usa `pkill + setsid -f lxpanel`.
- O painel direito separado evita o clipping do tray no XRDP.
- O `00-background` existe porque no XRDP/Ubuntu 24.04 o LXPanel pode calcular a largura natural do painel funcional como menor que a tela, deixando um vao preto no meio da barra.
- O fundo da barra usa `panel-background.xpm` para vencer o fundo claro/cinza do tema GTK2 do LXPanel.
- Apps modernos que usam `System` devem enxergar dark via GSettings e portal: `org.gnome.desktop.interface color-scheme='prefer-dark'` e portal `org.freedesktop.appearance color-scheme=1`.
- `nm-applet` nao representa `enp0s6`/`wg0` neste fleet porque as interfaces aparecem como `unmanaged`; o dark theme remove esse applet do autostart LXDE, cria override XDG `Hidden=true` em `~/.config/autostart/nm-applet.desktop` e usa `omni-network-tray.py`.
- `omni-network-tray.py` detecta a interface Oracle pelo default route, detecta `wg0`, mostra tooltip com OCI/WireGuard, usa `sudo -n wg show` quando disponivel para handshake/transferencia e renderiza os SVGs `omni-network-*.svg` para combinar com a barra escura.
