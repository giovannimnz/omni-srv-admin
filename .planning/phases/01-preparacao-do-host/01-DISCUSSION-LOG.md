# Phase 1: Preparação do Host - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-19
**Phase:** 01-preparacao-do-host
**Areas discussed:** FQDN, Port Mapping, DNS Strategy, Hostname, NTP, WireGuard Port, Cloudflare, Certbot

---

## FQDN

| Option | Description | Selected |
|--------|-------------|----------|
| atius-srv-1.atius.com.br | Hostname atual + domínio | |
| ipa.atius.com.br | Só domínio (mais limpo para FreeIPA) | ✓ |
| Outro FQDN | Definir nome customizado | |

**User's choice:** `ipa.atius.com.br`
**Notes:** FQDN dedicado para o servidor FreeIPA, mais claro que incluir hostname do servidor.

## Port Mapping

| Option | Description | Selected |
|--------|-------------|----------|
| 9080/9444 (Apache2) | Apache2 HTTP/HTTPS, Keycloak 9180/9843 | ✓ |
| 7080/7443 (Apache2) | Portas mais baixas, Keycloak 9443 | |
| 8880/8883 (Apache2) | Portas intermediárias, Keycloak 9443 | |

**User's choice:** 9080/9444 para Apache2
**Notes:** Portas 8080 e 9443 já em uso por Docker. 9080 estava livre mas 9443 estava em uso — ajustado para 9444 após verificação.

## DNS Strategy

| Option | Description | Selected |
|--------|-------------|----------|
| FreeIPA DNS primary | FreeIPA BIND assume, CoreDNS removido | ✓ |
| CoreDNS primary | CoreDNS continua, encaminha para FreeIPA | |
| Só FreeIPA DNS | Remove CoreDNS completamente | |

**User's choice:** FreeIPA BIND como DNS primário
**Notes:** CoreDNS será removido após FreeIPA DNS estar operacional.

## Hostname

| Option | Description | Selected |
|--------|-------------|----------|
| Alterar hostname | Mudar de atius-srv-1 para ipa.atius.com.br | |
| Manter atual | atius-srv-1 com FQDN via /etc/hosts + DNS | ✓ |

**User's choice:** Manter hostname atual `atius-srv-1`
**Notes:** FQDN configurado via `/etc/hosts` é suficiente para FreeIPA.

## NTP

| Option | Description | Selected |
|--------|-------------|----------|
| chrony | Padrão Ubuntu, melhor para VMs/cloud | ✓ |
| systemd-timesyncd | Mais simples, já pode estar ativo | |
| ntp (ntpd) | Traditional | |

**User's choice:** chrony
**Notes:** Recomendado para ambiente cloud/VM.

## WireGuard Port

| Option | Description | Selected |
|--------|-------------|----------|
| 51820 | Porta padrão, sem conflito | ✓ |
| 51821 | Alternativa | |

**User's choice:** 51820
**Notes:** Não conflita com FreeIPA DNS (porta 53).

## Cloudflare

| Option | Description | Selected |
|--------|-------------|----------|
| Origin Rules | :443 → origin:9444 (proxied mode) | ✓ |
| Custom ports | DNS proxy com portas customizadas | |
| Proxied off | DNS direto, sem SSL Cloudflare | |

**User's choice:** Origin Rules
**Notes:** Manter modo proxied do Cloudflare com Origin Rules apontando para porta 9444.

## Certbot

| Option | Description | Selected |
|--------|-------------|----------|
| http-01 alt port | --http-01-port 9080 | ✓ |
| DNS-01 challenge | Via Cloudflare API | |
| Manter atual | Sem mudanças | |

**User's choice:** http-01 na porta 9080
**Notes:** Certbot configurado para validar na porta alternativa HTTP.

---

## Claude's Discretion

Nenhuma área foi delegada à discrição do Claude.

## Deferred Ideas

- Migração de apps Atius para Keycloak OIDC — futuro
- Horistic no domínio — projeto separado
- Replica FreeIPA para HA — v2
