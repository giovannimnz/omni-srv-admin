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
   build tools, Rust, cargo-binstall e Zellij.
7. Instalar `omni` em pipx e aplicar `xrdp-abnt2` com
   `--install-packages` apenas em host novo. Validar os três units XRDP e o
   timer de reconciliação.
8. Registrar o host no inventário, documentar a evidência e atualizar GBrain
   e Obsidian com fatos sem segredos.

## Guardrails

- Nunca copiar `.ssh/private.pem`, Vault tokens, `.env`, caches ou dumps PM2
  entre hosts.
- Não promover K3s, Vault, Wayland, PM2 de produção ou containers de outro
  servidor sem que a função do novo host esteja explicitamente definida.
- A integração ao DRG central é cross-tenancy e exige OperationPlan, preview,
  confirmação tipada, readback e atualização das rotas dos dois lados.
- RDP público não é baseline. Expor TCP/3389 somente por regra OCI específica
  e aprovada para a origem necessária.

## Evidência de conclusão

- SSH por chave canônica autenticado;
- TCP/22 e a route table efetiva comprovados;
- `podman info` rootless e smoke de container aprovados;
- `omni xrdp-abnt2 validate` aprovado;
- `~/GitHub/omni-srv-admin` limpo no commit registrado;
- inventário, GBrain e Obsidian atualizados.
