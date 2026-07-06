# Omni Srv Admin release/versioning standard

Este repo deve ser versionado antes de publicar mudanças no GitHub. O padrão é:

1. Validar testes/lint relevantes.
2. Escolher versão semântica (`MAJOR.MINOR.PATCH`).
3. Executar `scripts/release.sh <versao>`.
4. O script atualiza `cli/omni/__init__.py`, `cli/setup.py`, `CHANGELOG.md`, cria commit `chore(release): vX.Y.Z`, tag anotada e GitHub Release.
5. A release deve conter notas de implementações e/ou correções derivadas dos commits desde a tag anterior.
6. Antes de criar commit/tag/release, `scripts/release.sh` roda `scripts/release-preflight.sh` para bloquear workflows que falhariam de forma determinística.

Comandos:

```bash
# prévia sem commit/tag/push
scripts/release.sh 0.2.0 --dry-run

# release real
scripts/release.sh 0.2.0
```

O workflow `.github/workflows/release.yml` publica/atualiza o GitHub Release quando uma tag `v*.*.*` é enviada ou via `workflow_dispatch` com uma tag existente.

Não publique release com worktree sujo, segredos, logs sensíveis ou artefatos locais.

Para forks e programas enviados pelo `fork-sync`, o mesmo gate fica em
`modules/fork-sync/bin/deploy.sh`. Detalhes: `docs/operations/release-preflight.md`.
