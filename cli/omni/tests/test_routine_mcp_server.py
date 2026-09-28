"""Tests for Omni Routine Stdio MCP Server."""
from __future__ import annotations

import io
import json
from pathlib import Path
from unittest.mock import patch
import pytest

from omni.routine_mcp_server import RoutineMcpServer


def test_mcp_server_initialize() -> None:
    server = RoutineMcpServer()
    req = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "test-client", "version": "1.0.0"},
        },
    }
    resp = server.handle_message(req)
    assert resp is not None
    assert resp["id"] == 1
    assert resp["result"]["serverInfo"]["name"] == "omni-routine"
    assert resp["result"]["protocolVersion"] == "2024-11-05"
    assert "tools" in resp["result"]["capabilities"]


def test_mcp_server_tools_list() -> None:
    server = RoutineMcpServer()
    req = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/list",
        "params": {},
    }
    resp = server.handle_message(req)
    assert resp is not None
    assert resp["id"] == 2
    tools = resp["result"]["tools"]
    tool_names = [t["name"] for t in tools]
    assert "omni_routine_list" in tool_names
    assert "omni_routine_trigger" in tool_names
    assert "omni_routine_status" in tool_names
    assert "omni_routine_diagnose" in tool_names


def test_mcp_server_tools_call_list() -> None:
    server = RoutineMcpServer()
    req = {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {
            "name": "omni_routine_list",
            "arguments": {},
        },
    }
    resp = server.handle_message(req)
    assert resp is not None
    assert resp["id"] == 3
    content = resp["result"]["content"]
    assert len(content) == 1
    data = json.loads(content[0]["text"])
    assert "routines" in data
    assert any(r["id"] == "srv1:backup-gdrive" for r in data["routines"])


def test_mcp_server_tools_call_trigger_dry_run() -> None:
    server = RoutineMcpServer()
    req = {
        "jsonrpc": "2.0",
        "id": 4,
        "method": "tools/call",
        "params": {
            "name": "omni_routine_trigger",
            "arguments": {
                "routine_id": "srv1:backup-gdrive",
                "dry_run": True,
            },
        },
    }
    resp = server.handle_message(req)
    assert resp is not None
    assert resp["id"] == 4
    content = resp["result"]["content"]
    data = json.loads(content[0]["text"])
    assert data.get("status") == "planned"
    assert data.get("dry_run") is True
    assert data.get("routine_id") == "srv1:backup-gdrive"


def test_mcp_server_stdio_stream() -> None:
    input_stream = io.StringIO(
        json.dumps({"jsonrpc": "2.0", "id": 10, "method": "ping"}) + "\n" +
        json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n"
    )
    output_stream = io.StringIO()

    server = RoutineMcpServer()
    server.run_stdio(stdin=input_stream, stdout=output_stream)

    output = output_stream.getvalue().strip()
    lines = [json.loads(line) for line in output.splitlines() if line.strip()]
    assert len(lines) == 1  # notifications do not reply
    assert lines[0]["id"] == 10
    assert lines[0]["result"] == {}
