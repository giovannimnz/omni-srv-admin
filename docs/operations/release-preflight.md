# Release/deploy preflight

Objetivo: impedir que o `omni-srv-admin`, `fork-sync` ou scripts de release
publiquem tags, pushes ou deploys que acionariam GitHub Actions com falhas
deterministicas ja conhecidas.

## Entrada unica

```bash
scripts/release-preflight.sh <repo-path> \
  --tag vX.Y.Z \
  --mode fork-deploy \
  --github-repo owner/repo \
  --deploy-config modules/fork-sync/projects/<project>/deploy.yaml
```

O preflight retorna `release_preflight=success` ou sai com erro antes do envio.

## Checks bloqueantes

- Workflow roda `bun run build` dentro de `web/`, mas `web/package.json` nao tem
  `scripts.build`.
- Workflow usa `DOCKERHUB_USERNAME`/`DOCKERHUB_TOKEN` sem `if`/guard, e o repo
  nao tem os dois secrets.
- Tag de quatro partes, como `v0.12.15.1`, chega em `npm version` sem
  normalizacao SemVer.
- Deploy usa uma imagem fora do GHCR e nao ha secrets DockerHub suficientes.

## Warnings aceitos

- DockerHub sem secrets e workflow guardado por `dockerhub_enabled`: o envio deve
  publicar GHCR e pular DockerHub.

## Pontos integrados

- `scripts/release.sh` chama o preflight antes de criar commit/tag/release.
- `modules/fork-sync/bin/deploy.sh` chama o preflight antes de build/push/restart.
- O modulo testavel fica em
  `modules/fork-sync/cli/fork_sync/core/release_preflight.py`.

## Exemplo validado

```bash
scripts/release-preflight.sh /home/ubuntu/GitHub/containers/router-ai-atius \
  --tag v0.12.15.1 \
  --mode fork-deploy \
  --github-repo giovannimnz/router-ai-atius \
  --deploy-config modules/fork-sync/projects/atius-router/deploy.yaml
```

Resultado esperado para o router depois da correcao: success com warnings de
DockerHub opcional, porque GHCR e o caminho padrao.
