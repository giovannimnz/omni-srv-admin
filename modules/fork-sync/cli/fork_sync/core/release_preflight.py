"""Release/deploy preflight checks for fork sends.

The checks are intentionally static and conservative. They catch deterministic
CI failures before a tag, push, or deploy triggers GitHub Actions.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


FOUR_PART_VERSION = re.compile(r"^v?[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+(?:[-+].*)?$")
PUSH_LIKE_MODES = {"push", "release", "deploy", "fork-deploy", "tag"}
MAX_SECRET_SCAN_BYTES = 512 * 1024
ATIUS_ROUTER_DOCS_LINK_FILES = [
    "controller/misc.go",
    "setting/operation_setting/general_setting.go",
    "web/default/src/hooks/use-top-nav-links.ts",
    "web/default/src/lib/docs-link.ts",
    "web/default/src/components/layout/types.ts",
    "web/default/src/components/layout/components/nav-link-item.tsx",
    "web/default/src/components/layout/components/top-nav.tsx",
    "web/default/src/components/layout/components/public-header.tsx",
    "web/default/src/components/layout/components/public-navigation.tsx",
    "web/default/src/components/layout/components/mobile-drawer.tsx",
    "web/default/src/features/home/components/sections/hero.tsx",
    "web/default/src/components/layout/components/footer.tsx",
    "web/default/src/features/system-settings/general/quota-settings-section.tsx",
    "web/classic/src/helpers/docs.js",
    "web/classic/src/hooks/common/useNavigation.js",
    "web/classic/src/components/layout/headerbar/index.jsx",
    "web/classic/src/components/layout/headerbar/Navigation.jsx",
    "web/classic/src/pages/Home/index.jsx",
    "web/classic/src/components/layout/Footer.jsx",
    "web/classic/src/pages/Setting/Operation/SettingsGeneral.jsx",
    "docs/atius-router-docs/src/lib/i18n.ts",
    "docs/atius-router-docs/next.config.mjs",
    "docs/atius-router-docs/middleware.ts",
    "docs/atius-router-docs/src/app/json/route.ts",
    "docs/atius-router-docs/src/app/[lang]/layout.tsx",
    "docs/atius-router-docs/src/app/[lang]/(home)/layout.tsx",
    "docs/atius-router-docs/src/components/footer.tsx",
    "docs/atius-router-docs/content/docs/pt/guide/index.mdx",
    "docs/atius-router-docs/content/docs/pt/guide/meta.json",
    "docs/atius-router-docs/content/docs/pt/guide/project-introduction.mdx",
    "docs/atius-router-docs/content/docs/pt/guide/technical-architecture.mdx",
]
ATIUS_ROUTER_DOCS_PROTECTED_FILES = [
    *ATIUS_ROUTER_DOCS_LINK_FILES,
    "scripts/smoke-docs-links.sh",
]
ATIUS_ROUTER_PT_BR_REQUIRED_FILES = [
    "i18n/locales/pt.yaml",
    "i18n/i18n.go",
    "web/default/src/i18n/config.ts",
    "web/default/src/i18n/languages.ts",
    "web/default/src/i18n/locales/pt.json",
    "web/default/scripts/sync-i18n.mjs",
    "web/classic/src/i18n/i18n.js",
    "web/classic/src/i18n/language.js",
    "web/classic/src/i18n/locales/pt.json",
    "web/classic/src/components/layout/headerbar/LanguageSelector.jsx",
    "web/classic/src/components/settings/personal/cards/PreferencesSettings.jsx",
    "scripts/smoke-pt-br-i18n.sh",
]
ATIUS_ROUTER_USER_QUOTA_ADMISSION_FILES = [
    "service/pre_consume_quota.go",
    "service/billing_session.go",
    "service/quota.go",
    "relay/mjproxy_handler.go",
]
ATIUS_ROUTER_USER_QUOTA_REQUIRED_FILES = [
    *ATIUS_ROUTER_USER_QUOTA_ADMISSION_FILES,
    "service/billing_session_wallet_overdraft_test.go",
    "scripts/atius-user-quota-guard.sh",
    "patches/atius-user-quota-unlimited.patch",
    "docs/ATIUS-USER-QUOTA-INVARIANT.md",
]
ATIUS_ROUTER_USER_QUOTA_FORBIDDEN_MARKERS = [
    "model.GetUserQuota(",
    "ErrorCodeInsufficientUserQuota",
    '"insufficient_user_quota"',
    '"quota_not_enough"',
    "UserActiveSubscriptionsAllowWalletOverflow(",
]
ATIUS_ROUTER_USER_QUOTA_SCOPED_FUNCTIONS = {
    # Other admission files are scanned in full. quota.go also contains
    # permitted post-accounting notification code that reads UserQuota.
    "service/quota.go": ["PreWssConsumeQuota"],
}
ATIUS_ROUTER_RERANK_REQUIRED_FILES = [
    "dto/channel_settings.go",
    "dto/channel_settings_tei_rerank_test.go",
    "k8s/router-ai-atius/configmap.yaml",
    "relay/channel/advancedcustom/adaptor.go",
    "relay/channel/advancedcustom/tei_rerank.go",
    "relay/channel/advancedcustom/tei_rerank_test.go",
    "relay/embedding_handler_test.go",
    "relay/rerank_handler.go",
    "service/embeddinggovernor/governor.go",
    "service/embeddinggovernor/governor_test.go",
]
ATIUS_ROUTER_RERANK_PROTECTED_PATHS = [
    "dto/channel_settings.go",
    "dto/channel_settings_tei_rerank_test.go",
    "k8s/router-ai-atius/configmap.yaml",
    "relay/channel/advancedcustom/",
    "relay/embedding_handler_test.go",
    "relay/rerank_handler.go",
    "service/embeddinggovernor/",
]
ATIUS_ROUTER_RERANK_REQUIRED_MARKERS = {
    "dto/channel_settings.go": [
        "AdvancedCustomConverterJinaRerankToTEINative",
        '"jina_rerank_to_tei_native"',
    ],
    "k8s/router-ai-atius/configmap.yaml": [
        "EMBEDDING_GOVERNOR_MODELS",
        "embedding-gte-v1,reranker-gte-multilingual-v1",
    ],
    "relay/channel/advancedcustom/tei_rerank.go": [
        "newTEIRerankRequest",
        "doTEIRerankResponse",
    ],
    "relay/rerank_handler.go": [
        "acquireRerankGovernor",
        "maxGovernedTEIRerankDocuments",
    ],
    "service/embeddinggovernor/governor.go": [
        "embedding-gte-v1,reranker-gte-multilingual-v1",
    ],
}
SECRET_VALUE_PATTERNS = [
    re.compile(
        r"-----BEGIN (?:RSA |DSA |EC |OPENSSH |PRIVATE )?PRIVATE KEY-----\s+"
        r"[A-Za-z0-9+/=\r\n]{80,}\s+"
        r"-----END (?:RSA |DSA |EC |OPENSSH |PRIVATE )?PRIVATE KEY-----"
    ),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bghp_[A-Za-z0-9_]{30,}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{32,}\b"),
    re.compile(r"\bctx7sk-[A-Za-z0-9_-]{20,}\b"),
]


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="replace")


def _load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        import yaml

        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        data: dict[str, Any] = {}
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if ":" not in line or line.lstrip() != line:
                continue
            key, value = line.split(":", 1)
            data[key.strip()] = value.split("#", 1)[0].strip().strip("'\"")
        return data


def _git_output(repo: Path, args: list[str], *, timeout: int = 10) -> str | None:
    try:
        proc = subprocess.run(
            ["git", "-C", str(repo), *args],
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout


def _github_slug_from_remote(repo: Path) -> str | None:
    stdout = _git_output(repo, ["remote", "get-url", "origin"])
    if stdout is None:
        return None
    url = stdout.strip()
    patterns = [
        r"github\.com[:/](?P<owner>[^/]+)/(?P<repo>[^/.]+)(?:\.git)?$",
        r"github\.com/(?P<owner>[^/]+)/(?P<repo>[^/.]+)(?:\.git)?$",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return f"{match.group('owner')}/{match.group('repo')}"
    return None


def _git_status(repo: Path) -> list[str] | None:
    stdout = _git_output(repo, ["status", "--porcelain", "--untracked-files=all"])
    if stdout is None:
        return None
    return [line for line in stdout.splitlines() if line.strip()]


def _git_tracked_files(repo: Path) -> list[str]:
    stdout = _git_output(repo, ["ls-files", "-z"])
    if stdout is None:
        return []
    return [item for item in stdout.split("\0") if item]


def _is_sensitive_path(path: str) -> bool:
    lowered = path.replace("\\", "/").lower()
    name = Path(lowered).name
    if any(marker in name for marker in ("example", "sample", "template", "dist")):
        return False
    if name in {"id_rsa", "id_dsa", "id_ecdsa", "id_ed25519", "auth.json", "credentials.json"}:
        return True
    if name.startswith(".env"):
        return True
    if name.startswith("secrets.") or "/secrets/" in lowered:
        return True
    if name.endswith((".pem", ".p12", ".pfx")):
        return True
    if name.endswith(".key") and not name.endswith(".pub"):
        return True
    return False


def _tracked_sensitive_paths(repo: Path) -> list[str]:
    return [path for path in _git_tracked_files(repo) if _is_sensitive_path(path)]


def _tracked_secret_hits(repo: Path) -> list[dict[str, str]]:
    hits: list[dict[str, str]] = []
    for rel in _git_tracked_files(repo):
        path = repo / rel
        try:
            if path.stat().st_size > MAX_SECRET_SCAN_BYTES:
                continue
            raw = path.read_bytes()
        except OSError:
            continue
        if b"\0" in raw:
            continue
        text = raw.decode("utf-8", errors="ignore")
        for pattern in SECRET_VALUE_PATTERNS:
            if pattern.search(text):
                hits.append({"path": rel, "pattern": pattern.pattern})
                break
    return hits


def _secret_names(github_repo: str | None) -> tuple[set[str] | None, str | None]:
    if not github_repo:
        return None, "github repo slug unavailable; secret checks are static only"
    try:
        proc = subprocess.run(
            ["gh", "secret", "list", "--repo", github_repo],
            text=True,
            capture_output=True,
            timeout=20,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        return None, f"could not list GitHub secrets for {github_repo}: {exc}"
    if proc.returncode != 0:
        return None, f"could not list GitHub secrets for {github_repo}: {proc.stderr.strip()}"
    names = {line.split()[0] for line in proc.stdout.splitlines() if line.strip()}
    return names, None


def _workflow_files(repo: Path) -> list[Path]:
    workflows = repo / ".github" / "workflows"
    if not workflows.exists():
        return []
    return sorted(
        path
        for path in workflows.iterdir()
        if path.is_file() and path.suffix.lower() in {".yml", ".yaml"}
    )


def _has_web_build_script(repo: Path) -> bool:
    pkg = _load_json(repo / "web" / "package.json")
    scripts = pkg.get("scripts") if isinstance(pkg.get("scripts"), dict) else {}
    return bool(scripts.get("build"))


def _uses_web_root_bun_build(text: str) -> bool:
    if re.search(r"working-directory:\s*web\b[\s\S]{0,500}?bun\s+run\s+build", text):
        return True
    return bool(re.search(r"cd\s+web\b[\s\S]{0,500}?bun\s+(?:--[^\n]+\s+)*run\s+build", text))


def _dockerhub_refs(text: str) -> bool:
    return "DOCKERHUB_USERNAME" in text or "DOCKERHUB_TOKEN" in text


def _dockerhub_guarded(text: str) -> bool:
    if "dockerhub_enabled" in text.lower():
        return True
    if re.search(r"if:\s*.*dockerhub", text, flags=re.IGNORECASE):
        return True
    if re.search(r"if:\s*\$\{\{[^}]*DOCKERHUB", text):
        return True
    return False


def _uses_raw_npm_version(text: str) -> bool:
    return "npm version" in text and "normalize-electron-version" not in text


def _pull_request_target_risks(text: str) -> tuple[list[str], list[str]]:
    if "pull_request_target" not in text:
        return [], []
    errors = []
    warnings = ["pull_request_target requires explicit security review"]
    if "secrets." in text:
        errors.append("pull_request_target workflow references secrets")
    if "actions/checkout" in text:
        errors.append("pull_request_target workflow checks out code")
    if re.search(r"permissions:\s*write-all\b", text):
        errors.append("pull_request_target workflow grants write-all permissions")
    if re.search(r"\bcontents:\s*write\b", text):
        errors.append("pull_request_target workflow grants contents: write")
    return errors, warnings


def _atius_router_docs_link_violations(repo: Path) -> list[Path]:
    """Detect regressions that send Router Docs buttons back to upstream docs."""
    violations: list[Path] = []
    for rel in ATIUS_ROUTER_DOCS_LINK_FILES:
        path = repo / rel
        if not path.exists():
            continue
        if "docs.newapi.pro" in _read_text(path):
            violations.append(Path(rel))
    return violations


def _translation_map(path: Path) -> dict[str, Any]:
    data = _load_json(path)
    translation = data.get("translation")
    return translation if isinstance(translation, dict) else {}


def _flatten_locale(data: dict[str, Any], prefix: str = "") -> dict[str, Any]:
    flattened: dict[str, Any] = {}
    for key, value in data.items():
        path = f"{prefix}.{key}" if prefix else str(key)
        if isinstance(value, dict):
            flattened.update(_flatten_locale(value, path))
        else:
            flattened[path] = value
    return flattened


def _placeholders(value: Any) -> list[str]:
    return sorted(re.findall(r"\{\{[^}]+\}\}", str(value)))


def _locale_pair_violations(
    base: dict[str, Any],
    pt: dict[str, Any],
    *,
    pt_path: Path,
    locale_name: str,
    reject_empty_pt_values: bool = False,
) -> list[tuple[Path, str]]:
    violations: list[tuple[Path, str]] = []
    base_flat = _flatten_locale(base)
    pt_flat = _flatten_locale(pt)
    if not base_flat or not pt_flat:
        return [(pt_path, f"{locale_name} locale is empty or invalid")]
    if set(base_flat) != set(pt_flat):
        return [(pt_path, f"PT-BR {locale_name} keys differ from base locale")]
    for key, base_value in base_flat.items():
        pt_value = pt_flat[key]
        if reject_empty_pt_values and (
            pt_value is None or (isinstance(pt_value, str) and not pt_value.strip())
        ):
            violations.append((pt_path, f"empty PT-BR value for key: {key}"))
            break
        if _placeholders(base_value) != _placeholders(pt_value):
            violations.append((pt_path, f"placeholder drift for key: {key}"))
            break
    return violations


def _atius_router_pt_br_violations(repo: Path) -> list[tuple[Path, str]]:
    violations: list[tuple[Path, str]] = []
    for rel in ATIUS_ROUTER_PT_BR_REQUIRED_FILES:
        if not (repo / rel).is_file():
            violations.append((Path(rel), "required PT-BR file is missing"))

    markers = {
        "i18n/i18n.go": ["LangPt", "locales/pt.yaml", "strings.HasPrefix(lang, \"pt\")"],
        "web/default/src/i18n/config.ts": [
            "import pt from './locales/pt.json'",
            "supportedLngs:",
            "'pt'",
        ],
        "web/default/src/i18n/languages.ts": [
            "code: 'pt', label: 'Português'",
            "normalized.startsWith('pt')",
        ],
        "web/classic/src/i18n/i18n.js": ["ptTranslation", "pt: ptTranslation"],
        "web/classic/src/i18n/language.js": ["'pt'", "lower.startsWith('pt')"],
        "web/classic/src/components/layout/headerbar/LanguageSelector.jsx": [
            "onLanguageChange('pt')",
            "Português",
        ],
        "web/classic/src/components/settings/personal/cards/PreferencesSettings.jsx": [
            "value: 'pt'",
            "Português",
        ],
    }
    for rel, expected in markers.items():
        path = repo / rel
        if not path.is_file():
            continue
        text = _read_text(path)
        missing = [marker for marker in expected if marker not in text]
        if missing:
            violations.append((Path(rel), f"missing PT-BR registration: {missing[0]}"))

    backend_base = _load_yaml(repo / "i18n/locales/en.yaml")
    backend_pt = _load_yaml(repo / "i18n/locales/pt.yaml")
    violations.extend(
        _locale_pair_violations(
            backend_base,
            backend_pt,
            pt_path=Path("i18n/locales/pt.yaml"),
            locale_name="backend YAML",
        )
    )

    locale_pairs = [
        (
            "web/default/src/i18n/locales/en.json",
            "web/default/src/i18n/locales/pt.json",
        ),
        (
            "web/classic/src/i18n/locales/en.json",
            "web/classic/src/i18n/locales/pt.json",
        ),
    ]
    for base_rel, pt_rel in locale_pairs:
        base = _translation_map(repo / base_rel)
        pt = _translation_map(repo / pt_rel)
        violations.extend(
            _locale_pair_violations(
                base,
                pt,
                pt_path=Path(pt_rel),
                locale_name="frontend JSON",
                reject_empty_pt_values=True,
            )
        )

    return violations


def _atius_router_user_quota_violations(repo: Path) -> list[tuple[Path, str]]:
    """Reject local request-admission decisions based on account balance.

    Accounting may still decrease or increase a wallet after a request is
    accepted.  These admission surfaces, however, must never query user quota,
    emit ``insufficient_user_quota``, or condition wallet fallback on a
    subscription overflow flag.  The Router-owned audit/repair artifacts are
    required as a second, repository-local line of defense.
    """
    violations: list[tuple[Path, str]] = []
    for rel in ATIUS_ROUTER_USER_QUOTA_REQUIRED_FILES:
        if not (repo / rel).is_file():
            violations.append(
                (Path(rel), "required user-quota invariant file is missing")
            )

    guard = repo / "scripts/atius-user-quota-guard.sh"
    if guard.is_file() and not os.access(guard, os.X_OK):
        violations.append(
            (
                Path("scripts/atius-user-quota-guard.sh"),
                "user-quota guard is not executable",
            )
        )

    for rel in ATIUS_ROUTER_USER_QUOTA_ADMISSION_FILES:
        path = repo / rel
        if not path.is_file():
            continue
        text = _read_text(path)
        for marker in ATIUS_ROUTER_USER_QUOTA_FORBIDDEN_MARKERS:
            if marker in text:
                violations.append(
                    (
                        Path(rel),
                        f"local request admission still depends on user/subscription quota: {marker}",
                    )
                )

        scoped_functions = ATIUS_ROUTER_USER_QUOTA_SCOPED_FUNCTIONS.get(rel)
        scopes: list[tuple[str, str]] = []
        if scoped_functions:
            for function_name in scoped_functions:
                body = _go_function_body(text, function_name)
                if body is not None:
                    scopes.append((function_name, body))
        else:
            scopes.append(("admission file", text))

        for scope_name, scope_text in scopes:
            code = _strip_go_comments_and_literals(scope_text)
            if re.search(r"\b(?:userQuota|UserQuota)\b", code):
                violations.append(
                    (
                        Path(rel),
                        f"local request admission reads user quota directly in {scope_name}",
                    )
                )
    return violations


def _atius_router_rerank_violations(repo: Path) -> list[tuple[Path, str]]:
    """Fail closed when a sync drops the governed local reranker contract."""
    violations: list[tuple[Path, str]] = []
    for rel in ATIUS_ROUTER_RERANK_REQUIRED_FILES:
        path = repo / rel
        if not path.is_file():
            violations.append((Path(rel), "required governed reranker file is missing"))
            continue
        text = _read_text(path)
        for marker in ATIUS_ROUTER_RERANK_REQUIRED_MARKERS.get(rel, []):
            if marker not in text:
                violations.append(
                    (Path(rel), f"governed reranker contract marker is missing: {marker}")
                )
    return violations


def _go_function_body(text: str, function_name: str) -> str | None:
    declaration = re.search(
        rf"\bfunc\s+(?:\([^)]*\)\s*)?{re.escape(function_name)}\s*\(",
        text,
    )
    if declaration is None:
        return None
    brace = text.find("{", declaration.end())
    if brace < 0:
        return None

    depth = 0
    state = "code"
    index = brace
    while index < len(text):
        char = text[index]
        nxt = text[index + 1] if index + 1 < len(text) else ""
        if state == "code":
            if char == "/" and nxt == "/":
                state = "line-comment"
                index += 2
                continue
            if char == "/" and nxt == "*":
                state = "block-comment"
                index += 2
                continue
            if char == '"':
                state = "string"
            elif char == "'":
                state = "rune"
            elif char == "`":
                state = "raw-string"
            elif char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    return text[brace + 1 : index]
        elif state == "line-comment":
            if char == "\n":
                state = "code"
        elif state == "block-comment":
            if char == "*" and nxt == "/":
                state = "code"
                index += 2
                continue
        elif state in {"string", "rune"}:
            if char == "\\":
                index += 2
                continue
            terminator = '"' if state == "string" else "'"
            if char == terminator:
                state = "code"
        elif state == "raw-string" and char == "`":
            state = "code"
        index += 1
    return None


def _strip_go_comments_and_literals(text: str) -> str:
    """Keep Go code tokens while blanking comments and string/rune literals."""
    output: list[str] = []
    state = "code"
    index = 0
    while index < len(text):
        char = text[index]
        nxt = text[index + 1] if index + 1 < len(text) else ""
        if state == "code":
            if char == "/" and nxt == "/":
                output.extend("  ")
                state = "line-comment"
                index += 2
                continue
            if char == "/" and nxt == "*":
                output.extend("  ")
                state = "block-comment"
                index += 2
                continue
            if char == '"':
                output.append(" ")
                state = "string"
            elif char == "'":
                output.append(" ")
                state = "rune"
            elif char == "`":
                output.append(" ")
                state = "raw-string"
            else:
                output.append(char)
        elif state == "line-comment":
            output.append("\n" if char == "\n" else " ")
            if char == "\n":
                state = "code"
        elif state == "block-comment":
            output.append(" ")
            if char == "*" and nxt == "/":
                output.append(" ")
                state = "code"
                index += 2
                continue
        elif state in {"string", "rune"}:
            output.append("\n" if char == "\n" else " ")
            if char == "\\":
                if index + 1 < len(text):
                    output.append(" ")
                index += 2
                continue
            terminator = '"' if state == "string" else "'"
            if char == terminator:
                state = "code"
        else:
            output.append("\n" if char == "\n" else " ")
            if char == "`":
                state = "code"
        index += 1
    return "".join(output)


def _add_issue(issues: list[dict[str, str]], code: str, message: str, path: Path | None = None) -> None:
    item = {"code": code, "message": message}
    if path:
        item["path"] = str(path)
    issues.append(item)


def run_preflight(
    repo: str | Path,
    *,
    tag: str | None = None,
    mode: str = "push",
    github_repo: str | None = None,
    deploy_config: str | Path | None = None,
    secret_names: set[str] | None = None,
) -> dict[str, Any]:
    repo_path = Path(repo).expanduser().resolve()
    issues: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    checks: list[dict[str, Any]] = []

    if not repo_path.exists():
        _add_issue(issues, "repo-missing", f"repo path does not exist: {repo_path}")
        return {"status": "error", "repo": str(repo_path), "mode": mode, "errors": issues, "warnings": warnings, "checks": checks}

    origin_github_repo = _github_slug_from_remote(repo_path)
    github_repo = github_repo or origin_github_repo
    if origin_github_repo:
        checks.append({"check": "origin-github-repo", "github_repo": origin_github_repo})
    if github_repo and origin_github_repo and github_repo.lower() != origin_github_repo.lower():
        _add_issue(
            issues,
            "origin-repo-mismatch",
            f"origin points to {origin_github_repo}, but preflight target is {github_repo}",
        )

    if mode in PUSH_LIKE_MODES:
        dirty = _git_status(repo_path)
        if dirty:
            _add_issue(
                issues,
                "dirty-working-tree",
                f"repo has uncommitted changes; first entries: {', '.join(dirty[:5])}",
            )

    sensitive_paths = _tracked_sensitive_paths(repo_path)
    if sensitive_paths:
        _add_issue(
            issues,
            "tracked-sensitive-files",
            f"tracked sensitive-looking files must not be pushed: {', '.join(sensitive_paths[:8])}",
        )

    secret_hits = _tracked_secret_hits(repo_path)
    if secret_hits:
        _add_issue(
            issues,
            "tracked-secret-values",
            f"tracked files contain secret-like values: {', '.join(hit['path'] for hit in secret_hits[:8])}",
        )

    docs_link_violations = _atius_router_docs_link_violations(repo_path)
    if docs_link_violations:
        _add_issue(
            issues,
            "atius-router-docs-external-link",
            "Atius Router Docs buttons/config must use same-origin /en/docs and /pt/docs, not docs.newapi.pro",
            docs_link_violations[0],
        )
    elif any((repo_path / rel).exists() for rel in ATIUS_ROUTER_DOCS_LINK_FILES):
        checks.append({"check": "atius-router-docs-links", "status": "internal-only"})

    is_atius_router = bool(
        github_repo and github_repo.lower() == "giovannimnz/router-ai-atius"
    )
    if is_atius_router:
        pt_br_violations = _atius_router_pt_br_violations(repo_path)
        for path, message in pt_br_violations:
            _add_issue(issues, "atius-router-pt-br-regression", message, path)
        if not pt_br_violations:
            checks.append({"check": "atius-router-pt-br", "status": "complete"})

        user_quota_violations = _atius_router_user_quota_violations(repo_path)
        for path, message in user_quota_violations:
            _add_issue(issues, "atius-router-user-quota-regression", message, path)
        if not user_quota_violations:
            checks.append(
                {"check": "atius-router-user-quota-invariant", "status": "complete"}
            )

        rerank_violations = _atius_router_rerank_violations(repo_path)
        for path, message in rerank_violations:
            _add_issue(issues, "atius-router-rerank-regression", message, path)
        if not rerank_violations:
            checks.append(
                {"check": "atius-router-governed-rerank", "status": "complete"}
            )

    if secret_names is None:
        secret_names, secret_warning = _secret_names(github_repo)
        if secret_warning:
            _add_issue(warnings, "secret-list-unavailable", secret_warning)

    has_dockerhub_secrets = bool(
        secret_names is not None
        and {"DOCKERHUB_USERNAME", "DOCKERHUB_TOKEN"}.issubset(secret_names)
    )

    has_web_build = _has_web_build_script(repo_path)
    four_part_tag = bool(tag and FOUR_PART_VERSION.match(tag))

    for workflow in _workflow_files(repo_path):
        text = _read_text(workflow)
        rel = workflow.relative_to(repo_path)
        checks.append({"check": "workflow-scanned", "path": str(rel)})

        if _uses_web_root_bun_build(text) and not has_web_build:
            _add_issue(
                issues,
                "web-root-build-script-missing",
                "workflow runs `bun run build` from web/, but web/package.json has no scripts.build",
                rel,
            )

        if _dockerhub_refs(text) and not _dockerhub_guarded(text) and not has_dockerhub_secrets:
            _add_issue(
                issues,
                "unguarded-dockerhub-login",
                "workflow references DockerHub secrets without an optional guard and repo secrets are missing",
                rel,
            )
        elif _dockerhub_refs(text) and _dockerhub_guarded(text) and not has_dockerhub_secrets:
            _add_issue(
                warnings,
                "dockerhub-optional",
                "DockerHub secrets are missing; guarded workflow must publish GHCR or skip DockerHub",
                rel,
            )

        if four_part_tag and _uses_raw_npm_version(text):
            _add_issue(
                issues,
                "electron-npm-version-not-normalized",
                f"tag {tag} has four numeric components; workflow uses raw npm version without normalization",
                rel,
            )

        pr_target_errors, pr_target_warnings = _pull_request_target_risks(text)
        for message in pr_target_errors:
            _add_issue(issues, "pull-request-target-risk", message, rel)
        for message in pr_target_warnings:
            _add_issue(warnings, "pull-request-target-review", message, rel)

    deploy_data = _load_yaml(Path(deploy_config).expanduser()) if deploy_config else {}
    image = str(deploy_data.get("image") or "")
    if image:
        checks.append({"check": "deploy-image", "image": image})
        if "ghcr.io/" not in image and not has_dockerhub_secrets:
            _add_issue(
                issues,
                "deploy-image-needs-registry-auth",
                f"deploy image {image!r} is not GHCR and DockerHub secrets are missing",
                Path(deploy_config) if deploy_config else None,
            )

    status = "success" if not issues else "error"
    return {
        "status": status,
        "mode": mode,
        "repo": str(repo_path),
        "github_repo": github_repo,
        "tag": tag,
        "errors": issues,
        "warnings": warnings,
        "checks": checks,
    }


def _print_text(result: dict[str, Any]) -> None:
    print(f"release_preflight={result['status']} repo={result['repo']} mode={result['mode']}")
    if result.get("tag"):
        print(f"tag={result['tag']}")
    if result.get("github_repo"):
        print(f"github_repo={result['github_repo']}")
    for item in result.get("errors", []):
        location = f" [{item['path']}]" if item.get("path") else ""
        print(f"ERROR {item['code']}{location}: {item['message']}")
    for item in result.get("warnings", []):
        location = f" [{item['path']}]" if item.get("path") else ""
        print(f"WARN {item['code']}{location}: {item['message']}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Preflight GitHub Actions/release/deploy sends.")
    parser.add_argument("repo", help="Target repository path.")
    parser.add_argument("--tag", default=None)
    parser.add_argument("--mode", default="push")
    parser.add_argument("--github-repo", default=None)
    parser.add_argument("--deploy-config", default=None)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    result = run_preflight(
        args.repo,
        tag=args.tag,
        mode=args.mode,
        github_repo=args.github_repo,
        deploy_config=args.deploy_config,
    )
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        _print_text(result)
    return 0 if result["status"] == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
