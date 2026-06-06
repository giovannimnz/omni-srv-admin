# Solucao Teclado XRDP BR ABNT2

Data do registro: 2026-06-05 23:46:48 -03:00

## Objetivo

Manter o teclado deste Ubuntu 22.04 sempre em Portugues Brasil ABNT2, principalmente para o fluxo:

```text
Windows 11 Microsoft Remote Desktop -> Ubuntu 22.04 com xrdp
```

Prioridade principal: compatibilidade com Windows/RDP.

Prioridade secundaria: manter compatibilidade local no Ubuntu e no fluxo `Ubuntu -> ATIUS-SRV-1`.

## Diagnostico

O problema principal nao era o Remmina. O fluxo real em uso era o Microsoft RDP do Windows 11 conectando neste Ubuntu. Portanto, o componente critico e o servidor `xrdp`.

Logs encontrados:

```text
xrdp_load_keyboard_layout: keylayout:[0x0000F010]
Cannot find keymap file /etc/xrdp/km-0000f010.ini
Loading keymap file /etc/xrdp/km-00000409.ini

xrdp_load_keyboard_layout: keylayout:[0x00010416]
Cannot find keymap file /etc/xrdp/km-00010416.ini
```

Conclusao: o Windows 11 enviava layouts que o `xrdp` local nao mapeava corretamente. Em alguns casos, caia para `00000409`/US.

## Solucao Aplicada

Camadas aplicadas:

- Sistema Ubuntu configurado como `br abnt2`.
- `xrdp_keyboard.ini` agora reconhece `00010416` como `br(abnt2)`.
- `xrdp_keyboard.ini` tambem reconhece `0000F010` como `br(abnt2)`.
- Fallback `00000409`/US do XRDP foi trocado para ABNT2, por decisao explicita de manter este host sempre em ABNT2.
- Foram criados keymaps XRDP para `00010416` e `0000F010`.
- `startwm.sh` aplica ABNT2 no inicio da sessao XRDP.
- Watchdog reaplica ABNT2 a cada 5 segundos durante a sessao.
- Hook APT/DPKG reaplica a solucao apos atualizacoes.

## Arquivos Neste Pacote

```text
README.md
SOLUCAO-PASSO-A-PASSO.md
TRANSCRICAO-DA-CONVERSA.md
scripts/
  setxkbmap-abnt2.sh
  fix-xrdp-abnt2-keyboard
  reaplicar-solucao-completa.sh
configs/
  xrdp_keyboard.ini
  startwm.sh
  km-00000409.ini
  km-00000416.ini
  km-00010416.ini
  km-0000f010.ini
  99xrdp-abnt2-keyboard
backups/
  xrdp_keyboard.ini.bak-codex-20260605
  startwm.sh.bak-codex-20260605
  km-00000409.ini.bak-codex-20260605
```

## Como Reaplicar

Do diretorio desta solucao:

```bash
cd ~/Documentos/Solucao-Teclado-Xrdp-Br
sudo ./scripts/reaplicar-solucao-completa.sh
```

Depois, desconecte e reconecte pelo Microsoft RDP para pegar a configuracao em uma nova sessao.

O script nao reinicia `xrdp` automaticamente para evitar derrubar sessoes remotas ativas.

## Ressalvas

Isto cobre atualizacoes normais via `apt/dpkg`, autodeteccao do Windows RDP, fallback do XRDP e mudancas acidentais de layout durante a sessao.

Nao e uma protecao contra remocao manual deliberada, `apt purge xrdp`, apagamento de `/usr/local/share/xrdp-abnt2`, ou processo malicioso rodando como root.
