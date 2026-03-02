# [TASK003] Implementar Testes Automatizados

**Status**: In Progress  
**Adicionado**: 26 de janeiro de 2026  
**Atualizado**: 26 de janeiro de 2026  
**Prioridade**: 🔴 Alta  

---

## Original Request

Após correções de indentation e type-safety em `divap_backtest.py`, implementar testes automatizados para validar:
1. Lógica de período_choice (customizado vs predefinido)
2. Coleta e paginação de sinais Telegram
3. Integração com PostgreSQL
4. Execução de trades simulados

**Objetivo Final**: Expandir test coverage de ~20% para 70%

---

## Thought Process

### Análise Inicial
O projeto `divap_backtest.py` passou por correções críticas:
- 7 erros de indentation corrigidos
- Método `get_signals_from_telegram()` reimplementado com paginação otimizada
- Type-safe comparison de `period_choice` implementada

**Próximo passo lógico**: Validar essas mudanças com testes automatizados

### Decisões Arquiteturais

1. **Framework**: Usar `pytest` (já no requirements.txt)
2. **Estrutura**: Tests em `/tests/backend/`
3. **Padrão**: Arrange-Act-Assert (AAA)
4. **Cobertura**: Unitários + Integração
5. **Fixtures**: Compartilhar setup entre testes

### Priorização
1. **Fase 1** (URGENT): Testes de período_choice + get_signals_from_telegram
2. **Fase 2** (IMPORTANTE): Testes de integração PostgreSQL
3. **Fase 3** (IMPORTANTE): Testes de execução de trade
4. **Fase 4** (NICE-TO-HAVE): Testes E2E

---

## Implementation Plan

### Fase 1: Setup Pytest Infrastructure
- [ ] Criar `tests/backend/conftest.py` com fixtures compartilhadas
- [ ] Configurar `pytest.ini` com opções padrão
- [ ] Setup mock de banco de dados para testes
- [ ] Setup mock de Telethon client

### Fase 2: Testes de Período_Choice
- [ ] Test: `period_choice_str` conversão correta
- [ ] Test: Comparação string-based com valores 1-6
- [ ] Test: Conversão de volta para int
- [ ] Test: Edge cases (None, 0, valores inválidos)

### Fase 3: Testes de Telegram Signal Fetching
- [ ] Test: Paginação com offset_id
- [ ] Test: Paginação com offset_date
- [ ] Test: Batch size 1000 funcionando
- [ ] Test: Reverse chronological order
- [ ] Test: Tratamento de erros Telethon

### Fase 4: Testes de PostgreSQL Integration
- [ ] Test: Salvamento de sinais no banco
- [ ] Test: Busca de sinais por período
- [ ] Test: Fallback de Telegram para DB

### Fase 5: Testes de Trade Execution
- [ ] Test: Simulação de trade com preço
- [ ] Test: Cálculo de PnL
- [ ] Test: Aplicação de SL/TP
- [ ] Test: Múltiplas posições simultâneas

### Fase 6: Performance & Cobertura
- [ ] Executar coverage report
- [ ] Ajustar para 70%+
- [ ] Otimizar testes lentos

---

## Progress Tracking

**Overall Status**: 0% Iniciado

### Subtasks

| ID | Descrição | Status | Atualizado | Notas |
|----|-----------|--------|-----------|-------|
| 3.1 | Setup conftest.py e fixtures | Not Started | 26/01 | Aguardando início |
| 3.2 | Criar pytest.ini config | Not Started | 26/01 | Config padrão |
| 3.3 | Testes de period_choice string conversion | Not Started | 26/01 | Unit tests |
| 3.4 | Testes de period_choice comparison logic | Not Started | 26/01 | Unit tests |
| 3.5 | Mock de Telethon para testes | Not Started | 26/01 | Preparação para 3.6+ |
| 3.6 | Testes de get_signals_from_telegram paginação | Not Started | 26/01 | Integration-style |
| 3.7 | Testes de trim.offset_id vs offset_date kwargs | Not Started | 26/01 | Lógica crítica |
| 3.8 | Mock de PostgreSQL para testes | Not Started | 26/01 | Setup integração |
| 3.9 | Testes de fallback DB se Telegram falha | Not Started | 26/01 | Error handling |
| 3.10 | Testes de trade execution simulation | Not Started | 26/01 | Lógica crítica |
| 3.11 | Executar coverage report | Not Started | 26/01 | Métrica de sucesso |
| 3.12 | Ajustar testes para atingir 70% coverage | Not Started | 26/01 | Final target |

---

## Progress Log

### 26 de janeiro de 2026
- **11:00** - Tarefa criada e planejamento definido
- **Próximo passo**: Iniciar Fase 1 (Setup Pytest Infrastructure)

---

## Dependências

- ✅ pytest (já no requirements.txt)
- ✅ pytest-asyncio (para testes assync)
- ✅ pytest-cov (para coverage reports)
- 📋 Mock de Telethon (será necessário criar)
- 📋 Mock de PostgreSQL (usar testcontainers ou SQLite)

## Acoplamentos

- **Arquivos principais**: 
  - `/home/ubuntu/atius/backend/backtest/divap_backtest.py`
  - `/home/ubuntu/atius/tests/backend/`
  
- **Classes criticamente testadas**:
  - `InteractiveBacktestEngine`
  - `_FallbackPeriodManager`
  - `get_signals_from_telegram()`
  - `simulate_trade_real()`

## Riscos Identificados

1. **Async Complexity**: `get_signals_from_telegram()` é async, testes precisam de pytest-asyncio
2. **Telethon Mocking**: Difícil mockar cliente Telethon (há dependências internas)
3. **DB Setup**: PostgreSQL em testes pode ser lento, considerar SQLite para unit tests
4. **Flakiness**: Testes de timeout/retry podem ser intermitentes

**Mitigação**:
- Use fixtures de pytest-asyncio
- Mock Telethon em nível de função (iter_messages)
- Use testcontainers para PostgreSQL apenas em testes de integração
- Use deterministic timeouts, evitar sleep() em testes

---

## Critérios de Sucesso

✅ **Sucesso Completo**:
1. Todos os 12 subtasks marcados como Complete
2. Coverage report >= 70% para divap_backtest.py
3. Todos os testes passando (pytest run com sucesso)
4. Documentação de testes criada
5. CI/CD pipeline validando testes (se aplicável)

⚠️ **Sucesso Parcial** (accept if):
- Coverage >= 60%
- Testes críticos (period_choice, signals) 100% completos
- Testes de trade execution começados

❌ **Falha**:
- Coverage < 50%
- Testes falhando consistentemente
- Bloqueador não documentado

---

## Continuação Esperada

**Próximo passo após TASK003**:
- TASK002: Validação de Integridade de Dados
- TASK001: Executar Validação de Backtesting
