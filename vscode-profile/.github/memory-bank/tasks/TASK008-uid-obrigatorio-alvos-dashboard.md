# [TASK008] - UID Obrigatório, Labels Alvo, Manual Target, Dashboard Balance

**Status:** Completed  
**Added:** 12/02/2026  
**Updated:** 12/02/2026

## Original Request

O usuário solicitou 4 mudanças:
1. Tirar o "opcional" do UID do cadastro de Usuário, tornar verificação de UID obrigatória
2. Mudar TP1, TP2, etc para "Alvo 1", "Alvo 2" no painel semi-automático
3. Colocar mais uma janela de alvo ao lado do Alvo 5: "Inserir manualmente"
4. O saldo do dashboard deve atualizar com base na corretora (como já é feito no painel semiautomático)
5. Testar tudo com Playwright até 100%

## Thought Process

- UID obrigatório: Mudança simples em frontend (validação + label) e backend (schema JSON)
- Labels Alvo: Renomeação pura de texto, sem mudança de lógica
- Alvo Manual: Adição de 6º box no grid com input editável e lógica de submit diferenciada
- Dashboard Balance: O dashboard já tinha endpoint de refresh, faltava chamá-lo no useEffect
- Cookie Domain: Descoberto que auth-token tem Domain=.atius.com.br, impossibilitando login via formulário no localhost. Solução: setar cookie via `page.context().addCookies()` no Playwright

## Implementation Plan
- [x] Step 1: UID obrigatório no frontend (login-form.tsx)
- [x] Step 2: UID obrigatório no backend (users/index.js schema)
- [x] Step 3: Renomear TP1-5 → Alvo 1-5 (multi-tp-trading-interface.tsx)
- [x] Step 4: Adicionar box Manual com grid-cols-6 e input editável
- [x] Step 5: Dashboard balance auto-refresh (dashboard.tsx)
- [x] Step 6: Build frontend e PM2 restart
- [x] Step 7: Atualizar testes E1, E4, E5 de registro afiliado
- [x] Step 8: Criar testes A1-A10 para Alvo/Manual e Dashboard

## Progress Tracking

**Overall Status:** Completed - 100%

### Subtasks
| ID | Description | Status | Updated | Notes |
|----|-------------|--------|---------|-------|
| 8.1 | UID obrigatório frontend | Complete | 12/02 | Label "UID Bybit *", validação exige UID verificado |
| 8.2 | UID obrigatório backend | Complete | 12/02 | Schema require bybit_uid minLength:1 |
| 8.3 | Labels TP → Alvo | Complete | 12/02 | 5 labels + placeholders renomeados |
| 8.4 | Box Alvo Manual | Complete | 12/02 | 6º box, grid-cols-6, border-orange, input editável |
| 8.5 | Dashboard balance refresh | Complete | 12/02 | updateAllAccountBalances + 60s interval |
| 8.6 | Build e deploy | Complete | 12/02 | Build OK, PM2 restart OK |
| 8.7 | Testes affiliate atualizados | Complete | 12/02 | E1, E4, E5 reescritos |
| 8.8 | Novos testes Alvo/Manual/Dashboard | Complete | 12/02 | A1-A10, 13/13 passando |

## Progress Log
### 12/02/2026
- Implementadas as 4 mudanças solicitadas
- Frontend build: sucesso
- PM2 restart: atius-api e atius-web online
- Validação via curl: registro sem UID → 400, UID vazio → 400
- Atualização dos testes E1, E4, E5 para refletir UID obrigatório
- Criação de test_alvo_manual_e_labels.spec.ts com 8 testes (A1-A10)
- Descoberto e resolvido problema de cookie Domain=.atius.com.br nos testes
- Resultado final: 13/13 testes passando (5 affiliate + 8 novos)

## Arquivos Modificados
- `frontend/src/components/auth/login-form.tsx` — UID obrigatório
- `backend/server/routes/users/index.js` — Schema UID obrigatório
- `frontend/src/components/multi-tp-trading-interface.tsx` — Alvos + Manual
- `frontend/src/components/dashboard.tsx` — Balance auto-refresh
- `tests/frontend/e2e/test_affiliate_registration.spec.js` — E1, E4, E5 atualizados
- `tests/frontend/e2e/test_alvo_manual_e_labels.spec.ts` — 8 novos testes (CRIADO)
