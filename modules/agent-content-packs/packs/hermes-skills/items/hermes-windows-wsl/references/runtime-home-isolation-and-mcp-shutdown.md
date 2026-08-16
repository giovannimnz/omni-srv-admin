# Hermes Windows/WSL Runtime Isolation and MCP Shutdown

Use this reference when a Windows-native Hermes install predates a WSL migration and the WSL CLI shows database corruption, incompatible MCP paths, or shutdown tracebacks.

## Core invariant

Windows and WSL must have separate mutable Hermes homes:

```text
Windows: C:\Users\<user>\AppData\Local\hermes
WSL:    /home/<user>/.hermes
```

Never point WSL `HERMES_HOME` at `/mnt/c/...`. SQLite WAL files, locks, PIDs, logs, caches, and gateway state are runtime-local. Sharing them across Win32 and DrvFS/NTFS risks corruption and cross-process races.

Safe to copy deliberately, with platform-specific path normalization:

```text
config.yaml
.env
auth.json
SOUL.md
memories/
skills/
```

Do not share or copy as live state:

```text
state.db*
*.lock
*.pid
logs/
cache/
gateway_state.json
```

## Detect split-brain homes

Check both interactive CLI and service environments:

```bash
printf 'shell HERMES_HOME=%s\n' "$HERMES_HOME"
hermes config path
hermes config env-path
systemctl cat hermes-gateway.service
```

The WSL CLI and WSL gateway should all resolve to `/home/<user>/.hermes`. A gateway may be correct while login shells are wrong if a cross-platform `common-env.sh` imports Windows `LOCALAPPDATA` and derives `HERMES_HOME` from it.

For a shared shell config, branch explicitly and override imported Windows state in WSL:

```sh
if is_wsl_shell; then
  export HERMES_HOME="${HERMES_HOME_WSL:-$HOME/.hermes}"
else
  export HERMES_HOME="$(shell_host_path "${HERMES_HOME:-$LOCALAPPDATA/hermes}")"
fi
```

Do not use `${HERMES_HOME:-...}` in the WSL branch: an earlier Windows-environment sync may already have populated it.

## MCP path normalization

A copied config may contain Win32 arguments such as:

```yaml
command: node
args:
  - 'C:\Users\user\service\server.js'
```

Normalize only the WSL copy:

```yaml
command: node
args:
  - /mnt/c/Users/user/service/server.js
```

HTTP MCP URLs usually need no platform change. Keep `${VAR}` references intact and never materialize bearer tokens in documentation.

## Database recovery rule

If `hermes doctor` reports `database disk image is malformed`, b-tree failures, invalid pages, or freelist errors, treat it as physical corruption—not merely stale FTS.

1. Stop writers.
2. Preserve `state.db`, `state.db-wal`, and `state.db-shm` as raw evidence.
3. Work only on a copy on the WSL ext4 filesystem.
4. Try SQLite recovery:

```bash
sqlite3 corrupt-copy.db '.recover --ignore-freelist' > recovered.sql
sqlite3 recovered.db < recovered.sql
sqlite3 recovered.db 'PRAGMA integrity_check;'
```

5. Require `integrity_check = ok` and non-zero canonical `sessions`/`messages` counts before promotion.
6. Never run destructive `VACUUM`, `DROP`, or in-place repair on the only copy.

`hermes sessions repair` is appropriate for malformed schema or FTS reconstruction; broad b-tree/page corruption needs `.recover` or restoration from backup first.

## Local Windows symptom signatures worth recognizing early

Treat the following as strong evidence that the local session store itself is broken, not that the current task's model/provider/MCP setup is wrong:

- `session_search` fails with an FTS message like:
  - `fts5: corruption found reading blob ... from table messages_fts`
- `hermes sessions stats` fails with:
  - `sqlite3.DatabaseError: database disk image is malformed`
- `hermes doctor` reports:
  - `state.db fails a write-health probe (FTS index may be corrupt)`
- `hermes sessions repair` fails and leaves a `.malformed-backup-*` artifact

Practical response order on Windows:
1. backup `C:\Users\<user>\AppData\Local\hermes\state.db`
2. run `hermes doctor`
3. run `hermes sessions stats`
4. run `hermes sessions repair`
5. if repair still fails with `database disk image is malformed`, keep both the original DB and the generated malformed-backup copy and escalate to SQLite salvage/rebuild

Do not keep retrying Hermes-level history commands after those signatures are confirmed.

## Why `/exit` may show `Event loop is closed`

A distinct Hermes ownership bug can amplify broken MCP config:

1. `MCPServerTask.run()` parks after exhausting initial-connect retries.
2. `_discover_and_register_server()` records the instance in `_servers` only after `_connect_server()` succeeds.
3. If startup raises, the parked task can remain unregistered.
4. Final shutdown snapshots `_servers`, misses the detached task, and closes the MCP event loop.
5. Coroutine finalization then calls `cancel()` on the closed loop.

Typical signature:

```text
Exception ignored in: <coroutine object MCPServerTask.run ...>
... _wait_for_reconnect_or_shutdown ...
t.cancel()
RuntimeError: Event loop is closed
```

The ownership-safe implementation is to clean up the server if initial start fails before re-raising the original exception:

```python
async def _connect_server(name: str, config: dict) -> MCPServerTask:
    server = MCPServerTask(name)
    try:
        await server.start(config)
    except BaseException:
        try:
            await server.shutdown()
        except BaseException:
            logger.debug(
                "MCP server '%s': cleanup after failed start also failed",
                name,
                exc_info=True,
            )
        raise
    return server
```

Catch `BaseException` so `asyncio.CancelledError` also transfers through cleanup. Add a regression test proving a failed `start()` leaves no pending task and that the original exception is preserved.

## Windows-local teardown hardening pattern

A second, simpler shutdown-only variant can happen even without cross-runtime ownership issues: helper wait tasks inside `tools/mcp_tool.py` may reach their `finally` blocks after the loop is already closing. In that case, `task.cancel()` itself can raise `RuntimeError('Event loop is closed')`.

Defensive patch pattern:
- centralize cleanup in a helper like `_cancel_task_and_wait(task)`
- no-op if the task is already done
- check `task.get_loop().is_closed()` before calling `cancel()`
- swallow `RuntimeError` during final cleanup
- use the helper consistently in lifecycle waiter cleanup paths such as:
  - `_wait_for_lifecycle_event()`
  - `_wait_for_reconnect_or_shutdown()`
  - `_wait_for_lazy_reconnect()`

Validation:

```bash
python -m py_compile C:/Users/<user>/AppData/Local/hermes/hermes-agent/tools/mcp_tool.py
```

Then reproduce a normal Hermes exit and confirm the ignored-exception traceback is gone.

## End-to-end verification

After isolation and recovery:

```bash
zsh -lic 'echo "$HERMES_HOME"; hermes config path; hermes doctor'
findmnt -T /home/<user>/.hermes/state.db
sqlite3 /home/<user>/.hermes/state.db 'PRAGMA integrity_check;'
hermes mcp list
hermes gateway status
```

Then launch Hermes in a PTY/tmux session, let MCP discovery finish, send `/exit`, and assert the captured output contains none of:

```text
RuntimeError: Event loop is closed
Task was destroyed but it is pending
Exception ignored in: <coroutine object MCPServerTask.run
```
