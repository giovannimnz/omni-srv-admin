from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, TextIO

_CLI_ROOT = Path(__file__).resolve().parents[1]
if str(_CLI_ROOT) not in sys.path:
    sys.path.insert(0, str(_CLI_ROOT))

from omni.routine_mcp import RoutineMcpHandler


class RoutineMcpServer:
    """Servidor MCP sobre stdio implementando JSON-RPC 2.0 para orquestração de rotinas."""

    PROTOCOL_VERSION = "2024-11-05"
    SERVER_NAME = "omni-routine"
    SERVER_VERSION = "1.0.0"

    TOOLS_SPEC = [
        {
            "name": "omni_routine_list",
            "description": "Lista rotinas operacionais cadastradas no catálogo da frota ATIUS.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "host_id": {
                        "type": "string",
                        "description": "Filtro opcional por host alvo (ex: atius-srv-1, giovanni-w11-pc).",
                    }
                },
            },
        },
        {
            "name": "omni_routine_trigger",
            "description": "Dispara ou simula uma rotina operacional na frota ATIUS com contenção de CPU, locks e fallback SSH.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "routine_id": {
                        "type": "string",
                        "description": "ID canônico da rotina (ex: srv1:backup-gdrive, srv1:sync-vault).",
                    },
                    "target_host": {
                        "type": "string",
                        "description": "Host alvo opcional para override de destino.",
                    },
                    "dry_run": {
                        "type": "boolean",
                        "description": "Se true, apenas planeja a rotina sem executar alterações.",
                    },
                },
                "required": ["routine_id"],
            },
        },
        {
            "name": "omni_routine_status",
            "description": "Consulta o status detalhado, métricas e tail de saída de uma execução anterior de rotina.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "run_id": {
                        "type": "string",
                        "description": "UUID da execução retornado no disparo.",
                    }
                },
                "required": ["run_id"],
            },
        },
        {
            "name": "omni_routine_diagnose",
            "description": "Diagnostica falhas, status de circuit breaker e saúde de execução de rotinas.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "routine_id": {
                        "type": "string",
                        "description": "ID canônico da rotina para verificar circuit breaker.",
                    },
                    "run_id": {
                        "type": "string",
                        "description": "UUID opcional de execução para inspecionar erro específico.",
                    },
                },
            },
        },
    ]

    def __init__(self, handler: RoutineMcpHandler | None = None) -> None:
        self.handler = handler or RoutineMcpHandler()

    def handle_message(self, message: dict[str, Any]) -> dict[str, Any] | None:
        msg_id = message.get("id")
        method = message.get("method")
        params = message.get("params", {})

        # Notificações não recebem resposta (ex: notifications/initialized)
        if method == "notifications/initialized":
            return None

        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "protocolVersion": self.PROTOCOL_VERSION,
                    "serverInfo": {
                        "name": self.SERVER_NAME,
                        "version": self.SERVER_VERSION,
                    },
                    "capabilities": {
                        "tools": {},
                    },
                },
            }

        elif method == "ping":
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {},
            }

        elif method == "tools/list":
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "tools": self.TOOLS_SPEC,
                },
            }

        elif method == "tools/call":
            tool_name = params.get("name")
            arguments = params.get("arguments", {})
            result = self.handler.call_tool(tool_name, arguments)

            is_error = "error" in result
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(result, indent=2, ensure_ascii=False),
                        }
                    ],
                    "isError": is_error,
                },
            }

        # Método desconhecido
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "error": {
                "code": -32601,
                "message": f"Método não implementado: {method}",
            },
        }

    def run_stdio(self, stdin: TextIO | None = None, stdout: TextIO | None = None) -> None:
        in_stream = stdin or sys.stdin
        out_stream = stdout or sys.stdout

        for line in in_stream:
            line = line.strip()
            if not line:
                continue

            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                err_resp = {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {"code": -32700, "message": "Parse error: JSON inválido"},
                }
                out_stream.write(json.dumps(err_resp) + "\n")
                out_stream.flush()
                continue

            resp = self.handle_message(msg)
            if resp is not None:
                out_stream.write(json.dumps(resp, ensure_ascii=False) + "\n")
                out_stream.flush()


def main() -> None:
    server = RoutineMcpServer()
    server.run_stdio()


if __name__ == "__main__":
    main()
