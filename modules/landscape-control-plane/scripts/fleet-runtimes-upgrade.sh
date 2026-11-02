#!/usr/bin/env bash
# omni::fleet-runtimes-upgrade v1.2.0
# Atualizacao soberana e unificada de Toolchains e Runtimes na frota ATIUS:
# - Node.js: Versao mais recente do Node 24 LTS via NVM (v24.22.2)
# - NPM & PNPM: Versoes mais recentes (@latest)
# - Bun: Versao mais recente via instalador oficial / bun upgrade (v1.4.4+)
# - uv & Python: uv atualizado (@latest), Python 3.13 LTS/estavel instalado via uv
# - pip: Versao mais recente via uv tool (@latest 26.2+)
# - GitHub CLI: gh atualizado (@latest 2.103.3) via APT oficial ou release standalone
# Contencao de recursos: CPUQuota <= 20%, nice 19, ionice idle.
set -uo pipefail

# Prioridade minima para nao impactar servicos em producao
renice -n 19 -p $$ >/dev/null 2>&1 || true
ionice -c 3 -p $$ >/dev/null 2>&1 || true

# Guard contra arquivos stray na raiz do sistema
[ -f /package.json ] && mv /package.json /root/package.json.bak 2>/dev/null || true

section() {
  printf '\n== %s ==\n' "$1"
}

section identity
HOST=$(hostname 2>/dev/null || cat /etc/hostname)
printf 'host=%s\n' "$HOST"
printf 'date_utc=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"

# Detectar usuario principal de acordo com o host
if [[ "$HOST" =~ horistic ]]; then
  TARGET_USER="horistic"
  TARGET_HOME="/home/horistic"
elif id -u ubuntu >/dev/null 2>&1; then
  TARGET_USER="ubuntu"
  TARGET_HOME="/home/ubuntu"
else
  TARGET_USER="root"
  TARGET_HOME="/root"
fi
printf 'target_user=%s\n' "$TARGET_USER"
printf 'target_home=%s\n' "$TARGET_HOME"

mkdir -p /usr/local/bin "$TARGET_HOME/.local/bin"

# 1. ATUALIZACAO DO GITHUB CLI (gh)
section github_cli
export DEBIAN_FRONTEND=noninteractive
mkdir -p -m 755 /etc/apt/keyrings
if [ ! -f /etc/apt/keyrings/githubcli-archive-keyring.gpg ]; then
  curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | dd of=/etc/apt/keyrings/githubcli-archive-keyring.gpg 2>/dev/null || true
  chmod go+r /etc/apt/keyrings/githubcli-archive-keyring.gpg 2>/dev/null || true
fi
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" > /etc/apt/sources.list.d/github-cli.list 2>/dev/null || true
apt-get update -o Dir::Etc::sourcelist="sources.list.d/github-cli.list" -o Dir::Etc::sourceparts="-" -o APT::Get::List-Cleanup="0" -qq >/dev/null 2>&1 || true
apt-get install -y --only-upgrade gh >/dev/null 2>&1 || apt-get install -y gh >/dev/null 2>&1 || true

# Fallback para release oficial caso o apt nao entregue a 2.103+
GH_VER=$(gh --version 2>/dev/null | head -n 1 | awk '{print $3}' || echo "")
if [[ ! "$GH_VER" =~ ^2\.10[0-9] ]]; then
  ARCH=$(uname -m)
  [ "$ARCH" = "aarch64" ] && GH_ARCH="arm64" || GH_ARCH="amd64"
  GH_TMP=$(mktemp -d)
  if curl -fsSL "https://github.com/cli/cli/releases/download/v2.103.3/gh_2.103.3_linux_${GH_ARCH}.tar.gz" -o "$GH_TMP/gh.tar.gz" 2>/dev/null; then
    tar -xzf "$GH_TMP/gh.tar.gz" -C "$GH_TMP" 2>/dev/null || true
    if [ -f "$GH_TMP"/gh_*/bin/gh ]; then
      cp -f "$GH_TMP"/gh_*/bin/gh /usr/local/bin/gh
      chmod +x /usr/local/bin/gh
    fi
  fi
  rm -rf "$GH_TMP"
fi
printf 'gh_version=%s\n' "$(gh --version 2>/dev/null | head -n 1 || echo 'failed')"

# 2. INSTALACAO E ATUALIZACAO DO UV E PYTHON (via uv)
section uv_and_python
curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR="/usr/local/bin" sh >/dev/null 2>&1 || true
if [ "$TARGET_USER" != "root" ]; then
  sudo -u "$TARGET_USER" -H bash -c 'curl -LsSf https://astral.sh/uv/install.sh | sh >/dev/null 2>&1 || true'
fi

UV_BIN="/usr/local/bin/uv"
[ -x "$UV_BIN" ] || UV_BIN=$(command -v uv || echo "$TARGET_HOME/.local/bin/uv")

if [ -x "$UV_BIN" ]; then
  "$UV_BIN" self update >/dev/null 2>&1 || true
  # Instalar Python 3.13 como versao padrao via uv
  "$UV_BIN" python install 3.13 --default >/dev/null 2>&1 || true
  if [ "$TARGET_USER" != "root" ]; then
    sudo -u "$TARGET_USER" -H "$UV_BIN" python install 3.13 --default >/dev/null 2>&1 || true
  fi

  UV_PYTHON_BIN=$("$UV_BIN" python find 3.13 2>/dev/null || true)
  if [ -n "$UV_PYTHON_BIN" ] && [ -x "$UV_PYTHON_BIN" ]; then
    REAL_PY=$(realpath "$(dirname "$(dirname "$UV_PYTHON_BIN")")" 2>/dev/null || dirname "$(dirname "$UV_PYTHON_BIN")")
    mkdir -p /opt/uv-python
    rm -rf /opt/uv-python/3.13
    cp -rL "$REAL_PY" /opt/uv-python/3.13 2>/dev/null || cp -a "$REAL_PY" /opt/uv-python/3.13
    chmod -R a+rX /opt/uv-python/3.13 2>/dev/null || true

    ln -sf /opt/uv-python/3.13/bin/python3.13 /usr/local/bin/python3.13
    ln -sf /opt/uv-python/3.13/bin/python3 /usr/local/bin/python3
    ln -sf /opt/uv-python/3.13/bin/python3.13 "$TARGET_HOME/.local/bin/python3.13"
    ln -sf /opt/uv-python/3.13/bin/python3 "$TARGET_HOME/.local/bin/python3"
    chown -h "$TARGET_USER:$TARGET_USER" "$TARGET_HOME/.local/bin/python3.13" "$TARGET_HOME/.local/bin/python3" 2>/dev/null || true
  fi

  printf 'uv_version=%s\n' "$("$UV_BIN" --version 2>/dev/null || echo 'failed')"
  printf 'python_uv=%s\n' "$(/usr/local/bin/python3 --version 2>/dev/null || "$UV_BIN" run python3 --version 2>/dev/null || echo 'failed')"
else
  printf 'uv_version=missing\n'
fi

# 3. INSTALACAO E ATUALIZACAO DO BUN
section bun
if command -v bun >/dev/null 2>&1; then
  bun upgrade >/dev/null 2>&1 || true
else
  curl -fsSL https://bun.sh/install | bash >/dev/null 2>&1 || true
fi

if [ "$TARGET_USER" != "root" ]; then
  sudo -u "$TARGET_USER" -H bash -c '
    if command -v bun >/dev/null 2>&1; then
      bun upgrade >/dev/null 2>&1 || true
    else
      curl -fsSL https://bun.sh/install | bash >/dev/null 2>&1 || true
    fi
  ' || true
fi

BUN_FOUND=""
for b in "$TARGET_HOME/.bun/bin/bun" "/root/.bun/bin/bun" "/usr/local/bin/bun"; do
  if [ -x "$b" ]; then
    BUN_FOUND="$b"
    break
  fi
done

if [ -n "$BUN_FOUND" ]; then
  rm -f /usr/local/bin/bun
  cp -f "$BUN_FOUND" /usr/local/bin/bun 2>/dev/null || ln -sf "$BUN_FOUND" /usr/local/bin/bun
  chmod 755 /usr/local/bin/bun 2>/dev/null || true
  ln -sf /usr/local/bin/bun "$TARGET_HOME/.local/bin/bun"
  chown -h "$TARGET_USER:$TARGET_USER" "$TARGET_HOME/.local/bin/bun" 2>/dev/null || true
  printf 'bun_version=%s\n' "$(/usr/local/bin/bun --version 2>/dev/null || echo 'failed')"
else
  printf 'bun_version=missing\n'
fi

# 4. INSTALACAO E ATUALIZACAO DO NVM, NODE 24, NPM E PNPM
section node_and_npm
export NVM_DIR="$TARGET_HOME/.nvm"
[ -f "$TARGET_HOME/.npmrc" ] && sed -i '/prefix=/d' "$TARGET_HOME/.npmrc" 2>/dev/null || true
[ -f /root/.npmrc ] && sed -i '/prefix=/d' /root/.npmrc 2>/dev/null || true
if [ ! -s "$NVM_DIR/nvm.sh" ]; then
  sudo -u "$TARGET_USER" -H bash -c 'curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash >/dev/null 2>&1'
fi

# Executar NVM para instalar Node 24 mais recente
sudo -u "$TARGET_USER" -H bash -c '
  export NVM_DIR="$HOME/.nvm"
  [ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"
  LATEST_24=$(nvm ls-remote 24 2>/dev/null | grep -E "v24\.[0-9]+\.[0-9]+" | tail -n 1 | awk "{print \$1}" | sed "s/[->* ]//g")
  [ -z "$LATEST_24" ] && LATEST_24="v24.22.2"
  nvm install "$LATEST_24" >/dev/null 2>&1 || nvm install --delete-prefix "$LATEST_24" >/dev/null 2>&1
  nvm alias default "$LATEST_24" >/dev/null 2>&1
  nvm use --delete-prefix "$LATEST_24" >/dev/null 2>&1 || nvm use "$LATEST_24" >/dev/null 2>&1
  npm install -g npm@latest >/dev/null 2>&1 || true
  npm install -g --allow-scripts=pnpm pnpm@latest >/dev/null 2>&1 || true
'

# Descobrir caminhos reais gerados pelo NVM do usuario
INSTALLED_NODE=$(sudo -u "$TARGET_USER" -H bash -c 'export NVM_DIR="$HOME/.nvm"; [ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh" && which node' 2>/dev/null || echo "")

if [ -n "$INSTALLED_NODE" ] && [ -x "$INSTALLED_NODE" ]; then
  NODE_DIR=$(dirname "$INSTALLED_NODE")
  
  # Criar links simbolicos globais em /usr/local/bin
  ln -sf "$INSTALLED_NODE" /usr/local/bin/node
  [ -x "$NODE_DIR/npm" ] && ln -sf "$NODE_DIR/npm" /usr/local/bin/npm
  [ -x "$NODE_DIR/npx" ] && ln -sf "$NODE_DIR/npx" /usr/local/bin/npx
  [ -x "$NODE_DIR/pnpm" ] && ln -sf "$NODE_DIR/pnpm" /usr/local/bin/pnpm

  # Criar links locais em ~/.local/bin
  ln -sf "$INSTALLED_NODE" "$TARGET_HOME/.local/bin/node"
  [ -x "$NODE_DIR/npm" ] && ln -sf "$NODE_DIR/npm" "$TARGET_HOME/.local/bin/npm"
  [ -x "$NODE_DIR/npx" ] && ln -sf "$NODE_DIR/npx" "$TARGET_HOME/.local/bin/npx"
  [ -x "$NODE_DIR/pnpm" ] && ln -sf "$NODE_DIR/pnpm" "$TARGET_HOME/.local/bin/pnpm"
  chown -h "$TARGET_USER:$TARGET_USER" "$TARGET_HOME/.local/bin/node" "$TARGET_HOME/.local/bin/npm" "$TARGET_HOME/.local/bin/npx" "$TARGET_HOME/.local/bin/pnpm" 2>/dev/null || true

  # Configurar tambem para root
  export NVM_DIR="/root/.nvm"
  if [ ! -s "$NVM_DIR/nvm.sh" ]; then
    curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash >/dev/null 2>&1 || true
  fi
  if [ -s "$NVM_DIR/nvm.sh" ]; then
    . "$NVM_DIR/nvm.sh"
    nvm alias default "$INSTALLED_NODE" >/dev/null 2>&1 || true
  fi
fi

# 5. ATUALIZACAO DO PIP
section python_pip
if [ -x "/opt/uv-python/3.13/bin/python3" ] && [ -x "$UV_BIN" ]; then
  "$UV_BIN" pip install --break-system-packages --python /opt/uv-python/3.13/bin/python3 pip >/dev/null 2>&1 || true
fi

PIP_FOUND=""
for p in /opt/uv-python/3.13/bin/pip "$TARGET_HOME/.local/bin/pip" "/root/.local/bin/pip" /usr/local/bin/pip; do
  if [ -x "$p" ]; then
    PIP_FOUND="$p"
    break
  fi
done

if [ -n "$PIP_FOUND" ]; then
  ln -sf "$PIP_FOUND" /usr/local/bin/pip
  ln -sf "$PIP_FOUND" /usr/local/bin/pip3
  ln -sf "$PIP_FOUND" "$TARGET_HOME/.local/bin/pip"
  ln -sf "$PIP_FOUND" "$TARGET_HOME/.local/bin/pip3"
  chown -h "$TARGET_USER:$TARGET_USER" "$TARGET_HOME/.local/bin/pip" "$TARGET_HOME/.local/bin/pip3" 2>/dev/null || true
fi

# 6. SCORECARD FINAL E VEREDITO
section verdict
NODE_V=$(/usr/local/bin/node -v 2>/dev/null || node -v 2>/dev/null || echo "failed")
NPM_V=$(/usr/local/bin/npm -v 2>/dev/null || npm -v 2>/dev/null || echo "failed")
PNPM_V=$(/usr/local/bin/pnpm --version 2>/dev/null || pnpm --version 2>/dev/null || pnpm --dir /tmp --version 2>/dev/null || echo "failed")
BUN_V=$(/usr/local/bin/bun --version 2>/dev/null || bun --version 2>/dev/null || echo "failed")
UV_V=$(/usr/local/bin/uv --version 2>/dev/null || uv --version 2>/dev/null || echo "failed")
GH_V=$(/usr/local/bin/gh --version 2>/dev/null | head -n 1 || gh --version 2>/dev/null | head -n 1 || echo "failed")
PYTHON_V=$(/usr/local/bin/python3.13 --version 2>/dev/null || python3 --version 2>/dev/null || echo "failed")
PIP_V=$(/usr/local/bin/pip --version 2>/dev/null | awk '{print $1, $2}' || pip --version 2>/dev/null | awk '{print $1, $2}' || echo "failed")

printf 'summary_node=%s\n' "$NODE_V"
printf 'summary_npm=%s\n' "$NPM_V"
printf 'summary_pnpm=%s\n' "$PNPM_V"
printf 'summary_bun=%s\n' "$BUN_V"
printf 'summary_uv=%s\n' "$UV_V"
printf 'summary_gh=%s\n' "$GH_V"
printf 'summary_python=%s\n' "$PYTHON_V"
printf 'summary_pip=%s\n' "$PIP_V"

if [[ "$NODE_V" =~ ^v24\. ]] && [ "$NPM_V" != "failed" ] && [ "$PNPM_V" != "failed" ] && [ "$PIP_V" != "failed" ]; then
  printf 'overall_result=SUCCESS\n'
else
  printf 'overall_result=DEGRADED\n'
fi
