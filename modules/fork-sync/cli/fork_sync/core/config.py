"""Configuração de paths e variáveis do fork-sync."""

import os
from pathlib import Path

# REPO_ROOT: raiz do repo git (resolve de <cli/fork_sync/core/config.py> subindo 4 níveis)
_THIS = Path(__file__).resolve()
REPO_ROOT = Path(os.environ.get("FORK_SYNC_ROOT", _THIS.parents[3])).resolve()
PROJECTS_DIR = REPO_ROOT / "projects"
LOGS_DIR = REPO_ROOT / "logs"
BIN_DIR = REPO_ROOT / "bin"
LIB_DIR = REPO_ROOT / "lib"

# Bash scripts legados (mantidos por compatibilidade)
SYNC_SH = BIN_DIR / "sync.sh"
DEPLOY_SH = BIN_DIR / "deploy.sh"
DETECT_SH = BIN_DIR / "detect-release.sh"
