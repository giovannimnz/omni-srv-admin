# Project Brief: Starboy Postgres

**Última Atualização**: 26 de janeiro de 2026

## Descrição Geral

**Starboy Postgres** é um sistema completo de trading automatizado em futuros com suporte a múltiplas corretoras (Binance, Bybit, MEXC). O sistema integra coleta de dados de mercado, automação de estratégias quantitativas, backtesting, monitoramento em tempo real e um dashboard de gerenciamento.

## Objetivos Primários

1. **Execução e Automação de Estratégias**: Implementar trading automatizado em futuros com suporte a múltiplas exchanges
2. **Qualidade de Dados**: Garantir integridade, consistência e auditabilidade dos dados de mercado
3. **Backtesting Robusto**: Validar estratégias com simulação precisa de mercado
4. **Monitoramento em Tempo Real**: Dashboard para acompanhar posições, sinais e performance
5. **Escalabilidade**: Arquitetura preparada para múltiplos traders e estratégias simultâneas

## Stack Tecnológico

### Backend
- **Python 3.x**: Lógica principal, backtesting, automação
- **Node.js**: Processamento assíncrono, webhooks, APIs complementares
- **PostgreSQL**: Armazenamento relacional de dados, sinais, históricos

### Frontend
- **Next.js**: Framework React com SSR
- **Tailwind CSS**: Estilização responsiva
- **JavaScript/TypeScript**: Lógica cliente-side

### Integrações
- **Telethon**: Coleta de sinais de grupos Telegram
- **CCXT**: Integração com APIs de exchanges
- **Binance, Bybit, MEXC APIs**: Trading direto

## Escopo Principal

### Módulos Backend
1. **backtest/**: Motor de backtesting interativo (divap_backtest.py)
2. **exchanges/**: Conexões com APIs de corretoras
3. **indicators/**: Cálculos de indicadores técnicos
4. **services/**: Serviços de negócio (estratégias, gerenciamento de posições)
5. **server/**: API REST e servidor web
6. **telegram/**: Integração com Telegram para sinais
7. **utils/**: Utilitários compartilhados

### Frontend
- Dashboard de monitoramento
- Gerenciamento de estratégias
- Histórico de trades
- Análise de performance

## Estrutura do Repositório

```
atius/
├── backend/              # Código Python principal
│   ├── backtest/        # Motor de backtesting
│   ├── exchanges/       # Integração com exchanges
│   ├── indicators/      # Indicadores técnicos
│   ├── services/        # Serviços de negócio
│   ├── server/          # API REST
│   ├── telegram/        # Integração Telegram
│   └── utils/           # Utilitários
├── frontend/            # Código Next.js
├── tests/               # Testes automatizados
├── docs/                # Documentação
└── .github/memory-bank/ # Banco de memória do projeto
```

## Status Atual

### Fase: OTIMIZAÇÃO E INTEGRAÇÃO CONTÍNUA
- ✅ Sistema de trading multi-broker funcionando
- ✅ Backtester interativo operacional
- ✅ Integração com Telegram para sinais
- 🔄 Correções e refinamentos contínuos
- 📋 Testes automatizados sendo expandidos

### Últimas Correções Aplicadas (26/01/2026)
1. Correção de indentation em 7 linhas do InteractiveBacktestEngine
2. Reimplementação de `get_signals_from_telegram()` com paginação otimizada
3. Correção de comparação de `period_choice` em `main_cli()` com type-safety

## Próximas Prioridades

1. **Testes Automatizados**: Expand test coverage para backend e frontend
2. **Documentação**: Consolidar documentação técnica e de usuário
3. **Performance**: Otimizar queries de banco de dados e lógica de backtesting
4. **Integração Contínua**: Implementar CI/CD pipeline
5. **Validação de Dados**: Fortalecer validação de integridade em signals e trades

## Contatos e Recursos

- **Repositório**: /home/ubuntu/atius
- **Banco de Dados**: PostgreSQL (configuração em config/)
- **Documentação**: /docs
- **Testes**: /tests
