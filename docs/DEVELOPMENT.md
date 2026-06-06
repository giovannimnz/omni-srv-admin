# Development

## Setup

```bash
cd /home/ubuntu/GitHub/omni-srv-admin
pip install -e cli/
```

## Run CLI from source

```bash
PYTHONPATH=cli python3 -m omni --help
PYTHONPATH=cli python3 -m omni fleet list
PYTHONPATH=cli python3 -m omni remote-manager list
```

## Validate Python

```bash
python3 -m compileall -q cli/omni
```

## Validate inventory

```bash
python3 - <<'PY'
from pathlib import Path
import yaml
for root in ['inventory/hosts', 'inventory/remotes', 'modules/fleet/configs']:
    for path in Path(root).glob('*.yaml'):
        yaml.safe_load(path.read_text())
        print('ok', path)
PY
```

## Add a host

1. Create `inventory/hosts/<id>.yaml`.
2. Add aliases, role, status, platform, access, modules.
3. Run `omni fleet list`.
4. Add docs if host has special constraints.

## Add a remote

1. Create `inventory/remotes/<id>.yaml`.
2. Include `source`, `mount_path`, `display_label`.
3. Run `omni remote-manager list`.
4. If GUI visible, add/rename GTK bookmark via `omni remote-manager rename-label`.

## Add a CLI module

1. Create `cli/omni/<module>.py`.
2. Expose a `click.group(name='<module-name>')`.
3. Import in `cli/omni/cli.py`.
4. Register with `cli.add_command(...)`.
5. Add module docs in `modules/<module>/README.md`.
6. Add GitHub docs under `docs/`.
7. Validate with `PYTHONPATH=cli python3 -m omni <module> --help`.

## Coding style

- PT-BR docs.
- Python CLI code can stay English for identifiers.
- No secrets in docs.
- No destructive command without `--dry-run` or explicit confirmation.
- Prefer stdlib + Click. Avoid new dependencies unless necessary.

## Commit discipline

Before commit:

```bash
git status --short
python3 -m compileall -q cli/omni
PYTHONPATH=cli python3 -m omni fleet status
PYTHONPATH=cli python3 -m omni remote-manager status
PYTHONPATH=cli python3 -m omni srv1-ops list
```

Then update vault worklog.
