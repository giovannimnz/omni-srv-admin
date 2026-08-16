# Verified cross-runtime gateway send (Windows → WSL)

Use when the current Hermes conversation runs natively on Windows, but gateway platforms and credentials are authoritative in a WSL distro.

## Detection

Run both status checks. These are different runtimes and may legitimately disagree:

```powershell
hermes gateway status
wsl.exe -d Ubuntu-24.04 -- bash -lc 'hermes gateway status && hermes status --all'
```

A disabled Windows Scheduled Task plus `No gateway process detected` is not a failure when the WSL systemd gateway is active. Do not create a second gateway.

`hermes status --all` in WSL is the useful read-only source for:

- active service manager/PID;
- configured messaging platforms;
- the home platform/channel;
- active session count.

Redact credentials if any config is inspected. Status output should not be used as a reason to print API keys.

## Delivery

Create a UTF-8 text report on Windows, then address it from WSL through `/mnt/c`:

```powershell
wsl.exe -d Ubuntu-24.04 -- bash -lc `
  'hermes send --to telegram --subject "[System report]" --file /mnt/c/Users/<user>/AppData/Local/Temp/report.txt --json'
```

Target forms supported by `hermes send`:

- `telegram` — configured home channel;
- `telegram:<chat_id>`;
- `telegram:<chat_id>:<thread_id>`;
- analogous platform/channel targets for Discord, Slack, Signal, etc.

Prefer `--to <platform>` when the user asks for the gateway/home channel and WSL status confirms that platform. Use an explicit ID only when the user named a different destination.

## Verification contract

Do not report success from command dispatch or exit code alone. Require a response shaped like:

```json
{
  "success": true,
  "platform": "telegram",
  "chat_id": "...",
  "message_id": "..."
}
```

Report platform and message ID; avoid unnecessarily echoing private chat IDs in broad/public contexts.

## Report shape

For a long technical session, send a compact handoff rather than the raw transcript:

1. subject/system;
2. final configuration/state;
3. measured results and caveats;
4. unresolved incidents/risks;
5. authoritative Obsidian paths and GBrain slugs;
6. explicit next action/guardrail.

Exclude passwords, tokens, private hardware identifiers, and raw config secrets. Preserve those only in appropriately private authoritative records.

## Pitfalls

- Do not enable the Windows gateway merely because the native CLI cannot see the WSL process.
- Do not use the Windows Hermes config to send when the WSL profile is authoritative.
- Translate staged file paths; `C:\...` is not a valid Linux path inside `bash -lc`.
- Do not confuse `mirrored:true` with proof of a second external delivery; the returned platform/chat/message receipt is the authoritative send result.
- If `hermes send` fails, inspect the WSL platform configuration and `.env`; do not encode the transient failure as a permanent limitation.
