# Synchronize a default model/provider across Hermes Windows and WSL

Use this reference when the same default inference route must be configured in Giovanni's two independent Hermes runtimes without sharing mutable runtime state.

## Durable rule

Configure each runtime through its own native Hermes executable and native `HERMES_HOME`. Never point one runtime at the peer's config directory.

Canonical homes:

- WSL: `/home/muniz/.hermes`
- Windows: `C:\Users\muniz\AppData\Local\hermes`

## Configuration semantics

The canonical default fields are:

```yaml
model:
  default: MODEL_ID
  provider: custom:PROVIDER_SLUG
```

For a named custom provider, the provider value is the normalized slug prefixed with `custom:` — not necessarily its display name. Example:

```text
display name: Atius Router
provider id:  custom:atius-router
```

A custom-provider entry may also carry its own `model` field. Hermes normally honors `model.default`, but the provider entry's `model` is used as a fallback when the effective model is empty or equals the provider name. Align both fields to prevent stale fallback routing:

```yaml
custom_providers:
  - name: Atius Router
    model: gpt-5.6-sol
```

Do not assume the desired provider is always list index `0`. Inspect `custom_providers`, identify the entry by normalized name and/or base URL, then use its actual numeric index with `hermes config set`.

## Procedure

### 1. Inspect safely

Read only:

- `model.default`
- `model.provider`
- custom-provider display names, model IDs, API mode and base URLs

Redact `api_key`, tokens and headers. Confirm each runtime's native config path before writing.

### 2. Apply in WSL

```bash
export HERMES_HOME=/home/muniz/.hermes
H=/home/muniz/.local/bin/hermes

"$H" config set model.default gpt-5.6-sol
"$H" config set model.provider custom:atius-router
"$H" config set custom_providers.PROVIDER_INDEX.model gpt-5.6-sol
```

### 3. Apply in native Windows

Invoke native PowerShell from WSL when necessary, but set the Windows home inside the Win32 process:

```powershell
$env:HERMES_HOME = 'C:\Users\muniz\AppData\Local\hermes'
$h = 'C:\Users\muniz\AppData\Local\hermes\hermes-agent\venv\Scripts\hermes.exe'

& $h config set model.default gpt-5.6-sol
& $h config set model.provider 'custom:atius-router'
& $h config set custom_providers.PROVIDER_INDEX.model gpt-5.6-sol
```

`hermes config set` supports numeric list indices such as `custom_providers.0.model` and writes atomically.

### 4. Validate both runtimes

Run the native command in each runtime:

```text
hermes config check
```

Then verify the typed values and provider resolution. A valid Atius Router result should report, without exposing credentials:

```text
MODEL_DEFAULT=gpt-5.6-sol
MODEL_PROVIDER=custom:atius-router
CUSTOM_NAME=Atius Router
CUSTOM_FALLBACK_MODEL=gpt-5.6-sol
RESOLVED_PROVIDER=custom
RESOLVED_SOURCE=pool:custom:atius-router
RESOLVED_MODEL=gpt-5.6-sol
RESOLVED_BASE_URL=https://router.atius.com.br/v1
RESOLVED_API_MODE=chat_completions
CREDENTIAL_PRESENT=True
```

For code-level verification, use each runtime's native Python and call:

```python
from hermes_cli.config import load_config
from hermes_cli.runtime_provider import resolve_runtime_provider

config = load_config()
model = config["model"]
runtime = resolve_runtime_provider(target_model=model["default"])
```

Print only non-secret routing metadata and a boolean for credential presence.

## Activation semantics

- The persisted default applies to new sessions/processes.
- An already-open CLI session can keep its session-selected model; use `/model MODEL_ID` or open a new session when immediate switching is required.
- Do not restart WSL merely for a model/provider config change.
- Restart the gateway only when an already-running gateway process must immediately reload configuration; persistence itself does not require a restart.
- A `config check` schema-migration notice is separate from model/provider correctness. Do not migrate unrelated config merely to complete this task.

## Verified machine-specific values (2026-07-19)

Both runtimes were configured and internally resolved successfully with:

```text
model.default = gpt-5.6-sol
model.provider = custom:atius-router
custom provider = Atius Router
base URL = https://router.atius.com.br/v1
API mode = chat_completions
```

No API keys belong in this reference.
