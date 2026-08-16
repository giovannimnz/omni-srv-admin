# WSL → native Windows `cua-driver` manifest bridge

## Quando usar

Use quando Hermes roda dentro do WSL, um wrapper executa corretamente o CUA Driver nativo do Windows e `hermes computer-use doctor` passa, mas a inicialização MCP tenta executar no Linux um caminho de drive como `C:\Users\...\cua-driver.exe`.

## Causa raiz

A invocação cruza dois domínios:

1. Hermes/ POSIX resolve `driver_cmd` para um wrapper WSL.
2. O wrapper inicia o driver nativo do Windows.
3. `cua-driver manifest` anuncia o executável Win32 em `mcp_invocation.command`.
4. Se o backend aceitar esse campo literalmente, `subprocess` no POSIX tenta executar a string de drive-letter, em vez do wrapper já resolvido.

`doctor` comprova que o wrapper consegue executar o binário; sozinho, não comprova que o subprocesso MCP derivado do manifest reutiliza esse comando.

## Correção preferida no backend

Mantenha os argumentos do manifest autoritativos, mas normalize seu comando na fronteira POSIX/Windows:

- Preserve o `driver_cmd` já resolvido quando o manifest retorna autorreferência genérica (`cua-driver`).
- Em POSIX, preserve `driver_cmd` quando o manifest retorna um caminho absoluto Win32/UNC para o mesmo driver.
- Continue respeitando um helper explicitamente diferente.
- Nunca descarte nem reescreva os argumentos do manifest sem necessidade.

Regra conceitual:

```python
manifest_cmd, manifest_args = read_manifest(driver_cmd)
if manifest_cmd_is_self_reference(manifest_cmd, host="posix"):
    command = driver_cmd
else:
    command = manifest_cmd
return command, manifest_args
```

## Fallback no wrapper

Se o core não puder ser alterado imediatamente, intercepte apenas `manifest` no wrapper WSL:

```bash
#!/usr/bin/env bash
set -euo pipefail

WINDOWS_CUA='/mnt/c/path/to/cua-driver.exe'
export WRAPPER_PATH="$HOME/.local/bin/cua-driver"

if [[ "${1-}" == manifest ]]; then
  "$WINDOWS_CUA" "$@" | /usr/bin/python3 -c '
import json, os, sys
payload = json.load(sys.stdin)
invocation = payload.get("mcp_invocation")
if isinstance(invocation, dict):
    invocation["command"] = os.environ["WRAPPER_PATH"]
json.dump(payload, sys.stdout, separators=(",", ":"))
'
  exit
fi

exec "$WINDOWS_CUA" "$@"
```

O invariante é: `mcp_invocation.command` devolvido ao Linux precisa ser executável pelo Linux.

## Cobertura de regressão

Cubra separadamente:

1. `command: "cua-driver"` mantém o wrapper resolvido e usa os args do manifest.
2. `command: "C:\\...\\cua-driver.exe"` em POSIX mantém o wrapper e usa os args.
3. Um helper genuinamente diferente continua autoritativo.
4. Manifest ausente/inválido cai no fallback já resolvido.

No incidente de referência, a classe direcionada terminou com `9 passed` usando explicitamente o Python Linux.

## Verificação ponta a ponta

Não pare no check de instalação:

```text
cua-driver manifest
hermes computer-use doctor
computer_use(action="list_apps")
computer_use(action="capture", app="Taskmgr.exe", mode="som")
```

Confirme que o manifest aponta para o wrapper WSL e que um app Windows real pode ser enumerado e capturado. Isso valida discovery, manifest, subprocesso MCP, UIAutomation e Windows Graphics Capture como uma cadeia.

## Recuperação de sessão

Se chamadas one-shot do driver continuam saudáveis, mas o cliente persistente fica vazio após diagnóstico de baixo nível:

- Não mate os aplicativos Windows nem o daemon interativo de autostart.
- Encerre no máximo o proxy dedicado `cua-driver.exe mcp` uma vez e permita reconexão.
- Se o processo pai mantiver estado antigo, inicie uma nova conversa Hermes depois de confirmar `doctor` e enumeração one-shot.
- Trate isso como recuperação do cliente, não como indisponibilidade do Windows ou do bridge.
