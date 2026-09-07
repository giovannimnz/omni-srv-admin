"""VS Code MCP templates must not carry deployable secrets."""

from pathlib import Path
import json


REPO = Path(__file__).resolve().parents[3]
CONFIG = REPO / "vscode-profile" / ".github" / "mcp-config" / "linux" / "mcp.json"


def test_postgres_mcp_uses_podman_and_secret_input() -> None:
    data = json.loads(CONFIG.read_text())
    for name in ("postgres", "postgres-horistic"):
        server = data["servers"][name]
        assert server["command"] == "podman"
        assert "${input:atius-postgres-password}" in server["env"]["DATABASE_URI"]
        assert "docker" not in server["command"]


def test_sensitive_mcp_values_are_prompted_and_hidden() -> None:
    data = json.loads(CONFIG.read_text())
    inputs = {entry["id"]: entry for entry in data["inputs"]}
    assert inputs["atius-postgres-password"]["type"] == "promptString"
    assert inputs["atius-postgres-password"]["password"] is True
    assert inputs["brave-api-key"]["type"] == "promptString"
    assert inputs["brave-api-key"]["password"] is True
    assert data["servers"]["brave"]["env"]["BRAVE_API_KEY"] == "${input:brave-api-key}"


def test_mcp_template_has_no_inline_sensitive_values() -> None:
    data = json.loads(CONFIG.read_text())
    for server in data["servers"].values():
        for field in ("env", "headers"):
            for key, value in server.get(field, {}).items():
                if any(token in key.upper() for token in ("PASSWORD", "TOKEN", "SECRET", "KEY", "DATABASE_URI", "DSN")):
                    assert isinstance(value, str)
                    assert "${input:" in value or "PLACEHOLDER" in value or value == "${GITHUB_PERSONAL_ACCESS_TOKEN}"
