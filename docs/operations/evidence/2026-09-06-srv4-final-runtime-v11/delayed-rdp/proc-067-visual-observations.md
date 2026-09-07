# Observações visuais — proc_06700dd17aab

## Screenshot local negativa

Arquivo: `proc-067-historical-client-negative.png`

- área predominantemente preta;
- janela `Connection Log`;
- mensagem `login failed for user ubuntu`;
- nenhum desktop ou painel renderizado nessa captura.

Disposição: artifact negativo da segunda conexão, bloqueada por `MaxSessions=1`. Não usar como prova do primeiro desktop.

## Framebuffer remoto histórico

Arquivo: `proc-067-historical-remote-desktop.png`

- desktop escuro 1024×768;
- atalhos Trash e Obsidian;
- painel inferior escuro;
- launchers de Chrome, terminal, Obsidian e outros;
- indicador `BR(ABNT...)`;
- nenhuma mensagem de erro visível.

A associação a LXDE/display `:1` vem do state de processos, não apenas dos pixels.

## Framebuffer atual com TLS

Arquivo: `proc-067-current-tls-desktop.png`

- desktop escuro 1024×768;
- atalhos Trash e Obsidian;
- painel inferior e launchers;
- indicador `BR(ABNT...)`;
- nenhuma mensagem de erro visível.

O journal separado associa a sessão `c7/:1` a TLS 1.3, ABNT2 e login bem-sucedido. A sessão foi terminada após a captura.
