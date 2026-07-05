# Política de Secrets e Dados Sensíveis

> **LEIA ANTES de contribuir ou commitar.**

Este documento define o que **NUNCA** deve aparecer no repositório `giovannimnz/fork-sync`,
e como configurar segredos de forma segura.

---

## 1. O que NUNCA commitar

### 1.1. Credenciais e tokens
- ❌ Senhas, API keys, tokens (GitHub, Telegram, Discord, OpenAI, etc.)
- ❌ PATs (`ghp_*`, `sk-*`, `AKIA*`, `xoxb-*`, etc.)
- ❌ Tokens de webhook
- ❌ OAuth client secrets
- ❌ JWT secrets / signing keys

### 1.2. Chaves privadas e certificados
- ❌ `*.key`, `*.pem`, `*.p12`, `*.pfx`
- ❌ `id_rsa`, `id_ed25519`, `*.ssh-key`
- ❌ Certificados SSL/TLS (`.crt`, `.cer`)
- ❌ Keystores Java (`*.jks`, `*.keystore`)

### 1.3. Arquivos de configuração sensíveis
- ❌ `.env`, `.env.*` (exceto `.env.example` com placeholders)
- ❌ `secrets/`, `*.local`, `*.prod`
- ❌ `credentials.json`, `service-account.json`
- ❌ `wp-config.php`, `database.yml` com senhas reais
- ❌ `kubeconfig` com credenciais

### 1.4. Dados pessoais e internos
- ❌ URLs internas com credenciais (`https://user:pass@host/...`)
- ❌ IPs internos que identificam infraestrutura privada
- ❌ Caminhos absolutos de servidores de produção
- ❌ Logs com tokens ou dados de clientes

### 1.5. Builds e artefatos
- ❌ Binários compilados, `node_modules/`, `__pycache__/`
- ❌ Imagens Docker locais (`.tar`, `.tar.gz`)
- ❌ `dist/`, `build/`, `target/`

---

## 2. O que fazer em vez disso

### 2.1. Variáveis de ambiente

```bash
# ~/.bashrc ou ~/.zshrc (gitignored por definição — fora do repo)
export GITHUB_TOKEN="ghp_..."
export TELEGRAM_BOT_TOKEN="..."
export HEALTH_TOKEN="..."
```

```yaml
# projects/meufork/deploy.yaml — placeholder Vazio
health_token: ""  # Set via env: $HEALTH_TOKEN
```

### 2.2. Arquivo `.env` local (gitignored)

```bash
# ~/fork-sync/.env (gitignored)
GITHUB_TOKEN=ghp_xxxxxxxxxxxx
TELEGRAM_BOT_TOKEN=xxxxxxxxxxxx
HEALTH_TOKEN=xxxxxxxxxxxx
```

O `.gitignore` já bloqueia `.env`. Ver [`/home/ubuntu/fork-sync/.gitignore`](../.gitignore).

### 2.3. Secret manager (recomendado para produção)

Em vez de `.env`, use:
- **HashiCorp Vault** (se disponível)
- **AWS Secrets Manager** / **GCP Secret Manager**
- **systemd-creds** (Linux nativo)
- **Doppler** / **Infisical** (cloud secret ops)

### 2.4. Placeholders em YAML

```yaml
# ✅ Correto
health_token: ""  # Set via env or secret manager
api_key: "${API_KEY}"  # interpolado em runtime

# ❌ Errado
health_token: "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
api_key: "sk-1234567890abcdef"
```

### 2.5. Sanitização em logs

```bash
# Em scripts bash: mascarar secrets
echo "[INFO] token=***" | tee -a log
sed -i 's/\(token=\)[^&]*/\1***/g' log
```

---

## 3. `.gitignore` reference

O `.gitignore` deste repo já bloqueia:

```gitignore
# Local config / secrets
*.local
.env
.env.*
secrets/
*.key
*.pem
*.p12
*.pfx

# Credentials
credentials.json
service-account.json
.gcp/
.aws/
.azure/

# Builds
node_modules/
__pycache__/
*.pyc
dist/
build/
target/

# OS / editor
.DS_Store
Thumbs.db
.idea/
.vscode/
*.swp
*.tmp
```

Se precisar commitar um arquivo que cairia no `.gitignore` (ex: `.env.example`),
use `git add -f` e **garanta que o conteúdo é seguro** (só placeholders).

---

## 4. Auditoria antes de push

### 4.1. Antes de cada commit

```bash
# 1. Verificar staged files
git diff --staged --name-only

# 2. Procurar padrões comuns
git diff --staged | grep -iE "(password|token|api[_-]?key|secret|private[_-]?key|BEGIN [A-Z ]+PRIVATE KEY|ghp_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9]{20,})" && echo "❌ POSSÍVEL SECRET DETECTADO" || echo "✅ OK"

# 3. Conferir .env não está trackeado
git ls-files | grep -E "(\.env$|\.env\.)" | grep -v ".env.example" && echo "❌ .env trackeado!" || echo "✅ .env não trackeado"
```

### 4.2. Antes de cada push

```bash
# Instalar gitleaks (recomendado)
brew install gitleaks  # macOS
# ou
go install github.com/zricethezav/gitleaks/v8@latest

# Rodar
gitleaks detect --source . --verbose
```

Alternativa:
```bash
trufflehog git file://. --only-verified
```

### 4.3. Em caso de vazamento

Se um secret vazar no repo:

1. **Revogar imediatamente** o secret (gerar novo, invalidar o antigo)
2. **Limpar histórico do Git** com `git filter-repo` (CUIDADO: reescreve SHA)
3. **Notificar** se for credencial de produção
4. **Documentar incidente** no vault Obsidian (`61-Incidents/`)

---

## 5. Em CI/CD

Se usar GitHub Actions:
- Usar **Secrets** do repositório (Settings → Secrets and variables → Actions)
- Nunca echo de secrets em logs (`echo $SECRET`)
- Usar `secrets.GITHUB_TOKEN` quando possível (escopo limitado)

Exemplo `.github/workflows/sync.yml`:
```yaml
- name: Run sync
  env:
    GITHUB_TOKEN: ${{ secrets.FORK_SYNC_TOKEN }}
    TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
  run: |
    fork-sync sync atius-router --deploy
```

---

## 6. Resumo rápido

| ✅ Permitido | ❌ Proibido |
|---|---|
| `health_token: ""` | `health_token: "eyJh..."` |
| `api_key: "${API_KEY}"` | `api_key: "sk-1234..."` |
| `.env.example` (placeholders) | `.env` (valores reais) |
| `https://api.exemplo.com` | `https://user:pass@api.exemplo.com` |
| Paths relativos (`./logs/`) | Paths absolutos com prod (`/srv/prod/...`) |
| Logs com `***` | Logs com token raw |

---

## 7. Contato

Em caso de dúvida ou incidente de segurança:
- Vault Obsidian: `ideaverse/61-Incidents/`
- GitHub: abrir issue SECURITY Advisories (privado)
- Email: ver perfil `giovannimnz` no GitHub

---

**Última atualização:** 2026-06-04
**Mantenedor:** Giovanni Muniz
