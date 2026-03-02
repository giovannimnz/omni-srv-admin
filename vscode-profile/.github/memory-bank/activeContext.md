# Active Context: Starboy Postgres

**Data**: 16 de fevereiro de 2026
**Fase**: Migração Infra/PM2/Postgres para Atius ✅ CONCLUÍDO

## Sessão Atual (16/02/2026) - Infra + Banco + PM2

### O que foi feito:

1. ✅ **Rebranding e alinhamento de portas**
   - `config/.env`: produção em `API_PORT=8015` e `FRONTEND_PORT=3015`
   - `ecosystem.config.js`: processo `bybit-atius-8`, frontend em `3015`
   - `ecosystem.testnet.config.js`: `DB_NAME=AtiusDev`, caminhos ajustados para `/home/ubuntu/GitHub/ats`

2. ✅ **Scripts PostgreSQL reconstruídos (`scripts/postgres`)**
   - Backup com validação (`dump + toc + sha256 + meta`)
   - Restore com verificação de checksum/TOC, recriação de banco e validação pós-restore
   - Scripts de manutenção vacuum/reindex parametrizados

3. ✅ **Execução real de migração de banco**
   - Backup gerado: `horistic-20260216-200537.dump`
   - Restore concluído em `AtiusPrd` e `AtiusDev`
   - Paridade de dados validada por contagem exata por tabela: `ROW_COUNT_PARITY=OK`

4. ✅ **PM2 ATS em execução**
   - Stack `atius-*` iniciada
   - Processos legados `horistic-*` removidos
   - `atius-api` ouvindo em `8015`, `atius-web` ajustado para `3015`

5. ✅ **Docs de infraestrutura atualizados**
   - Arquivos `HORISTIC` renomeados para `ATIUS`
   - Conteúdo de Apache/domínios atualizado para estado atual

## Foco de Trabalho Atual

### Sessão Atual (16/02/2026) - Reorganização Geral de docs/ e tests/

#### O que foi feito:

1. ✅ **Reorganização completa da pasta docs/** (161 arquivos)
   - Criada estrutura hierárquica: architecture/, backend/, changelog/, guides/, infrastructure/, validation/, assets/
   - 35 docs de correções → `changelog/fixes/`
   - 17 docs de features → `changelog/features/`
   - 4 docs de migrações → `changelog/migrations/`
   - 10 docs de refatoração → `changelog/refactoring/`
   - 14 guias → `guides/`
   - 7 validações → `validation/`
   - 15 configs de infra → `infrastructure/`
   - 17 assets (logos/ícones) → `assets/`
   - Removidos: `_Colar.txt`, `gemini.md`, `backups/`, logs, arquivos .backup duplicados

2. ✅ **Reorganização completa da pasta tests/** (271 arquivos)
   - `tests/bybit/` mesclado em `tests/backend/exchanges/bybit/`
   - `tests/python/` mesclado em `tests/backend/updaters/`
   - `websocketHandlers/` renomeado para `websocket/`
   - Testes de API → `backend/api/`
   - Testes de serviços → `backend/services/`
   - Testes de indicadores → `indicators/unit/` e `indicators/integration/`
   - Frontend organizado: `e2e/`, `unit/`, `integration/`
   - Caches `__pycache__` removidos

3. ✅ **READMEs Criados**
   - `docs/README.md` - Índice completo com links e convenções
   - `tests/README.md` - Estrutura, como executar, onde colocar novos testes

---

### Sessão Anterior - TASK009 Fase 2: Validação Telegram e Correções DVAP

#### O que foi feito:

1. ✅ **Corrigidos 6 Erros Pylance em divap_signal_generator.py**
   - 4x `reportArgumentType` (df.at[] em vez de df.iloc[get_loc()])
   - 2x `reportUnusedImport` (timedelta, Decimal removidos)

2. ✅ **Validação contra 71 Sinais Telegram**
   - Script: `tests/indicators/test_divap_telegram_validation.py` (~700 linhas)
   - Canal: -1003389775541 (17 símbolos, 3 TFs, 48 BUY / 23 SELL)
   - Fórmulas: Entry 96.9%, SL 100%, TP 100% confirmadas

3. ✅ **Diagnóstico DVAP por Componente**
   - D (Divergência): 26.9% → 64.2% (+138%)
   - V (Volume): 100% (OK)
   - A (Fibonacci): 73.1% → 89.6% (+22%)
   - P (Padrão): 38.8% → 83.6% (+115%)
   - DVAP combinado: 4.5% → 47.8% (+962%)

4. ✅ **4 Correções Aplicadas a 3 Arquivos**
   - Desacoplamento RSI/Preço na divergência
   - Persistência 12→20 bars
   - Pin Bar, Inside Bar, thresholds RSI relaxados
   - Fibonacci proximidade 1%→2%
   - Arquivos: divap_signal_generator.py, divap_strategy.pine, divap.pine

#### Comandos PM2 de Referência
```bash
# Backend
cd /home/ubuntu/atius
pm2 restart atius-api

# Frontend
cd /home/ubuntu/atius/frontend
pm2 restart atius-web
```

## Mudanças Recentes

### Código Modificado (Phase 2.1)
- **Arquivo**: `/home/ubuntu/atius/backend/backtest/divap_backtest.py`
- **Linhas Alteradas**: 
  - 229: Constante MAXIMUM_ENTRY_PCT removida/comentada
  - 1698: create_backtest_execution atualizado (max_entry_pct=0.0)
  - 3342: Limitação min(final_capital_pct, MAXIMUM_ENTRY_PCT) removida
  - 3934-3940: period_choice_str com type safety
  - 4032: args.maximum_entry_pct removido do global override
- **Total de Linhas**: 4374

### Documentação Criada
- `/home/ubuntu/atius/docs/CORRECAO_MAXIMUM_ENTRY_PCT_FINAL.md`
  - Análise completa do problema
  - Before/After de todas as correções
  - Impacto esperado na alavancagem
  - Próximos passos para validação

### Testes Criados
- `/home/ubuntu/atius/tests/backend/test_maximum_entry_pct_removal.py`
  - 6 testes automatizados validando correções
  - Resultado: ✅ 6/6 passando

### Padrões Aplicados
1. **Type Safety**: Conversão explícita de tipos em comparações (string vs int)
2. **Robustness**: Tratamento inteligente de kwargs Telethon
3. **Performance**: Batch size otimizado (2000)
4. **No Artificial Limits**: Alavancagem dinâmica sem teto de 5%
   - Status: Corrigido - Pylance: 0 erros

5. ✅ **SQL Table Name em index.js**
   - Erro: `SELECT * FROM backtests` (tabela não existe)
   - Solução: Mudado para `FROM backtest_results` (linha 183)
   - Status: Corrigido - Syntax OK

## Próximos Passos

### Fase Imediata: VALIDAÇÃO TRADINGVIEW
1. **Testar Pine Script Atualizado no TradingView**
   - Copiar `divap_strategy.pine` atualizado para o TradingView
   - Verificar se gera sinais com a divergência desacoplada
   - Comparar sinais gerados com histórico do Telegram

2. **Melhorar Generator Match Rate (se necessário)**
   - 25% dos sinais (_VAP) ainda não ativam divergência
   - Considerar modo DVA (sem exigir todos os 4 componentes)
   - Avaliar relaxamento adicional de pivot params (pivLeft=3/pivRight=1)

### Fase Secundária: TESTES E VALIDAÇÃO
1. **Testes de Backtesting** com períodos variados
2. **Testes de Integração** PostgreSQL → Backtester
3. **Testes Automatizados** expandir coverage
4. **Documentação** dos novos fluxos

## Decisões Ativas

1. **Divergência Desacoplada**: Pivots RSI rastreados independentemente do preço
2. **Fibonacci 2%**: Proximidade aumentada para melhor cobertura
3. **Padrões Expandidos**: Pin Bar e Inside Bar adicionados
4. **Type Safety**: df.at[df.index[i]] em vez de df.iloc[get_loc()]

## Bloqueadores Conhecidos

- Generator match rate 16.9% (limitação inerente Python vs TradingView)
- 25% dos sinais Telegram não ativam divergência mesmo com fix

## Métricas e Health

- **Pylance Errors**: 0 ✅
- **Syntax Errors**: 0 ✅
- **Fórmulas Entry/SL/TP**: 96.9-100% ✅
- **DVAP Activation**: 47.8% (antes 4.5%)
- **Generator Match**: 16.9% (antes 0%)

## Links Relacionados

- Memory Bank: `.github/memory-bank/`
- Código Principal: `backend/backtest/divap_backtest.py`
- Signal Generator: `backend/indicators/divap_signal_generator.py`
- Pine Script: `backend/indicators/pine/divap_strategy.pine`
- Validação Telegram: `tests/indicators/test_divap_telegram_validation.py`
- Relatório: `docs/VALIDACAO_DIVAP_TELEGRAM_16_02_2026.md`
