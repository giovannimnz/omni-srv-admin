try:
    import graphify_atius_router_patch  # noqa: F401
except Exception as exc:
    import sys
    print(f"[graphify-atius-router-patch] startup failed: {exc!r}", file=sys.stderr)
    raise
