# Evidência Operacional: CI Busca Inteligente Multi-Tier e Deploy Run #39125848876

- **Data:** 2026-10-18T09:16:00-03:00
- **Origem:** Workflow CI `giovannimnz/voto-certo` (Commit `cc2d79c`)
- **Resultado:** 100% Sucesso (5/5 Jobs: `test`, `system-test`, `lint`, `scan_ruby`, `scan_js`)
- **Implementação:** Diretriz Canônica Permanente de Busca Inteligente Multi-Tier (9 Tiers), simetria NFD desacentuada, busca por documentos (CPF/RG) e similaridade fuzzy pg_trgm.
- **Deploy:** Sincronizado com sucesso no nó de produção `aln-srv-1` (`10.31.1.17`). Serviço `voto-certo.service` reiniciado e respondendo HTTP 200 OK no probe `/up`.
- **Validação:** Simetria bidirecional confirmada no banco real (buscas `'betania'` e `'betânia'` retornam os mesmos registros com priorização de fidelidade literal).
- **Auditoria:** Certificado pela esteira autônoma Antigravity.
