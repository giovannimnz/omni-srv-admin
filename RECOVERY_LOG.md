# Log de Recuperação - Problema RDP Atius SRV
Data: 05 de Abril de 2026

## Estado Atual do Sistema
- **OS:** Ubuntu 22.04.5 LTS (Jammy) ARM64
- **Ambiente:** LXDE
- **Servidor RDP:** XRDP + xorgxrdp

## Ações Realizadas
1. **Credenciais:** Senha do usuário `ubuntu` resetada para `Bkfigi!546`.
2. **Arquivos de Configuração:**
   - `~/.xsession`: Contém `dbus-launch --exit-with-session startlxde`.
   - `/etc/X11/Xwrapper.config`: `allowed_users=anybody` (Permite X11 via RDP).
3. **Grupos e Permissões:**
   - `xrdp` está nos grupos: `ssl-cert`, `video`.
   - `ubuntu` está nos grupos: `xrdp`, `ssl-cert`.
4. **Serviços:** `xrdp` e `xrdp-sesman` reiniciados após as mudanças.

## Erros Observados anteriormente
- `pam_authenticate failed: Authentication failure` no `/var/log/xrdp-sesman.log`.
- Falha no carregamento da área de trabalho (provavelmente por falta do `.xsession` que agora foi criado).

## Próximos Passos (se não funcionar)
1. Verificar `/home/ubuntu/.xsession-errors` após a tentativa de login.
2. Testar login com teclado em modo US no Windows (para descartar problemas de layout ABNT2 no RDP).
3. Verificar se o firewall (`iptables`) está bloqueando a porta 3389 (embora o usuário consiga chegar na tela de login, o que indica que a porta está aberta).
