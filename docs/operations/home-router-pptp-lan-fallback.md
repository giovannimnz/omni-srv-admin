# Home Router PPTP LAN Fallback

**Date:** 2026-07-10
**Canonical project:** `/home/ubuntu/GitHub/vpn-atius/home-proxy`
**Status:** Architecture/spike, not live production

## Purpose

Documentar a linha de arquitetura para uma VPN residencial PPTP no Huawei BE3, reaproveitando o fluxo `home-proxy`/`home-edge` que ja esta planejado para `dns-casa.atius.com.br`, ADGuard Home, reverse proxy e watcher de WAN.

## Hard Requirements

- Nao usar L2TP. Esta linha e PPTP-only.
- `GIOVANNI-W11-PC` deve ficar reservado no router como `192.168.1.8`, MAC `44:FA:66:01:6F:AB`.
- `GIOVANNI-S20` deve ficar reservado no router como `192.168.1.9`, MAC `30:AB:6A:3C:96:D1`.
- `GIOVANNI-S23` deve ficar reservado no router como `192.168.1.10`, MAC `64:1B:2F:C2:DC:A3`.
- Apenas esses tres clientes devem usar o canal; se a exclusividade tecnica nao for comprovada, o modo deve ser rotulado como `GO risk-accepted dns-correlated`, nao como enforcement forte.
- WireGuard fica como fallback remoto/off-home, nao como preferencia quando os dois dispositivos estiverem em casa.
- Segredos ficam no Vault; docs registram apenas paths/nomes de variaveis.
- Este PPTP e home-edge residencial. Nao substitui OCI/DRG, nao anuncia `192.168.1.0/24` para DRG/wg100 e nao vira source of truth para DNS interno, PgBouncer, K3s, Vault, Obsidian, TEI ou inventory routing.

## Validated Context

- `home-proxy` Phase 3 fechou o caminho operacional `BE3 WAN admin allowlist -> casa.atius.com.br -> atius-srv-1`.
- `home-proxy` Phase 4 planeja `dns-casa.atius.com.br`, ADGuard Home, watcher de WAN e firewall dinamico.
- A tela VPN capturada no BE3 mostra L2TP/PPTP como conexoes para um servidor VPN externo, com `Connect`. A interpretacao atual e cliente VPN, nao servidor PPTP no roteador.
- Nao havia, no `omni-srv-admin`, plano canonico previo para esse PPTP residencial.

## Canonical Architecture

O servico deve ser tratado como uma unica stack `home-edge` de gestao/comunicacao para DNS/AdGuard, reverse proxy e PPTP. Isso significa um unico runbook/dashboard/state/cutover/rollback coordenado.

O isolamento continua obrigatorio como boundary tecnico interno, nao como produto separado:

- AdGuard: DNS/AdGuard, sem PPP/GRE e sem `NET_ADMIN`.
- Reverse proxy/status: HTTP/control plane, sem PPP.
- PPTP runtime: unico componente com `NET_ADMIN`, `/dev/ppp`, GRE/protocolo 47 e TCP 1723.

Usar o mesmo padrao operacional da Phase 4: firewall deny-by-default, estado auditavel, Vault-first, rollback documentado e validacao externa. Rollback de PPTP precisa remover TCP 1723/GRE sem quebrar DNS/proxy; rollback de AdGuard/proxy nao pode deixar PPTP aberto por acidente.

DNS/AdGuard/DHCP entra como catalogo operacional de identidade: `GIOVANNI-W11-PC`, `GIOVANNI-S20` e `GIOVANNI-S23` devem aparecer por hostname, IP fixo, MAC/lease, PTR/client registry, query logs e freshness. Isso ajuda a saber quem e quem nos logs PPTP/firewall, mas nao e identidade criptografica nem autorizacao forte.

## Critical Gate

Antes de qualquer deploy real, validar o comportamento PPTP do BE3 como transporte e provar enforcement no servidor `home-edge`.

O BE3 pode criar um tunel amplo para a LAN. `GO server-enforced` nao depende de policy/source routing no BE3; depende de o servidor enxergar um sinal distinguivel para permitir somente W11/S23, como origem LAN preservada, identidade/peer por dispositivo, IP PPP remoto atribuido por usuario ou outro gate server-side auditavel.

Se o BE3 fizer tunel global e NATear toda a LAN para uma unica identidade indistinta, o servidor nao consegue separar W11/S23 dos demais com enforcement forte. Nesse caso, a variante router-client so pode seguir como `GO risk-accepted dns-correlated` quando houver DNS/AdGuard/DHCP correlation, kill switch, logs, rollback e aceite explicito do risco; sem isso e `NO-GO`. A alternativa direta por dispositivo vira contingency/follow-up, nao promocao automatica.

## Operational Warning

PPTP e inseguro por definicao. O uso so e aceitavel aqui como fallback residencial estreito, sem exposicao ampla, sem credenciais reaproveitadas e sem misturar com L2TP. O modo `GO risk-accepted dns-correlated` e deliberadamente fraco: serve como camada adicional e auditoria, nao como garantia 100% segura.

## References

- `home-proxy/.planning/spikes/001-router-pptp-lan-fallback/README.md`
- `home-proxy/docs/research/2026-07-10-router-pptp-lan-fallback.md`
- Codex sessions: `019f42d1-9bde-7972-ae30-b2840cda9949`, `019f3ef0-bf50-7e93-9834-af51f040c1db`
