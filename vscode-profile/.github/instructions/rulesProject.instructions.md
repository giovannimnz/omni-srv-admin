---
applyTo: '**'
---
## Sobre o Projeto


Este repositório é dedicado ao desenvolvimento do **Starboy Postgres**, um software completo e modular para trading automatizado em futuros, com suporte a múltiplas corretoras (Binance, Bybit, MEXC), uso intensivo de Python, Node.js e PostgreSQL. O sistema abrange desde a coleta e tratamento de dados de mercado, execução e automação de estratégias, integração com APIs de exchanges, até rotinas de monitoramento, análise e backtesting (o backtest é apenas uma das funções do sistema).

**Principais características:**
- Trading automatizado em futuros (multi-corretora: Binance, Bybit, MEXC)
- Execução, automação e monitoramento de estratégias quantitativas
- Backtest e simulação de estratégias (função do sistema)
- Infraestrutura de banco de dados relacional (PostgreSQL)
- Scripts de automação, correção e validação de dados
- Frontend em Next.js/Tailwind para dashboards e monitoramento
- Estrutura de testes automatizados para backend, frontend e scripts de fix

**Público-alvo:**
Desenvolvedores, traders quantitativos, analistas de dados e entusiastas de automação financeira.

**Objetivo:**
Prover uma base robusta, auditável e extensível para operação, desenvolvimento e validação de estratégias quantitativas em múltiplas exchanges de futuros, com ênfase em qualidade de dados, automação e integração contínua.

---

Todos os testes/e/ou debug, check, diagnostic, diadgnostics, tudo que for referente verificação, análise ou teste/debug devem ser salvos sempre em: `tests/`, na pasta ou subpasta correspondente que mais fizer sentido conforme o contexto, inclusive, sempre antes de criar um novo teste ou debug, consulta lá na pasta ou subpastas se o referido já não existe, caso ele exista, apenas inclua um novo cenário, ou edite o arquivo, para não ficar sempre criando novos arquivos sem necessidade, procure ser o mais eficiente possível, fix em `tests/fix/`, backend em `tests/backend/`, frontend em `tests/frontend/`, quanto as docs, sempre em `docs`, tanto arquivos de correção, quanto summary, praticamente tudo que tu for gerar em `*.md` etc.

Sempre responda em português brasileiro. A menos que o usuário solicite especificamente outro idioma, todas as respostas devem ser fornecidas em português brasileiro.

