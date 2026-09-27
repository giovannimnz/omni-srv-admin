# Quick Task Summary: Mosh Port Range Governance & Fleet Rollout

- **Task ID:** `260927-mosh-port-governance-rollout`
- **Date:** 2026-09-27
- **Status:** Complete (100%)

## Objectives
1. Padronizar a faixa de portas UDP do Mosh para `60001 a 60999` em toda a frota (4 servidores ATIUS + 1 Horistic).
2. Auditar cada nó, instalar o pacote `mosh` onde ausente e aplicar/persistir a regra de firewall local no topo do iptables.
3. Atualizar as 9 Security Lists na OCI para permitir Ingress UDP 60001-60999.
4. Garantir que novas máquinas provisionadas via `omni-srv-admin` (`setup.sh`, `iptables-backup-v4.conf`, inventários) já nasçam prontas com o Mosh e suas portas liberadas.
5. Sincronizar toda a documentação no Obsidian, GBrain e no repositório `oci-admin`.

## Delivered Changes

### 1. Host Audits & Fixes
- `atius-srv-1`: `mosh` 1.4.0 ok; regra iptables adicionada no topo e salva.
- `atius-srv-2`: `mosh` 1.4.0 ok; regra iptables adicionada no topo e salva.
- `atius-srv-3`: `mosh` 1.4.0 ok; regra iptables adicionada no topo e salva.
- `atius-srv-4`: `mosh` ausente -> instalado via apt (`1.4.0`); regra iptables inserida antes da rejeição ICMP host-prohibited e salva.
- `horistic-srv`: `mosh` 1.4.0 ok; regra iptables adicionada no topo e salva.

### 2. OCI Security Lists (9 listas atualizadas)
- Regra Ingress: UDP, 0.0.0.0/0, destination min: 60001, max: 60999, stateless: False.
- Perfis OCI atualizados: `atius1`, `atius2`, `atius3`, `atius4`, `horistic`.

### 3. omni-srv-admin
- `setup.sh`: Adicionado `mosh` no apt-get da Etapa 1.
- `iptables/iptables-backup-v4.conf`: Inserida regra persistente UDP 60001:60999.
- `inventory/hosts/*.yaml`: Adicionado app `mosh` com `port_range: "60001-60999/udp"` nos 5 servidores.
- `docs/network/mosh-port-governance.md`: Criado guia canônico de governança de portas.

### 4. oci-admin
- `docs/mosh-port-governance-and-security-rules.md`: Documentação de regras de Security List, OCIDs e automação via SDK/CLI.

### 5. Obsidian Vault (`AiSecondBrain`)
- `Infra/portas-canonicas-mapeadas.md`: Faixa atualizada para 60001-60999 (UDP).
- `Infra/mosh-termius-setup-and-fleet-rollout.md`: Runbook atualizado para status concluído na frota.
- `60-LOGS/2026-09-27-mosh-fleet-port-governance-rollout.md`: Registro detalhado da execução.

### 6. GBrain
- `operations/mosh-termius-setup-and-fleet-rollout`: Conteúdo atualizado + timeline entry registrada.
- Fato `#151` registrado na memória semântica do GBrain.
