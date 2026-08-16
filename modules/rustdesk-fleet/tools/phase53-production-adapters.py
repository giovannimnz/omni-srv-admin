#!/usr/bin/env python3
"""Compatibility entry point for the reviewed Phase 53 provider seam.

The importable implementation uses the PEP-8 module name
``phase53_production_adapters``; this hyphenated path is retained because the
GSD plan and operator runbooks refer to the tool by its script-style name.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

_path = Path(__file__).with_name("phase53_production_adapters.py")
_spec = importlib.util.spec_from_file_location("phase53_production_adapters", _path)
if _spec is None or _spec.loader is None:
    raise RuntimeError("provider-seam-unavailable")
_module = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _module
_spec.loader.exec_module(_module)

for _name in _module.__all__:
    globals()[_name] = getattr(_module, _name)

__all__ = list(_module.__all__)
