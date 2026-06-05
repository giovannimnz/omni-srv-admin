"""REPL interativo (estilo CLI-Anything).

Comandos disponíveis no REPL (sem o prefixo fork-sync):
    projects list
    projects show <name>
    sync <name> [--dry-run] [--deploy]
    detect <name>
    deploy <name>
    logs [--project NAME] [--tail N]
    help
    exit
"""

import shlex
import sys
import click

from fork_sync.cli import cli as cli_group, _json_output


HELP_TEXT = """\
Comandos REPL:
  projects list                       Lista projetos
  projects show <name>                Detalhes de um projeto
  sync <name> [--dry-run] [--deploy]  Sincroniza fork com upstream
  detect <name>                       Detecta novo release
  deploy <name>                       Deploy Docker
  logs [--project NAME] [--tail N]    Mostra logs
  help                                Esta ajuda
  exit                                Sair do REPL
"""


def _try_prompt_toolkit():
    """Tenta importar prompt_toolkit; cai de volta para input() se não tiver."""
    try:
        from prompt_toolkit import PromptSession
        from prompt_toolkit.completion import WordCompleter
        from prompt_toolkit.history import InMemoryHistory
        return PromptSession, WordCompleter, InMemoryHistory
    except ImportError:
        return None, None, None


def run_repl():
    """Loop principal do REPL."""
    PromptSession, WordCompleter, InMemoryHistory = _try_prompt_toolkit()

    commands = ["projects", "sync", "detect", "deploy", "logs", "help", "exit"]
    subcommands = ["list", "show", "add", "remove"]

    if PromptSession and WordCompleter and InMemoryHistory:
        _completer = WordCompleter(commands + subcommands, ignore_case=True)
        _history = InMemoryHistory()
        _session = PromptSession(history=_history, completer=_completer)

        def _prompt():
            return _session.prompt("fork-sync> ")
    else:
        def _prompt():
            return input("fork-sync> ")

    click.echo("fork-sync REPL — digite 'help' para comandos, 'exit' para sair")
    while True:
        try:
            line = _prompt()
        except (EOFError, KeyboardInterrupt):
            click.echo("\nBye.")
            return
        line = line.strip()
        if not line:
            continue
        if line in ("exit", "quit"):
            click.echo("Bye.")
            return
        if line in ("help", "?"):
            click.echo(HELP_TEXT)
            continue
        try:
            args = shlex.split(line)
        except ValueError as e:
            click.echo(f"[parse error] {e}")
            continue
        try:
            cli_group.main(args=args, standalone_mode=False)
        except SystemExit:
            pass
        except click.ClickException as e:
            e.show()
        except Exception as e:
            click.echo(f"[error] {type(e).__name__}: {e}", err=True)
