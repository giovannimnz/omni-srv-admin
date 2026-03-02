# Product Context: Starboy Postgres

**Última Atualização**: 26 de janeiro de 2026

## Por Que Este Projeto Existe

Traders quantitativos e investidores automatizados precisam de uma solução confiável, auditável e extensível para:
1. Executar estratégias de trading em múltiplas exchanges simultaneamente
2. Validar estratégias através de backtesting preciso antes de colocá-las em produção
3. Monitorar posições e performance em tempo real
4. Integrar sinais de múltiplas fontes (Telegram, APIs, análise técnica)
5. Manter histórico completo e auditável de todas as operações

## Problemas que Resolve

### 1. Fragmentação de Dados
**Problema**: Traders gastam tempo sincronizando dados entre exchanges, análise e execução  
**Solução**: Starboy centraliza tudo em PostgreSQL com sincronização automática

### 2. Validação de Estratégias
**Problema**: Testar estratégias manualmente é impreciso e consome tempo  
**Solução**: Motor de backtesting com simulação precisa de mercado, suportando múltiplas corretoras

### 3. Risco de Operação Manual
**Problema**: Trading manual está propenso a erros e perdas por emoção  
**Solução**: Automação de estratégias com limites de risco e monitoramento contínuo

### 4. Perda de Auditoria
**Problema**: Histórico incompleto de trades, sinais e decisões  
**Solução**: Registro completo e rastreável de todas as operações no PostgreSQL

### 5. Integração com Múltiplas Fontes
**Problema**: Sinais chegam de Telegram, APIs, análise técnica - sem integração  
**Solução**: Pipeline unificado que absorve sinais de múltiplas fontes e executa de forma coordenada

## Como Deve Funcionar (Fluxo Principal)

### Fluxo 1: Coleta e Armazenamento de Sinais
```
Telegram Groups → Telethon Client → Signal Processing → PostgreSQL
     ↓
Normalization & Validation
     ↓
Signal Storage (signals table)
```

### Fluxo 2: Backtesting de Estratégias
```
Strategy Definition → Load Historical Data → Simulate Trades → Calculate Metrics
                         (PostgreSQL)         (InteractiveBacktestEngine)     (Pandas)
                     ↓
                 Backtest Results
```

### Fluxo 3: Execução de Trades
```
Signal Triggers → Risk Validation → Order Placement → Order Management → Position Tracking
                 (Limites)         (CCXT/APIs)      (Order Status)      (PostgreSQL)
                     ↓
            Performance Monitoring
```

### Fluxo 4: Monitoramento Dashboard
```
PostgreSQL ← Live Data Updates ← Real-time APIs
     ↓
Dashboard (Next.js) → User Interface
     ↓
Alerts & Notifications
```

## Objetivos de Experiência do Usuário

### Para Trader Quantitativo
- ✅ Definir estratégias com clareza matemática
- ✅ Testar estratégias em dados históricos rapidamente
- ✅ Confiar que o backtesting reflete a realidade de mercado
- ✅ Ativar automação com confiança
- ✅ Monitorar performance em tempo real
- ✅ Acessar histórico completo de operações para análise

### Para Desenvolvedor
- ✅ Entender a arquitetura do sistema rapidamente
- ✅ Adicionar novas estratégias facilmente
- ✅ Integrar novas corretoras sem reescrever tudo
- ✅ Testar mudanças antes de deployar
- ✅ Confiar que o sistema é confiável e auditável

### Para Analyst de Risco
- ✅ Rastrear cada trade e sua origem
- ✅ Validar que riscos estão sendo respeitados
- ✅ Identificar padrões de perda rapidamente
- ✅ Acessar relatórios de performance detalhados
- ✅ Auditar integridade histórica de dados

## Características Principais

### 1. Trading Multi-Broker
- Suporte nativo para Binance, Bybit, MEXC
- Abstração de API via CCXT
- Execução coordenada entre exchanges
- Gerenciamento centralizado de posições

### 2. Motor de Backtesting
- Simulação precisa de condições de mercado
- Suporte a múltiplos timeframes
- Análise de riscos (drawdown, Sharpe ratio, etc)
- Validação de estratégias antes de produção

### 3. Pipeline de Sinais
- Integração com Telegram para sinais
- Normalização de dados de múltiplas fontes
- Validação e filtro de sinais
- Histórico completo armazenado

### 4. Dashboard de Monitoramento
- Visão em tempo real de posições abertas
- Histórico de trades executados
- Métricas de performance (PnL, taxa de acerto)
- Alertas configuráveis

### 5. Automação
- Execução automática baseada em sinais
- Limites de risco (max drawdown, max loss)
- Gerenciamento automático de take-profit/stop-loss
- Retry automático em caso de falhas

## Princípios de Design

### Confiabilidade
- Armazenamento durável em PostgreSQL
- Histórico completo e auditável
- Recuperação de falhas automática

### Escalabilidade
- Arquitetura preparada para múltiplos traders
- Suporte a múltiplas estratégias simultâneas
- Processamento paralelo onde possível

### Transparência
- Logs detalhados de todas as operações
- Rastreamento completo de sinais → trades
- Relatórios de performance clara

### Flexibilidade
- Fácil adicionar novas estratégias
- Suporte a múltiplas corretoras
- Customização de parâmetros por trader

## Métricas de Sucesso

1. **Taxa de Execução**: 99%+ de sinais executados com sucesso
2. **Precisão de Backtest**: Resultado de backtest vs resultado real ≤ 5%
3. **Disponibilidade**: 99.5%+ uptime
4. **Tempo de Resposta**: Execução de trade em < 2 segundos
5. **Integridade de Dados**: 100% de trades registrados corretamente

## Visão de Futuro

- Integração com mais exchanges (Kraken, Coinbase, dYdX)
- Machine learning para otimização de estratégias
- Backtesting em GPU para velocidade massiva
- API pública para integrações de terceiros
- Plataforma SaaS para múltiplos usuários
