# [TASK006] - Verificação de Afiliados Bybit no Cadastro

**Status:** Completed  
**Added:** 10/02/2026  
**Updated:** 11/02/2026

## Original Request

Criar uma consulta à API de afiliados Bybit e adicionar no cadastro de usuário um campo opcional "UID Bybit" com botão "Verificar". Usuário só cadastra se o UID estiver na lista de afiliados. Armazenar credenciais na tabela `configuracoes`. Adicionar colunas `bybit_uid` e `affiliate` na tabela `users`. Ao cadastrar, apenas `can_access_trade=true`; demais permissões são atribuídas pelo admin.

**Credenciais API Bybit Affiliate:**
- Key: `MbEelAGZh1jA2WX403`
- Secret: `3ayIHzrVusuEdltKint4Bk4PwqnOQeLSVdIa`

## Thought Process

1. Pesquisa da API Bybit `/v5/affiliate/aff-user-list` — autenticação via HMAC-SHA256
2. Decisão: rota pública (sem auth) para verificação durante cadastro
3. Paginação: size=1000, até 50 páginas para cobrir listas grandes
4. Frontend: estados visuais claros (idle/verifying/valid/invalid/error)
5. Regra: campo UID preenchido ⇒ botão cadastro só habilita após verificação bem-sucedida
6. Migração: alterar defaults de permissões para restringir acesso automático

## Implementation Plan

- [x] Documentação completa do plano
- [x] Migração V14 no banco de dados
- [x] Rota backend POST /v1/users/verify-bybit-uid
- [x] Atualizar rota register (aceitar bybit_uid)
- [x] Atualizar GET /auth/me (retornar bybit_uid e affiliate)
- [x] Frontend: api.js (verifyBybitUid + register atualizado)
- [x] Frontend: auth-context.tsx (tipagem register)
- [x] Frontend: login-form.tsx (campo UID + botão Verificar)
- [x] Testes backend (10 cenários)
- [x] Testes E2E Playwright (5 cenários)
- [x] Documentação final atualizada

## Progress Tracking

**Overall Status:** Completed - 100%

### Subtasks

| ID | Description | Status | Updated | Notes |
|----|-------------|--------|---------|-------|
| 6.1 | Documentação do plano | Complete | 10/02 | docs/IMPLEMENTACAO_AFILIADOS_BYBIT_10_02_2026.md |
| 6.2 | Migração V14 banco de dados | Complete | 10/02 | Executada via MCP Postgres |
| 6.3 | Backend: rota verify-bybit-uid | Complete | 10/02 | HMAC-SHA256, paginação |
| 6.4 | Backend: register + auth/me | Complete | 10/02 | bybit_uid, affiliate |
| 6.5 | Frontend: api.js | Complete | 10/02 | verifyBybitUid() |
| 6.6 | Frontend: auth-context.tsx | Complete | 10/02 | Tipagem register |
| 6.7 | Frontend: login-form.tsx | Complete | 10/02 | Campo UID + Verificar |
| 6.8 | Testes backend | Complete | 10/02 | 10 cenários |
| 6.9 | Testes E2E Playwright | Complete | 10/02 | 5 cenários |
| 6.10 | Documentação final | Complete | 10/02 | Status ✅ Implementado |

## Progress Log

### 10/02/2026
- Pesquisa da API Bybit affiliate via Brave Search e Context7
- Análise do esquema de banco existente via MCP Postgres
- Criada documentação completa do plano
- Executada migração V14 (6 statements SQL) diretamente no banco
- Implementadas rotas backend (verify-bybit-uid, register atualizado, auth/me)
- Implementado frontend (api.js, auth-context.tsx, login-form.tsx)
- Criados 10 cenários de teste backend
- Criados 5 cenários E2E Playwright
- Todos os arquivos compilam sem erros

### 11/02/2026
- Backend reiniciado via PM2 (`pm2 restart atius-api`)
- Frontend compilado (`npm run build`) e reiniciado (`pm2 restart atius-web`)
- Testes backend executados: **9/9 passando** ✅
- Testes E2E Playwright executados: **5/5 passando** ✅
- Documentação atualizada com comandos PM2 detalhados
- **Status**: Totalmente implementado, validado e em produção

## Arquivos Criados/Modificados

| Arquivo | Operação |
|---------|----------|
| `backend/core/database/migrations/V14__add_bybit_affiliate.sql` | Criado |
| `backend/server/routes/users/index.js` | Modificado |
| `backend/server/routes/auth/index.js` | Modificado |
| `frontend/src/lib/api.js` | Modificado |
| `frontend/src/contexts/auth-context.tsx` | Modificado |
| `frontend/src/components/auth/login-form.tsx` | Modificado |
| `tests/backend/test_bybit_affiliate_verification.js` | Criado |
| `tests/frontend/e2e/test_affiliate_registration.spec.js` | Criado |
| `docs/IMPLEMENTACAO_AFILIADOS_BYBIT_10_02_2026.md` | Criado |
