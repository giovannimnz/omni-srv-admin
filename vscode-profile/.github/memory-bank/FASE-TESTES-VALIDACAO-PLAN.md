# Próxima Fase: TESTES E VALIDAÇÃO

**Fase Iniciada**: 26 de janeiro de 2026  
**Objetivo**: Implementar testes automatizados e validações de integridade  
**Duration**: ~2 semanas (até 09/02/2026)  
**Success Metric**: 70% test coverage, 0 data integrity issues

---

## 📋 Checklist Geral da Fase

### Semana 1 (26/01 - 02/02)
- [ ] **TASK003.1-3.5**: Setup Pytest infrastructure
  - [ ] conftest.py com fixtures
  - [ ] pytest.ini configurado
  - [ ] Mocks de Telethon e PostgreSQL prontos
  
- [ ] **TASK003.6-3.10**: Escrever testes críticos
  - [ ] Testes de period_choice (8 testes)
  - [ ] Testes de get_signals_from_telegram (6 testes)
  - [ ] Testes de trade execution (4 testes)

### Semana 2 (02/02 - 09/02)
- [ ] **TASK003.11-3.12**: Coverage e ajustes
  - [ ] Executar coverage report
  - [ ] Identificar gaps
  - [ ] Adicionar testes para atingir 70%

- [ ] **TASK001**: Testes manuais de validação
  - [ ] Backtest período customizado
  - [ ] Backtest períodos predefinidos
  - [ ] Validar sinais Telegram

- [ ] **TASK002.start**: Iniciar validação de integridade
  - [ ] Checksum de sinais
  - [ ] Detecção de duplicatas

---

## 🎯 Execução Imediata (Próximas 2 Horas)

### Step 1: Preparar Estrutura de Testes
```bash
# Verificar se estrutura existe
ls -la /home/ubuntu/atius/tests/backend/

# Se não existir, criar:
mkdir -p /home/ubuntu/atius/tests/backend
mkdir -p /home/ubuntu/atius/tests/backend/fixtures
```

### Step 2: Criar conftest.py Base
Arquivo: `/tests/backend/conftest.py`
- Fixtures para `MockTelegramClient`
- Fixtures para `MockDatabase`
- Fixtures para `InteractiveBacktestEngine`

### Step 3: Criar Primeiro Teste
Arquivo: `/tests/backend/test_period_choice.py`
- Test: `test_period_choice_str_conversion()`
- Test: `test_period_choice_comparison_values()`
- Test: `test_period_choice_invalid_values()`

### Step 4: Executar e Validar
```bash
cd /home/ubuntu/atius
pytest tests/backend/test_period_choice.py -v
```

---

## 🔄 Padrão de Testes

### Padrão AAA (Arrange-Act-Assert)
```python
def test_period_choice_str_conversion():
    # ARRANGE: Setup dados
    period_type = 2  # Ano atual
    
    # ACT: Executar lógica
    period_choice_str = str(period_type or 1)
    
    # ASSERT: Verificar resultado
    assert period_choice_str == "2"
    assert isinstance(period_choice_str, str)
```

### Padrão de Fixtures
```python
@pytest.fixture
def mock_telegram_client():
    """Mock de TelegramClient para testes"""
    # Setup
    client = Mock(spec=TelegramClient)
    yield client
    # Teardown

@pytest.fixture
def interactive_engine(mock_telegram_client, mock_db):
    """Engine com dependências mockadas"""
    engine = InteractiveBacktestEngine(
        telegram_client=mock_telegram_client,
        db_connection=mock_db
    )
    return engine
```

---

## 📊 Áreas de Teste Prioritárias

### 1️⃣ Period Choice Logic (CRITICAL)
**Arquivo**: `test_period_choice.py`

```
test_period_choice_str_conversion
test_period_choice_comparison_values
test_period_choice_boundary_values
test_period_choice_invalid_inputs
test_period_choice_fallback_to_1
test_period_choice_conversion_back_to_int
test_predefined_period_calculations
test_custom_period_date_validation
```

**Coverage Target**: 100%

### 2️⃣ Signal Fetching (CRITICAL)
**Arquivo**: `test_get_signals_from_telegram.py`

```
test_fetch_signals_basic
test_fetch_signals_pagination_offset_id
test_fetch_signals_pagination_offset_date
test_fetch_signals_batch_size_1000
test_fetch_signals_reverse_chronological
test_fetch_signals_error_handling
test_fetch_signals_fallback_to_db
test_fetch_signals_duplicate_detection
```

**Coverage Target**: 90%

### 3️⃣ Trade Execution (IMPORTANT)
**Arquivo**: `test_trade_execution.py`

```
test_simulate_trade_basic
test_simulate_trade_take_profit
test_simulate_trade_stop_loss
test_simulate_trade_multiple_positions
test_simulate_trade_pnl_calculation
```

**Coverage Target**: 85%

### 4️⃣ Database Integration (IMPORTANT)
**Arquivo**: `test_db_integration.py`

```
test_save_signal_to_db
test_load_signals_from_db
test_db_fallback_when_telegram_fails
test_data_consistency_checks
```

**Coverage Target**: 80%

---

## 🛠️ Tools & Setup Necessário

### Dependencies a Instalar
```bash
pip install pytest>=7.0
pip install pytest-asyncio>=0.21
pip install pytest-cov>=4.0
pip install pytest-mock>=3.10
pip install testcontainers>=3.7  # Para PostgreSQL em testes
```

### Config Pytest (`pytest.ini`)
```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
asyncio_mode = auto
addopts = -v --tb=short --strict-markers
markers =
    unit: Unit tests
    integration: Integration tests
    slow: Slow tests
    critical: Critical path tests
```

### Executar Testes
```bash
# Todos os testes
pytest tests/

# Com coverage
pytest tests/ --cov=backend --cov-report=html

# Apenas critical
pytest tests/ -m critical

# Verbose
pytest tests/ -vv
```

---

## 🎯 Definição de "Done"

Uma tarefa de teste é considerada **DONE** quando:

1. ✅ Arquivo de teste criado com nomenclatura correta
2. ✅ Testes implementados seguindo padrão AAA
3. ✅ Todos os testes passando (`pytest` com exit code 0)
4. ✅ Documentação de teste incluída (docstrings claros)
5. ✅ Coverage report atualizado (≥ meta target)
6. ✅ Sem warnings do pylance/mypy

---

## 📈 Métricas de Progresso

| Métrica | Baseline | Week 1 | Week 2 | Target |
|---------|----------|--------|--------|--------|
| # Tests | 0 | 20+ | 40+ | 50+ |
| Coverage | 20% | 40% | 70% | 70%+ |
| Pass Rate | N/A | 100% | 100% | 100% |
| Avg Test Speed | N/A | <100ms | <100ms | <100ms |

---

## 🚀 Próximas Tarefas (Sequência)

1. ✅ **TASK003**: Implementar Testes Automatizados (INICIADA)
2. 📋 **TASK001**: Executar Validação Manual de Backtesting
3. 📋 **TASK002**: Validação de Integridade de Dados
4. 📋 **TASK004**: Otimizar Performance PostgreSQL
5. 📋 **TASK005**: Documentação Técnica

---

## ⚠️ Riscos & Mitigation

| Risco | Probabilidade | Impacto | Mitigação |
|-------|--------------|---------|-----------|
| Async tests complexos | Médio | Alto | Use pytest-asyncio, fixtures prontas |
| Mock de Telethon difícil | Médio | Médio | Mock em nível de função, não classe |
| Testes lentos | Baixo | Médio | Separar unit (rápido) de integration |
| Ambiente de teste inconsistente | Baixo | Alto | Docker compose ou testcontainers |

---

## 📞 Bloqueadores Conhecidos

Nenhum bloqueador identificado no momento. Sistema está pronto para testes.

---

**Próxima Atualização**: 02/02/2026 com status de progresso semana 1
