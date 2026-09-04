# Bootstrap de novo servidor OCI ARM64

Este runbook transforma uma instância Ubuntu 24.04 ARM64 mínima no padrão
operacional ATIUS. Ele foi validado em `atius-srv-4`.

## Ordem obrigatória

1. Confirmar que cloud-init e qualquer instalador de utilitários terminaram.
2. Pelo `oci_admin_http`, validar instance `RUNNING`, VNIC, IP privado/público,
   NSG/security list e a tabela de rota efetiva da subnet.
3. Para SSH público, a subnet precisa usar uma route table com
   `0.0.0.0/0 -> Internet Gateway`; não usar a VCN ingress route table como
   route table da subnet.
4. Confirmar TCP/22 antes de diagnosticar chave. Comparar fingerprints da
   chave privada local e da chave pública entregue por Vault, sem expor o
   material.
5. Criar `~/GitHub` e `~/GitHub/containers`; copiar o checkout limpo mais
   recente de `omni-srv-admin` ou clonar a origem verificada.
6. Instalar a baseline ARM64: Git, Python/venv/pipx, Podman rootless, rede,
   build tools, Rust estável, cargo-binstall e Zellij. Materializar
   `~/.config/environment.d/90-atius-developer-tools.conf` para que
   `~/.cargo/bin` e `~/.local/bin` existam também nas sessões XRDP e systemd
   do usuário.
   Configurar Podman com `srv4-podman` em `10.10.4.0/24`, netavark e
   `systemd-resolved`; habilitar linger e `podman.socket` para persistência
   user-level, sem iniciar stacks de aplicação.
7. Instalar `omni` em pipx e aplicar `xrdp-abnt2` com
   `--install-packages` apenas em host novo. Validar os três units XRDP e o
   timer de reconciliação.
8. Fixar o teclado global em `br(abnt2)` e revalidar o guard XRDP; a sessão
   RDP usa os keymaps canônicos mesmo sem um desktop já aberto.
9. Instalar e registrar `landscape-client` no Landscape self-hosted
   `standalone` com os endpoints `message-system` HTTPS e `ping` HTTP. Nunca
   usar o profile SaaS legado para o self-hosted.
10. Hidratar o profile Vault `omni-fleet`, instalar `omni-fleet-agent` e
    registrar o inventário no DbOmniFleet; confirmar heartbeat, programas e
    versão antes de declarar o host incluído nos relatórios.
11. Registrar o host no inventário, documentar a evidência e atualizar GBrain
    e Obsidian com fatos sem segredos.

## Guardrails

- Nunca copiar `.ssh/private.pem`, Vault tokens, `.env`, caches ou dumps PM2
  entre hosts.
- Não promover K3s, Vault, Wayland, PM2 de produção ou containers de outro
  servidor sem que a função do novo host esteja explicitamente definida.
- A integração ao DRG central é cross-tenancy e exige OperationPlan, preview,
  confirmação tipada, readback e atualização das rotas dos dois lados.
- Depois de a rota DRG estar comprovada, adicionar `10.14.0.0/16` aos guards
  persistentes de serviços do SRV-1 (PgBouncer e Obsidian REST) e às rotas
  OCI-primary do host antes de declarar a malha privada green.
- RDP público não é baseline. Expor TCP/3389 somente por regra OCI específica
  e aprovada para a origem necessária.

## Evidência de conclusão

- SSH por chave canônica autenticado;
- TCP/22 e a route table efetiva comprovados;
- `podman info` rootless e smoke de container aprovados;
- `omni xrdp-abnt2 validate` aprovado;
- `landscape-config --is-registered` e `landscape-client` ativos;
- `omni-fleet-agent` ativo, com heartbeat e relatórios DB para o host;
- `~/GitHub/omni-srv-admin` limpo no commit registrado;
- inventário, GBrain e Obsidian atualizados.
