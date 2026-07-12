#!/usr/bin/env python3
import re
import sys
from pathlib import Path


REQUIRED = (
    "profile_cpu_max: 80000 100000",
    "focused_go_suite: pass",
    "internal_invalid: pass",
    "upstream_401_token_invalidated: pass",
    "upstream_401_refresh_token_invalidated: pass",
    "upstream_401_invalid_api_key: pass",
    "upstream_403: pass",
    "refresh_success: pass",
    "regenerate_success: pass",
    "probe_success: pass",
    "secret_material_present: false",
    "V2: pass",
    "V3: pass",
    "V4: pass",
    "V5: pass",
    "V6: pass",
)

SECRET_PATTERNS = (
    re.compile(r"Authorization:\s*Bearer\s+\S+", re.I),
    re.compile(r'"refresh_token"\s*:\s*"[^"\s]+"', re.I),
    re.compile(r"\beyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{10,}\b"),
)


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: verify-router-evidence.py <evidence.md>", file=sys.stderr)
        return 2
    text = Path(sys.argv[1]).read_text(encoding="utf-8")
    missing = [marker for marker in REQUIRED if marker not in text]
    leaked = [pattern.pattern for pattern in SECRET_PATTERNS if pattern.search(text)]
    if missing or leaked:
        if missing:
            print("missing markers: " + ", ".join(missing), file=sys.stderr)
        if leaked:
            print("secret-like material detected", file=sys.stderr)
        return 1
    print("router evidence: pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
