# [TASK007] - Feedback de Execução de Ordens no Painel Semi-Automático

**Status:** Completed  
**Added:** 2026-02-10  
**Updated:** 2026-02-11

## Original Request

No painel de trading semi-automático (`trade.atius.com.br/sinal/[id]`), quando o usuário envia uma ordem, o sistema mostra apenas "Pending" sem dar retorno real da corretora. O usuário quer:
- **Sucesso**: "Ordem posicionada com sucesso"
- **Erro**: "Envio de ordem falhou (MOTIVO)" com tradução amigável em pt-BR para erros comuns da Bybit
- Erro 110092 e outros erros comuns tratados em português
- Erros desconhecidos: mensagem genérica

## Thought Process

### Problema Raiz
O backend usa `setImmediate()` para executar a ordem de forma assíncrona. O endpoint POST retorna imediatamente com `{ success: true, status: 'PENDING', order_id }` antes de a corretora responder.

### Solução Escolhida
**Polling no frontend**: Após receber o `order_id`, o frontend faz polling no endpoint GET existente (`/v1/orders/manual/:orderId?conta_id=X`) a cada 2 segundos até o status mudar de PENDING/VALIDATING/PROCESSING para EXECUTED ou ERROR/REJECTED. Timeout de 30s.

### Alternativa Descartada
- Tornar o endpoint síncrono: Rejeitado por causar timeout HTTP em ordens lentas e bloquear o servidor.
- WebSocket: Over-engineering para o caso de uso atual.

## Implementation Plan
1. Adicionar método `getManualOrderStatus(orderId, contaId)` em `api.js`
2. Criar mapa de tradução de erros Bybit em pt-BR
3. Modificar `handleSubmit` em `multi-tp-trading-interface.tsx` para fazer polling após criação
4. Mostrar estados visuais: "Executando..." → "Sucesso" / "Falha: motivo"
5. Build e restart dos serviços
6. Testes
7. Documentação

## Progress Tracking

**Overall Status:** Completed - 100%

### Subtasks
| ID | Description | Status | Updated | Notes |
|----|-------------|--------|---------|-------|
| 7.1 | Mapear fluxo atual (backend + frontend) | Complete | 2026-02-10 | Endpoint GET já existe, falta polling no frontend |
| 7.2 | Adicionar `getManualOrderStatus` em api.js | Complete | 2026-02-11 | |
| 7.3 | Criar mapa tradução erros Bybit pt-BR | Complete | 2026-02-11 | ~30 códigos + padrões textuais |
| 7.4 | Implementar polling em handleSubmit | Complete | 2026-02-11 | Polling 2s, max 15 tentativas, spinner |
| 7.5 | Build + restart serviços PM2 | Complete | 2026-02-11 | |
| 7.6 | Testes backend (28/28) | Complete | 2026-02-11 | |
| 7.7 | Documentação | Complete | 2026-02-11 | |

## Progress Log

### 2026-02-10
- Mapeamento completo do fluxo: backend executa com `setImmediate()`, retorna PENDING imediatamente
- Endpoint GET `/v1/orders/manual/:orderId` já existe e retorna todos campos de `signal_panel`
- Frontend (`multi-tp-trading-interface.tsx`) mostra PENDING e limpa após 3s sem polling
- `api.js` não tem método para consultar status individual de ordem
- Decisão: implementar polling no frontend, sem alterar backend

### 2026-02-11
- Implementado método `getManualOrderStatus` em `api.js`
- Criado mapa de tradução de erros Bybit (30+ códigos e padrões textuais)
- Implementado polling no `handleSubmit`: 2s intervalo, 15 tentativas, spinner visual
- Tratados status: EXECUTED, PARTIALLY_FILLED, ERROR, REJECTED, CANCELED, timeout
- Criados 28 testes backend (todos passando)
- Build frontend ok, PM2 restart ok
- Documentação criada em `docs/FEEDBACK_EXECUCAO_ORDENS_PAINEL_10_02_2026.md`
