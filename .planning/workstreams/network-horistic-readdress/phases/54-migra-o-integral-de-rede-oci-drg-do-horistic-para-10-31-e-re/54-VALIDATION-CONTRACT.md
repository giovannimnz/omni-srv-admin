# Fase 52 — contrato de validação automática

Cada plano termina com uma tarefa `type="auto"` de validação. Essa tarefa é
parte do plano, não uma atividade posterior opcional, e deve ser executada antes
de liberar o plano seguinte.

## Runner comum

O primeiro plano cria e testa:

```text
modules/fleet-control-plane/scripts/phase54_network_gate.py
```

Interface:

```text
python3 modules/fleet-control-plane/scripts/phase54_network_gate.py final \
  --plan 54-0N \
  --evidence .planning/phases/54-.../54-0N-EVIDENCE.json \
  --gate .planning/phases/54-.../54-0N-GATE.json
```

O runner deve:

- executar todos os probes do plano com timeout e sem retry cego;
- redigir segredos, tokens, chaves e headers;
- gravar JSON atomicamente, com timestamp, comandos, exit codes, resultados,
  SHA-256 do evidence e `status: PASS|WARN|BLOCK|UNKNOWN`;
- sair `0` somente quando todos os checks obrigatórios passarem;
- sair diferente de zero e gravar `BLOCK` quando um check obrigatório falhar;
- converter `UNKNOWN` em `BLOCK` para qualquer check obrigatório; `WARN` só é
  permitido para check advisory com owner/expiry explícitos;
- nunca executar uma remoção ou liberar IP público como efeito colateral.

## Gate entre planos

O início de cada plano posterior deve verificar o gate anterior:

```text
test -s 54-0N-GATE.json && jq -e \
  '.status == "PASS" and .plan == "54-0N" and (.evidence_sha256 | length == 64)' \
  54-0N-GATE.json
```

Falha no teste bloqueia a wave e mantém o caminho de rollback. Checkpoints
humanos continuam obrigatórios antes de writes destrutivos; a validação
automática não substitui aprovação humana. O agregador da fase grava
`54-VALIDATION-RESULT.json` e só permite atualizar STATE/ROADMAP/requirements
quando todos os gates requeridos estão em `PASS`.

## Evidência mínima por plano

| Plano | Validação automática obrigatória |
|---|---|
| 54-01 | inventário dos quatro profiles, CIDRs/rotas/VNICs/public IP, hosts/serviços/portas/WG/DNS/K3s e backup + restore staging |
| 54-02 | overlap matrix, `lpg_ready`, CIDR/subnet ACTIVE/containment, regras/rotas ida-retorno e attachment VNIC |
| 54-03 | endereços/rotas/ARP, K3s worker, public-IP OCIDs/estado, origin direto/Cloudflare/TLS/SSH e reversa dry-run |
| 54-04 | listeners/HTTP/SSH/TEI/reranker/PgBouncer/Router/exporters, FreeIPA A/PTR/SOA/TTL, forwards e classificação `.21` |
| 54-05 | BE3 screenshot/readback/lease/collision, peer11, `AllowedIPs`, handshakes, device-side S23/S20 e fallback |
| 54-06 | duas matrizes completas separadas por ≥15 min, rollback receipt, public-IP reverse dry-run e residual CIDR explícito |
