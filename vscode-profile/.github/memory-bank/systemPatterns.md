# System Patterns: Starboy Postgres

**Última Atualização**: 26 de janeiro de 2026

## Arquitetura Geral

```
┌─────────────────────────────────────────────────────────┐
│                    Frontend (Next.js)                   │
│              Dashboard + User Interface                 │
└────────────────────────┬────────────────────────────────┘
                         │
        ┌────────────────┼────────────────┐
        │                │                │
┌───────▼────────┐  ┌────▼──────────┐  ┌─▼────────────────┐
│  REST API      │  │ WebSocket     │  │ Server-Side      │
│  (FastAPI)     │  │ (Real-time)   │  │ Actions (Next.js)│
└───────┬────────┘  └────┬──────────┘  └─┬────────────────┘
        │                │                │
        └────────────────┼────────────────┘
                         │
        ┌────────────────┼────────────────────────────────┐
        │                │                                │
┌───────▼─────────┐  ┌───▼──────────────┐  ┌────────────▼────┐
│  Backtester     │  │  Order Manager   │  │  Signal Pipeline│
│  (divap_bt.py)  │  │  (services/)     │  │  (telegram/)    │
└───────┬─────────┘  └───┬──────────────┘  └────────────┬────┘
        │                │                              │
        └────────────────┼──────────────────────────────┘
                         │
                    ┌────▼────────────┐
                    │  PostgreSQL     │
                    │  (Data Store)   │
                    └─────────────────┘
                         │
        ┌────────────────┼────────────────┐
        │                │                │
    ┌───▼──┐        ┌────▼────┐      ┌──▼────┐
    │ CCXT │        │ Telethon│      │ APIs  │
    │(Exch)│        │(Telegram)      │(Other)│
    └───┬──┘        └────┬────┘      └──┬────┘
        │                │              │
    ┌───▼────────────────▼──────────────▼────┐
    │     External Services (Exchanges, APIs) │
    └────────────────────────────────────────┘
```

## Padrões Arquiteturais

### 1. Separação de Camadas

#### Frontend Layer (Next.js)
- **Responsabilidade**: Interface de usuário, visualização, interação
- **Tecnologia**: React, TypeScript, Tailwind CSS
- **Padrões**: Component-based, hooks, server-side actions

#### API Layer (FastAPI/Express)
- **Responsabilidade**: Exposição de endpoints, validação, autorização
- **Tecnologia**: FastAPI (Python) ou Express (Node.js)
- **Padrões**: RESTful, middleware, error handling

#### Business Logic Layer
- **Backtesting**: `InteractiveBacktestEngine` (divap_backtest.py)
- **Trading**: `OrderManager`, strategy executors
- **Signals**: `TelegramSignalClient`, signal processors
- **Padrões**: Service layer, async/await, error handling

#### Data Layer
- **Banco de Dados**: PostgreSQL
- **Padrões**: ORM/SQL, migrations, connection pooling

### 2. Signal Processing Pipeline

```
Telegram → Telethon → Extract → Normalize → Validate → Store → Queue → Execute
                        ↓
                   Metadata
                   extraction
```

**Componentes**:
- `TelegramSignalClient`: Conecta e extrai mensagens
- `SignalProcessor`: Normalização e validação
- `SignalQueue`: Buffer para processamento
- `ExecutionEngine`: Dispara trades baseado em sinais

**Data Flow**:
1. Telethon itera mensagens do Telegram
2. Extrai pares, preços, direção (BUY/SELL/CLOSE)
3. Normaliza para formato padrão (OHLCV, meta)
4. Valida integridade (preços válidos, pares conhecidos)
5. Armazena em PostgreSQL
6. Enfileira para execução
7. OrderManager executa quando condições são atendidas

### 3. Backtesting Engine Architecture

```
Strategy Definition
        ↓
Period Selection (1=Custom, 2=YTD, 3=Since Beginning, 4-6=Last 30/60/90 days)
        ↓
Load Market Data (PostgreSQL or API)
        ↓
Signal Collection (Telegram or Database)
        ↓
Simulation Loop (Tick-by-tick or OHLC)
        ↓
Trade Execution Simulation
        ↓
Metrics Calculation
        ↓
Results & Analysis
```

**Classe Principal**: `InteractiveBacktestEngine`

**Métodos Críticos**:
- `get_signals_from_telegram()`: Coleta sinais com paginação inteligente
- `get_signals_from_database()`: Fallback para sinais armazenados
- `fetch_market_data_for_trade()`: Obtém dados OHLC
- `simulate_trade_real()`: Simula execução de trade
- `run()`: Loop principal de backtesting

**Period Choice Logic**:
- `period_choice = "1"`: Customizado (requer start_date + end_date)
- `period_choice = "2"`: Ano atual
- `period_choice = "3"`: Desde o início (sem limite de sinais)
- `period_choice = "4"`: Últimos 30 dias
- `period_choice = "5"`: Últimos 60 dias
- `period_choice = "6"`: Últimos 90 dias

### 4. Trading Execution Pattern

```
Signal Available
        ↓
Risk Check (Max positions, max drawdown, margin)
        ↓
Order Validation (Price, size, pair valid?)
        ↓
Place Order (CCXT API to Exchange)
        ↓
Monitor Position
        ↓
SL/TP Management
        ↓
Close or Hold
```

### 5. Data Consistency Patterns

#### Period & Date Handling
- **Conversão Type-Safe**: `period_choice_str = str(args.period_type or 1)`
- **Comparação String**: `if period_choice_str == "1"` (evita bugs de tipo)
- **Conversão de Volta**: `engine.period_choice = int(period_choice_str)`

#### Telegram Pagination
- **Smart Kwargs Construction**: Evita conflito offset_id vs offset_date
- **Batch Processing**: 1000 mensagens por batch
- **Reverse Chronological**: Carrega mensagens mais recentes primeiro

#### Database Integrity
- Foreign keys para relacionamentos
- Constraints para validação de dados
- Indexes para performance de queries críticas

## Decisões de Design Justificadas

### 1. Type-Safe Period Comparison
**Problema**: `args.period_type` pode ser int, string ou None  
**Solução**: Converter para string antes de comparação  
**Benefício**: Elimina bugs sutis de comparação de tipo  
**Custo**: Mínimo (uma conversão string)

### 2. Batch-Based Telegram Pagination
**Problema**: Telethon permite offset_id ou offset_date, não ambos  
**Solução**: Construir kwargs dinamicamente baseado em estado atual  
**Benefício**: Evita erros de API, maximiza velocidade  
**Custo**: Lógica um pouco mais complexa

### 3. Period Predefinition
**Problema**: Traders frequentemente usam períodos comuns  
**Solução**: Cache de períodos predefinidos com cálculo dinâmico  
**Benefício**: UX simplificada, performance melhorada  
**Custo**: Manutenção de lógica de período

### 4. Fallback para Database
**Problema**: Telegram pode ficar indisponível ou limitar acesso  
**Solução**: Se Telegram falha, busca sinais já armazenados  
**Benefício**: Resilência, operação contínua  
**Custo**: Sincronização database ↔ Telegram

## Padrões de Erro e Resiliência

### Error Handling Strategy
1. **Validação Preventiva**: Validar inputs antes de processar
2. **Fallback Automático**: Se Telegram falha → Database
3. **Logging Detalhado**: Registrar todo erro com contexto
4. **Retry Logic**: Retry em falhas temporárias (rate limit, timeout)
5. **Graceful Degradation**: Sistema funciona em modo reduzido se possível

### Retry Policy
- **Transient Errors**: Retry com exponential backoff (1s, 2s, 4s, 8s)
- **Permanent Errors**: Log e skip, continua com próximo item
- **Rate Limits**: Respeita rate limits de Telegram/APIs

## Padrões de Performance

### Backtesting
- **Batch Processing**: Processa múltiplos sinais em um loop
- **Lazy Loading**: Carrega dados sob demanda, não tudo de uma vez
- **Caching**: Cache de períodos predefinidos, dados de mercado

### Database
- **Indexes**: Sobre data, ticker, tipo_sinal
- **Connection Pooling**: Reutiliza conexões
- **Pagination**: Não carrega todos os registros de uma vez

### API
- **Response Compression**: Gzip para respostas grandes
- **Pagination**: Endpoint limita resultados (ex: 100 registros/página)
- **Caching Headers**: ETags, Last-Modified para respostas estáticas

## Extensibility Points

### Adicionar Novo Sinal Source
1. Criar nova classe herdando de `SignalSource`
2. Implementar `fetch_signals(period)`
3. Retornar em formato padronizado
4. Registrar em pipeline

### Adicionar Nova Exchange
1. CCXT já suporta 100+ exchanges
2. Configurar API key na env
3. Atualizar `OrderManager` se necessário
4. Testar em backtester

### Adicionar Novo Indicador
1. Implementar cálculo em `indicators/`
2. Criar testes unitários
3. Integrar em estratégia
4. Validar em backtester

## Riscos Técnicos Conhecidos

1. **Telethon Rate Limiting**: Telegram pode limitar requisições
   - Mitigação: Caching, retry automático, fallback para DB

2. **Data Consistency**: Sinais podem estar corrompidos ou incompletos
   - Mitigação: Validação rigorosa, checksums, auditoria

3. **Performance de Backtest**: Grandes períodos podem ser lentos
   - Mitigação: Batch processing, índices, otimização SQL

4. **Exchange Outages**: Exchanges podem estar indisponíveis
   - Mitigação: Retry automático, alerts, fallback para manual

## Evolução Arquitetural

### Curto Prazo (1-3 meses)
- Adicionar caching distribuído (Redis)
- Implementar message queue (RabbitMQ) para sinais
- Expandir cobertura de testes

### Médio Prazo (3-6 meses)
- Refatorar para microserviços (Backtester como serviço separado)
- Adicionar streaming de dados em tempo real (WebSocket)
- Implementar sharding para escalabilidade horizontal

### Longo Prazo (6+ meses)
- Machine learning para otimização de estratégias
- API pública para desenvolvedores terceiros
- Plataforma multi-tenant (SaaS)
