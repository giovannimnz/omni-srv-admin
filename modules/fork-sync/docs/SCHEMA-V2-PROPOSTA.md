# Schema v2 — fork-sync

> **Status:** Proposta (2026-06-04). Sujeito a feedback antes de implementar.

## Motivação

O schema v1 (1 upstream + protected paths + merge_strategy) cobre forks tradicionais
(atius-router, aionui, hermes-agent). Mas não cobre:

- **Fusões de múltiplos upstreams** (ex: `gsd-caveman-hermes` = get-shit-done + hermes-agent)
- **Lógica de merge customizada** (ex: copy de pastas específicas, rename de namespaces, reescrita de imports)
- **Detecção de release multi-source** (qual dos 3 upstreams mudou? como versionar?)
- **Dependências entre forks** (sync de A dispara sync de B)

## Schema v2 (proposto)

```yaml
# projects/gsd-caveman-hermes/sync.yaml
project: gsd-caveman-hermes
display_name: "GSD Caveman Hermes (fusão)"

# ───── Fontes (1..N upstreams) ─────
upstreams:
  - name: get-shit-done
    url: https://github.com/gsd-build/get-shit-done
    branch: main
    role: primary                # quem dita versão major
    paths:
      include:                   # só estes paths são puxados
        - workflows/
        - skills/caveman/
        - profiles/
  - name: hermes-agent
    url: https://github.com/NousResearch/hermes-agent
    branch: main
    role: secondary
    paths:
      include:
        - skills/
        - config/

# ───── Destino ─────
target:
  path: /home/ubuntu/GitHub/forks/gsd-caveman-hermes
  branch: main

# ───── Lógica de fusão ─────
merge:
  strategy: custom              # custom | theirs | ours | merge | subtree
  strategy_script: ./merge.sh   # relativo a projects/<name>/
  # OU plugin Python:
  # strategy_plugin: gsd_caveman_hermes.merge:CavemanMerge
  pre_merge:                     # hooks antes do merge
    - ./pre-validate.sh
  post_merge:                    # hooks depois do merge
    - ./rebrand.py
    - ./update-imports.sh
  protected_paths:               # preservados em conflito
    - README.md
    - VERSION
    - .gsd-identity

# ───── Versionamento ─────
version:
  scheme: "{primary_version}+{secondary_count}.rf{N}"
  # ex: v2.0.0+12.rf3 (primary=gsd-build, 12 commits novos do hermes, 3 syncs nossos)
  counter_dir: "~/.fork-sync/{project}/counter"

# ───── Detecção de release ─────
detect:
  # Detecta em qual upstream houve mudança
  sources:
    - get-shit-done
    - hermes-agent
  # Como reagir quando AMBOS mudam no mesmo sync
  multi_change_action: queue    # queue | abort | manual

# ───── Notificações ─────
notifications:
  level: all                    # all | conflicts | errors | none
  telegram:
    chat_id: -1003797723446     # Atius Capital Group
    on_success: true
    on_conflict: true
    on_failure: true

# ───── Cron / agendamento ─────
schedule:
  cron: "0 8 * * *"             # 8h BRT diário
  cooldown_minutes: 60          # evita rodar 2x em sequência

# ───── Dependências ─────
triggers:
  # Quando get-shit-done publicar release major, dispara fusão
  on_release:
    - get-shit-done:minor
    - hermes-agent:patch
```

## Schema v1 (legado, ainda suportado)

Para forks simples (1 upstream), o schema antigo continua válido:

```yaml
project: aionui
upstream: https://github.com/iOfficeAI/AionUi
upstream_branch: main
origin_branch: main
fork: /home/ubuntu/GitHub/forks/AionUi
protected_paths: [...]
merge_strategy: merge
```

CLI detecta automaticamente: se tem `upstreams:` (lista) → schema v2, se tem `upstream:` (string) → schema v1.

## Como funciona a estratégia custom

### Modo script (`strategy_script`)

```bash
#!/usr/bin/env bash
# projects/gsd-caveman-hermes/merge.sh
set -euo pipefail
# Argumentos: $1=upstream_a, $2=upstream_b, $3=target
# Exit 0 = sucesso, Exit 1 = conflito manual, Exit 2 = abortar

A="$1"  # path local do upstream A (já fetched)
B="$2"  # path local do upstream B (já fetched)
T="$3"  # path local do target

# Exemplo: copiar skills/caveman/ do A, skills/ do B, reescrever imports
cp -r "$A/skills/caveman/." "$T/skills/caveman/"
cp -r "$B/skills/." "$T/skills/hermes/"
# ... lógica de fusão ...

echo "Fusão concluída"
```

### Modo plugin Python (`strategy_plugin`)

```python
# gsd_caveman_hermes/merge.py
from fork_sync.plugins import MergeStrategy

class CavemanMerge(MergeStrategy):
    def pre_fetch(self, upstreams):
        # Chamado antes do git fetch
        for u in upstreams:
            if not u.url.startswith("https://"):
                raise ValueError(f"URL insegura: {u.url}")

    def merge(self, upstreams, target):
        # Sua lógica de fusão customizada
        self.copy_paths(upstreams[0], target, ["workflows/", "skills/caveman/"])
        self.copy_paths(upstreams[1], target, ["skills/"])
        self.rewrite_imports(target, old="hermes_agent", new="hermes")
        return {"files_changed": 42, "conflicts": 0}

    def post_merge(self, target, result):
        # Validação, testes, notificação
        self.run_tests(target)
```

Instalação do plugin:
```bash
# Projeto isolado, em qualquer lugar do PYTHONPATH
pip install -e ~/projects/gsd-caveman-hermes-plugin/
# fork-sync descobre via entry_points:
#   [project.entry-points."fork_sync.strategies"]
#   caveman = "gsd_caveman_hermes.merge:CavemanMerge"
```

## Detecção de release multi-source

```python
# Lógica:
1. Para cada upstream em `detect.sources`:
   - Comparar local_commit vs remote_commit
   - Se mudou → marcar
2. Se 0 mudaram → no_op
3. Se 1 mudou → sync normal com aquele upstream
4. Se 2+ mudaram → aplicar `multi_change_action`:
   - queue: enfileirar, syncar 1 por vez
   - abort: cancelar sync atual, notificar
   - manual: parar e pedir decisão humana
```

## Versionamento de fusão

```
upstreams:
  - name: get-shit-done
    version: v2.5.0         # versão do upstream A
  - name: hermes-agent
    version: 1.2.3          # versão do upstream B

version:
  scheme: "{primary_version}+{secondary_count}.rf{N}"

# Result: v2.5.0+15.rf3
#   ^^^^^   ^  ^
#   |       |  └─ nosso sync #3 desde o último release A
#   |       └──── 15 commits no upstream B desde último sync
#   └──────────── versão do upstream primary
```

## Cronograma coordenado

```yaml
triggers:
  # Quando get-shit-done major release, executa este projeto
  on_release:
    - get-shit-done:major
  # Quando hermes-agent patch release, executa este projeto
  on_release:
    - hermes-agent:patch
  # Quando atius-router atualiza, executa este projeto
  on_upstream_change:
    - atius-router
```

CLI mantém um arquivo de estado (`~/.fork-sync/state.json`) que rastreia
"último commit visto por upstream" e dispara chains.

## Migração

```bash
# Adicionar campo `upstreams:` a partir de um schema v1
fork-sync migrate projects/gsd-caveman-hermes/sync.yaml

# Gerar esqueleto de estratégia custom
fork-sync init-strategy gsd-caveman-hermes --type script
# → cria projects/gsd-caveman-hermes/merge.sh com template

fork-sync init-strategy gsd-caveman-hermes --type plugin
# → cria ~/projects/gsd-caveman-hermes-plugin/ com setup.py
```

## Compatibilidade

- v1 YAML (string `upstream:`) → detectado, funciona como antes
- v2 YAML (lista `upstreams:`) → novo motor
- Scripts bash legados (`bin/sync.sh`) → continua sendo o backend default
- Plugins Python → opt-in via entry_points

## Próximos passos

1. Feedback Giovanni sobre o schema (este doc)
2. Implementar parser dual (v1+v2) em `core/registry.py`
3. Implementar `core/multi_upstream.py` (fetch paralelo, merge multi-source)
4. Adicionar `core/plugins.py` (entry_points discovery)
5. Adicionar `fork-sync init-strategy` (gerador)
6. Migrar aionui/atius-router para v2 (com 1 upstream) só pra testar parser
7. Criar `gsd-caveman-hermes` real (validação end-to-end)
