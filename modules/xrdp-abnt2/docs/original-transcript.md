# Transcricao da Conversa

Registro operacional da conversa inteira sobre a correcao do teclado XRDP ABNT2.

Observacao: outputs longos de comandos foram resumidos quando repetitivos, mas as decisoes, diagnosticos, arquivos alterados e resultados foram preservados.

## 1. Pergunta Inicial

Usuario:

> Qual o programa instalado de teclado aqui no meu ubuntu 22.04? de modo que penso em mudar para usar um que seja o mais compativel possivel com conexao rdp windows -> ATIUS-SRV-1 e Ubuntu cliente -> ATIUS-SRV-1

Resposta operacional:

- Foi verificado o ambiente local.
- Ambiente: `LXDE`, `X11`.
- Framework de input: `IBus 1.5.26`.
- Layout do sistema: `br`, variante `abnt2`.
- Cliente RDP instalado: `Remmina 1.4.25` com plugin RDP.
- Bibliotecas FreeRDP instaladas, mas inicialmente sem binario `xfreerdp`.
- Tambem havia `xrdp`, que e servidor RDP.

## 2. Prioridade Definida

Usuario:

> minha prioridade e compatibilidade com o windows, mas registre isso da compatibilidade com o linux tambem

Resposta operacional:

- Prioridade principal registrada: compatibilidade Windows/RDP para `ATIUS-SRV-1`.
- Compatibilidade Linux mantida como secundaria.

## 3. Problema no Remmina/Ubuntu Cliente

Usuario:

> Sigamos para como podemos resolver quanto a compatibilidade do windows, agora mesmo esta errado o teclado, diferente do windows 11 host que esta acessando via rdp

Resposta operacional:

- Investigado inicialmente como problema `Ubuntu/Remmina -> ATIUS-SRV-1`.
- Configurado Remmina:

```ini
rdp_keyboard_layout=10416
rdp_use_client_keymap=0
rdp_kbd_remap=
```

Motivo:

- `10416` corresponde ao layout Windows `00010416`, Portugues Brasil ABNT2.
- Desativar `Use client keyboard mapping` evita algumas traducoes problemáticas pelo GTK/Remmina.

## 4. Pedido de Ficar Sempre Fixo em ABNT2

Usuario:

> por mim, esse aqui fica full fixo sempre em br abnt2 totalmente autonomo, sem a possibilidade de ser alterado por app de conexao remota que seja

Resposta operacional:

- Verificado `/etc/default/keyboard`; ja estava correto:

```text
XKBMODEL="pc105"
XKBLAYOUT="br"
XKBVARIANT="abnt2"
XKBOPTIONS="lv3:ralt_switch"
BACKSPACE="guess"
```

- Encontrado problema: autostart e systemd apontavam para `/home/ubuntu/bin/setxkbmap-abnt2.sh`, mas o arquivo nao existia.
- Criado `/home/ubuntu/bin/setxkbmap-abnt2.sh`.
- Alterado autostart LXDE para chamar watchdog:

```text
@/home/ubuntu/bin/setxkbmap-abnt2.sh --watch
```

- Alterado `keyboard-abnt2.service` para rodar em modo persistente com restart.

## 5. Pesquisa de Bug Conhecido

Usuario:

> por mim tambem pesquisa se e um bug conhecido e afins eu quero a correcao definitiva

Resposta operacional:

- Pesquisados bugs e relatos de Remmina/FreeRDP/XRDP.
- Encontrados relatos recorrentes de teclado errado em RDP.
- Observado que `Use client keyboard mapping` no Remmina tem historico de comportamento inconsistente.
- Instalado `freerdp2-x11` para ter `xfreerdp`, mas depois ficou claro que o fluxo principal nao era esse.

## 6. Correcao de Foco: Windows 11 -> Este Ubuntu

Usuario:

> Mas preste atencao, eu estou conectado via microsoft rdp do windows 11 para o meu servidor ubuntu, esse aqui

Resposta operacional:

- Foco corrigido: componente principal e `xrdp` neste Ubuntu.
- Verificado `/etc/xrdp/xrdp_keyboard.ini`.
- O arquivo mapeava `00000416` para `br(abnt2)`, mas nao listava `00010416`.
- Criado `/etc/xrdp/km-00010416.ini`.
- Adicionado `00010416 -> br(abnt2)`.
- Reforcado `/etc/xrdp/startwm.sh` para aplicar ABNT2 e iniciar watchdog na sessao.

## 7. Logs Mostraram Outro Codigo do Windows

Achado nos logs:

```text
keylayout:[0x0000F010]
Cannot find keymap file /etc/xrdp/km-0000f010.ini
Loading keymap file /etc/xrdp/km-00000409.ini
```

E tambem:

```text
keylayout:[0x00010416]
Cannot find keymap file /etc/xrdp/km-00010416.ini
```

Resposta operacional:

- Criado `/etc/xrdp/km-0000f010.ini`.
- Adicionado `0000F010 -> br(abnt2)`.
- Por decisao do usuario, fallback `00000409`/US tambem foi substituido por ABNT2.

## 8. Pergunta Sobre Automaticidade

Usuario:

> aogra sera sempre 100% automatico e ficara sempre correto?

Resposta operacional:

- Sim para o fluxo normal `Windows 11 Microsoft RDP -> este Ubuntu`.
- Coberto:

```text
00010416 -> ABNT2
0000F010 -> ABNT2
00000409 -> ABNT2
```

- Watchdog reaplica a cada 5 segundos.
- Necessario desconectar e reconectar pelo RDP para nova sessao pegar a configuracao.

## 9. Pergunta Sobre Desconfigurar no Meio da Sessao

Usuario:

> e tem como no meio da sessao desconfigurar?

Resposta operacional:

- Sim, um processo poderia chamar `setxkbmap us`.
- Mitigacao aplicada: watchdog corrige em ate 5 segundos.
- Nao foi feita protecao destrutiva bloqueando binarios ou X11, por risco de quebrar aplicativos.

## 10. Pergunta Sobre Atualizacoes

Usuario:

> Esta protegido quanto a atualizacoes tambem?

Resposta operacional:

- Verificado que `xrdp_keyboard.ini`, `startwm.sh` e `km-00000409.ini` sao conffiles do pacote `xrdp`.
- Criado hook APT/DPKG:

```text
/etc/apt/apt.conf.d/99xrdp-abnt2-keyboard
```

- Criado script:

```text
/usr/local/sbin/fix-xrdp-abnt2-keyboard
```

- Criada fonte da verdade:

```text
/usr/local/share/xrdp-abnt2/
```

- Resultado: updates normais via `apt/dpkg` reaplicam a configuracao ABNT2 automaticamente.

## 11. Pedido de Salvamento

Usuario:

> Salva esse chat, a conversa inteira em: ~/Documentos/Solucao-Teclado-Xrdp-Br
>
> Tambem a solucao passo a passo, scripts, etc, completo

Resposta operacional:

- Criado este pacote em:

```text
/home/ubuntu/Documentos/Solucao-Teclado-Xrdp-Br
```

- Incluidos documentos, scripts, configs finais e backups.
