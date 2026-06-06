# Solucao Passo a Passo

## 1. Confirmar Configuracao Base do Ubuntu

Arquivo esperado:

```bash
/etc/default/keyboard
```

Conteudo esperado:

```text
XKBMODEL="pc105"
XKBLAYOUT="br"
XKBVARIANT="abnt2"
XKBOPTIONS="lv3:ralt_switch"
BACKSPACE="guess"
```

## 2. Corrigir Mapeamento do XRDP

Arquivo:

```bash
/etc/xrdp/xrdp_keyboard.ini
```

Entradas importantes aplicadas:

```ini
variant=abnt2
model=pc105

rdp_layout_br_abnt2_alt=0x0000F010
rdp_layout_br=0x00000416
rdp_layout_br_abnt2=0x00010416

rdp_layout_us=br(abnt2)
rdp_layout_us_dvorak=br(abnt2)
rdp_layout_us_dvp=br(abnt2)
rdp_layout_br_abnt2_alt=br(abnt2)
rdp_layout_br=br(abnt2)
rdp_layout_br_abnt2=br(abnt2)
```

Motivo: os logs mostraram que o Windows 11 enviava `0000F010` e `00010416`. Antes, o XRDP nao tinha keymap para eles e podia cair em US.

## 3. Criar Keymaps XRDP

Arquivos criados ou substituidos:

```bash
/etc/xrdp/km-00000409.ini
/etc/xrdp/km-00010416.ini
/etc/xrdp/km-0000f010.ini
```

Todos usam o conteudo ABNT2 baseado em:

```bash
/etc/xrdp/km-00000416.ini
```

Motivo: como a decisao foi este host ficar sempre ABNT2, ate o fallback US `00000409` foi convertido para ABNT2.

## 4. Forcar ABNT2 no Inicio da Sessao XRDP

Arquivo:

```bash
/etc/xrdp/startwm.sh
```

Trecho aplicado:

```sh
for i in $(seq 1 10); do
    if [ -n "$DISPLAY" ] && /usr/bin/setxkbmap -model pc105 -layout br -variant abnt2 -option -option lv3:ralt_switch 2>/dev/null; then
        break
    fi
    sleep 1
done

if [ -x "$HOME/bin/setxkbmap-abnt2.sh" ]; then
    "$HOME/bin/setxkbmap-abnt2.sh" --watch &
fi
```

## 5. Watchdog ABNT2

Arquivo:

```bash
/home/ubuntu/bin/setxkbmap-abnt2.sh
```

Funcao:

- Aplica ABNT2 uma vez quando chamado sem argumentos.
- Com `--watch`, reaplica ABNT2 a cada 5 segundos.
- Usa lock em `/tmp` para evitar varios watchdogs duplicados.

## 6. Protecao Contra Atualizacoes

Arquivos:

```bash
/etc/apt/apt.conf.d/99xrdp-abnt2-keyboard
/usr/local/sbin/fix-xrdp-abnt2-keyboard
/usr/local/share/xrdp-abnt2/
```

Hook APT:

```aptconf
DPkg::Post-Invoke { "/usr/local/sbin/fix-xrdp-abnt2-keyboard || true"; };
```

Funcao: depois de operacoes `apt/dpkg`, reaplica automaticamente os arquivos XRDP fixos em ABNT2.

## 7. Validacao

Verificar mapeamentos:

```bash
rg -n '00010416|0000F010|rdp_layout_us=br\(abnt2\)|rdp_layout_br_abnt2' /etc/xrdp/xrdp_keyboard.ini
```

Verificar arquivos:

```bash
ls -l /etc/xrdp/km-00000409.ini /etc/xrdp/km-00010416.ini /etc/xrdp/km-0000f010.ini
```

Verificar hook:

```bash
cat /etc/apt/apt.conf.d/99xrdp-abnt2-keyboard
```

Verificar script:

```bash
/usr/local/sbin/fix-xrdp-abnt2-keyboard
```

## 8. Aplicacao em Sessao Ativa

Para a sessao atual, o mais limpo e desconectar e reconectar pelo Microsoft RDP.

Nao reiniciar automaticamente:

```bash
sudo systemctl restart xrdp
```

Esse comando derruba sessoes RDP ativas, entao deve ser usado apenas se houver janela de manutencao.
