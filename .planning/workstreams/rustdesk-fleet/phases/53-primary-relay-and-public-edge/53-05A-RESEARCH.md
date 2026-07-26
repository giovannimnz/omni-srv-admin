# Phase 53-05A Research — Candidate Pin and Live Adapter Closure

## Findings

1. O release oficial `rustdesk-server` 1.1.16 aponta para commit
   `73523b31cfd25d77dee862e6fc9f5e1fb5e485ef`, imagem OCI multiarch
   `sha256:8ecdab65deb7c84652a626380e31d11a8f1fbafd97916d57f95c20628f943c00`,
   child ARM64 `sha256:593c9af7fb8010df0104f9150e8cac8fface359bcc3a358533214cc09ec80520`
   e ZIP ARM64 SHA-256 `6a4ae3c5ca257a4278ded72fd17eb2ca4eeb0356a5425e63a3e7fcb0ec6c155c`.
2. O release registra correção de reflection/amplification por UDP PunchHoleRequest
   não autenticado, atualização de `mio` e correção de overflow de timeout; promover
   1.1.15 sem avaliação seria uma regressão de segurança.
3. A observação Phase 52 existente está fora do TTL e ligada a source HEAD antigo;
   ela não pode autorizar live. É necessário um preflight currentness novo, sem
   replay de Gate B.
4. A tag 1.1.16 aponta para commit não verificado; a admissão exige uma exceção
   de provenance explicitamente owner-bound ou um rebuild assinado antes de
   qualquer promoção. Isso não reescreve o freeze histórico 1.1.15.
5. O runner atual só despacha adapters injetados. Os módulos server, edge, probe e
   ops API são reutilizáveis, mas requerem um factory explícito, journal value-free,
   rollback após falha e adapters remotos/OCI/DNS testáveis.
6. A capacidade histórica mantém srv-2/srv-3 em NO-GO e Horistic como primary; a
   preferência de relay exige dois samples frescos, recovery e security gate antes
   de qualquer colocação nova.

## Validation Strategy

- Verificar estrutura do plano e cobertura de requirements sem tocar os freezes.
- Testar factory com fakes, ordem completa, alias `edge-probes`, journal/resume,
  redaction e fault matrix de runtime/nft/OCI/IP/DNS/Apache.
- Validar supply candidate, currentness e ausência de secrets antes de qualquer
  live flag; só então considerar preflight e aprovação humana.

## Sources

- https://github.com/rustdesk/rustdesk-server/releases/tag/1.1.16
- https://api.github.com/repos/rustdesk/rustdesk-server/releases/tags/1.1.16
- https://hub.docker.com/v2/repositories/rustdesk/rustdesk-server/tags/1.1.16
- `modules/rustdesk-fleet/tools/run-phase53-live-gate.py`
- `modules/rustdesk-fleet/tools/install-phase53-server.py`
- `modules/rustdesk-fleet/tools/apply-phase53-edge.py`
- `modules/rustdesk-fleet/tools/probe-phase53-edge.py`
- `modules/rustdesk-fleet/tools/rustdesk-ops-api.py`
