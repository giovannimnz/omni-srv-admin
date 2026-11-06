"""
Canonical Entrypoint for ATIUS Omni Control-Plane FastAPI (127.0.0.1:34805)
and Keycloak SSO IAM Gateway (127.0.0.1:8015).
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = REPO_ROOT / "modules" / "omni-control-plane" / "backend"

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _load_control_plane_module():
    pkg_name = "omni_control_plane_backend"
    if pkg_name not in sys.modules:
        init_spec = importlib.util.spec_from_file_location(
            pkg_name,
            BACKEND_DIR / "__init__.py",
            submodule_search_locations=[str(BACKEND_DIR)],
        )
        pkg_mod = importlib.util.module_from_spec(init_spec)
        sys.modules[pkg_name] = pkg_mod
        assert init_spec and init_spec.loader
        init_spec.loader.exec_module(pkg_mod)

    app_mod_name = f"{pkg_name}.app"
    if app_mod_name in sys.modules:
        return sys.modules[app_mod_name]

    for sub in ("search", "iam_store", "app"):
        sub_name = f"{pkg_name}.{sub}"
        if sub_name not in sys.modules:
            spec = importlib.util.spec_from_file_location(sub_name, BACKEND_DIR / f"{sub}.py")
            mod = importlib.util.module_from_spec(spec)
            sys.modules[sub_name] = mod
            assert spec and spec.loader
            spec.loader.exec_module(mod)
    return sys.modules[app_mod_name]


_backend = _load_control_plane_module()
app = _backend.app
create_app = _backend.create_app
DEFAULT_CONTROL_PLANE_PORT = _backend.DEFAULT_CONTROL_PLANE_PORT
DEFAULT_SSO_GATEWAY_PORT = _backend.DEFAULT_SSO_GATEWAY_PORT
DEFAULT_BIND_HOST = _backend.DEFAULT_BIND_HOST

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=DEFAULT_BIND_HOST, port=DEFAULT_CONTROL_PLANE_PORT)
