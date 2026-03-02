# Tech Context: Starboy Postgres

**Última Atualização**: 26 de janeiro de 2026

## Stack Tecnológico Principal

### Backend
| Componente | Tecnologia | Versão | Uso |
|----------|-----------|--------|-----|
| Linguagem | Python | 3.8+ | Lógica principal, backtesting |
| Runtime | Node.js | 18+ | Webhooks, APIs complementares |
| Banco de Dados | PostgreSQL | 12+ | Armazenamento relacional |
| ORM | SQLAlchemy | 2.0+ | Mapeamento objeto-relacional |
| Async | asyncio + aiohttp | Native | I/O não-bloqueante |
| Task Queue | Celery/RQ | Variável | Agendamento de jobs |

### Frontend
| Componente | Tecnologia | Versão | Uso |
|----------|-----------|--------|-----|
| Framework | Next.js | 14+ | SSR, SSG, API routes |
| Styling | Tailwind CSS | 3.x | Estilização responsiva |
| Linguagem | TypeScript | 5+ | Type safety |
| Estado | React Hooks | Built-in | Gerenciamento de estado |
| Build | Webpack/Turbopack | Built-in | Bundling e hot reload |

### Integrações Externas
| Serviço | Tecnologia | Uso |
|---------|-----------|-----|
| Exchanges | CCXT | Trading multi-corretora |
| Binance | REST API + WebSocket | Trading, dados |
| Bybit | REST API | Trading |
| MEXC | REST API | Trading |
| Telegram | Telethon | Coleta de sinais |

### Bibliotecas Críticas
```python
# Backend
telethon==1.29.x          # Telegram client
ccxt==4.x                 # Unified exchange API
sqlalchemy==2.x           # ORM
psycopg2-binary           # PostgreSQL driver
pandas==2.x               # Data analysis
numpy==1.x                # Numerical computing
vectorbt==0.25.x          # Backtesting optimization
python-dateutil           # Date utilities
pytz                      # Timezone handling

# Testing
pytest==7.x
pytest-asyncio
pytest-cov

# Utilities
python-dotenv             # Environment management
pydantic==2.x             # Data validation
```

## Configuração de Desenvolvimento

### Ambiente Local
```bash
# Clone e setup
git clone <repo>
cd atius
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# PostgreSQL
# Criar banco: createdb atius_dev
# Migrations: alembic upgrade head

# Frontend
cd frontend
npm install
npm run dev

# Backend
python backend/server/main.py
```

### Variáveis de Ambiente
```
# Database
DATABASE_URL=postgresql://user:pass@localhost:5432/atius_dev

# Telegram
TELEGRAM_API_ID=<YOUR_API_ID>
TELEGRAM_API_HASH=<YOUR_API_HASH>
TELEGRAM_SESSION_NAME=my_account

# Exchanges
BINANCE_API_KEY=<KEY>
BINANCE_SECRET=<SECRET>
BYBIT_API_KEY=<KEY>
BYBIT_SECRET=<SECRET>
MEXC_API_KEY=<KEY>
MEXC_SECRET=<SECRET>

# Server
API_HOST=0.0.0.0
API_PORT=8000
FRONTEND_URL=http://localhost:3000

# Mode
BACKTEST_NON_INTERACTIVE=0  # 1 para CLI automático
DEBUG=true
```

## Estrutura de Código Principal

### Backend Structure
```
backend/
├── backtest/
│   ├── divap_backtest.py       # InteractiveBacktestEngine (4432 linhas)
│   └── ...
├── exchanges/
│   ├── base.py                 # Classe base para exchanges
│   ├── binance.py
│   ├── bybit.py
│   └── mexc.py
├── indicators/
│   ├── technical.py            # SMA, EMA, RSI, MACD
│   ├── volume.py
│   └── custom.py
├── services/
│   ├── order_manager.py        # Gerenciamento de ordens
│   ├── position_manager.py     # Rastreamento de posições
│   ├── risk_manager.py         # Validação de riscos
│   └── strategy_executor.py
├── telegram/
│   ├── client.py               # TelegramSignalClient
│   ├── signal_processor.py     # Normalização de sinais
│   └── handlers.py
├── server/
│   ├── main.py                 # FastAPI app
│   ├── routes/
│   │   ├── backtest.py
│   │   ├── trades.py
│   │   ├── signals.py
│   │   └── accounts.py
│   └── middleware/
├── utils/
│   ├── database.py             # Conexão PostgreSQL
│   ├── logger.py
│   ├── validators.py
│   └── helpers.py
└── config/
    └── settings.py
```

### Frontend Structure
```
frontend/
├── app/
│   ├── layout.tsx
│   ├── page.tsx
│   ├── dashboard/
│   │   ├── page.tsx
│   │   ├── components/
│   │   │   ├── PositionsTable.tsx
│   │   │   ├── PerformanceChart.tsx
│   │   │   └── ...
│   │   └── actions.ts          # Server-side actions
│   ├── backtest/
│   │   ├── page.tsx
│   │   └── components/
│   ├── signals/
│   │   ├── page.tsx
│   │   └── components/
│   └── api/
│       └── routes
├── components/
│   ├── Navigation.tsx
│   ├── Sidebar.tsx
│   └── common/
├── lib/
│   ├── api.ts                  # API client
│   ├── hooks.ts
│   └── utils.ts
├── styles/
│   └── globals.css
├── public/
└── next.config.js
```

## Pontos de Integração Críticos

### 1. Telethon → PostgreSQL
**Arquivo**: `backend/backtest/divap_backtest.py::get_signals_from_telegram()`
- Extrai mensagens do Telegram em batches de 1000
- Processa em reverse chronological order
- Normaliza para formato padrão
- Salva em tabela `signals`
- **Type-Safety**: period_choice_str para evitar bugs

### 2. PostgreSQL → Backtesting
**Arquivo**: `backend/backtest/divap_backtest.py::fetch_market_data_for_trade()`
- Carrega OHLC histórico de banco
- Filtra por período de backtest
- Retorna DataFrame para simulação
- **Otimização**: Batch loading, indexes em data/ticker

### 3. Order Execution → Exchange APIs
**Arquivo**: `backend/services/order_manager.py`
- Valida ordem contra limites de risco
- Executa via CCXT para exchange específica
- Armazena resultado em PostgreSQL
- **Resilência**: Retry automático, fallback

### 4. Real-Time Data → Frontend
**Arquivo**: `backend/server/routes/trades.py` + WebSocket
- API poll cada 5 segundos (ou WebSocket contínuo)
- Dados de posições abertas
- Atualiza dashboard em tempo real
- **Performance**: Paginação, caching de respostas

## Restrições Técnicas

### 1. Telegram API Limits
- **Rate Limit**: ~5000 mensagens por chat por dia
- **Workaround**: Cache local, fallback para DB
- **Documentação**: Respectar delays entre requisições

### 2. PostgreSQL Constraints
- **Conexões**: Pool de 20-50 conexões
- **Max Query Time**: Timeout em 30 segundos
- **Storage**: Arquivar dados > 2 anos

### 3. Exchange Rate Limits
- **Binance**: 1200 requests/min (API)
- **Bybit**: 1000 requests/min
- **MEXC**: 500 requests/min
- **Workaround**: Rate limiting cliente-side, queue

### 4. Memory Constraints
- **Backtester**: Carregar máx 1 ano de dados por rodada
- **Frontend**: Lazy load de dados históricos
- **Cache**: TTL máximo 1 hora para dados em tempo real

## Dependências Externas

### Críticas (Single Point of Failure)
1. **PostgreSQL**: Armazenamento de todos os dados
2. **Telegram**: Coleta de sinais (fallback: DB)
3. **Exchanges**: Execução de trades

### Secundárias
1. **Redis** (opcional): Caching e session management
2. **RabbitMQ** (opcional): Message queue para tasks

## Setup do Banco de Dados

### Migrations
```bash
# Criar nova migration
alembic revision --autogenerate -m "desc"

# Aplicar
alembic upgrade head

# Rollback
alembic downgrade -1
```

### Principais Tabelas
```sql
-- Sinais
signals (id, timestamp, ticker, direction, entry_price, take_profit, stop_loss)

-- Trades Executados
trades (id, signal_id, exchange, order_id, entry_price, exit_price, pnl)

-- Posições Abertas
positions (id, exchange, ticker, side, size, entry_price, current_price)

-- Histórico de Backtests
backtest_results (id, strategy, period, start_date, end_date, total_return, sharpe_ratio)

-- Accounts/Wallets
accounts (id, exchange, api_key_hash, balance, equity, margin_used)
```

## Performance Benchmarks (Target)

| Métrica | Target | Atual | Status |
|---------|--------|-------|--------|
| Backtest 1 ano | < 30s | ~45s | 🔴 |
| Coleta sinais Telegram | < 5s | ~8s | 🔴 |
| Execução de trade | < 2s | ~1.5s | 🟢 |
| API response (avg) | < 100ms | ~150ms | 🟡 |
| Uptime | 99.5% | 97% | 🟡 |

## Tooling e DevOps

### Local Development
- **IDE**: VSCode com Python extension, Pylance
- **Linting**: Pylance, Black, Flake8
- **Debugging**: pdb, VSCode debugger
- **Database**: DBeaver (GUI), psql (CLI)

### Testing
- **Unit Tests**: pytest + pytest-asyncio
- **Integration Tests**: pytest + testcontainers (PostgreSQL)
- **E2E Tests**: Playwright (frontend)
- **Load Tests**: k6, Locust

### Monitoring & Logging
- **Logs**: Python logging, estruturado em JSON
- **Metrics**: Prometheus (optional)
- **Traces**: OpenTelemetry (optional)

### CI/CD
- **VCS**: Git (GitHub/GitLab)
- **CI**: GitHub Actions
- **Artifact Registry**: Docker Hub ou GitHub Container Registry

## Roadmap Técnico

### Q1 2026
- [ ] Implementar Redis para caching
- [ ] Adicionar message queue (RabbitMQ)
- [ ] Expand test coverage a 70%+
- [ ] Otimizar queries PostgreSQL

### Q2 2026
- [ ] Refatorar para arquitetura de microsserviços
- [ ] Adicionar WebSocket para real-time data
- [ ] Implementar CI/CD pipeline completo
- [ ] Suportar mais 5 exchanges

### Q3 2026
- [ ] Machine learning para signal processing
- [ ] Backtesting em GPU (RAPIDS)
- [ ] API pública para desenvolvedores
- [ ] Multi-tenant SaaS

## Links Importantes

- **PostgreSQL Docs**: https://www.postgresql.org/docs/
- **CCXT Docs**: https://docs.ccxt.com/
- **Telethon Docs**: https://docs.telethon.dev/
- **Next.js Docs**: https://nextjs.org/docs
- **SQLAlchemy Docs**: https://docs.sqlalchemy.org/
- **Pydantic Docs**: https://docs.pydantic.dev/
