"""Runtime patch for Graphify backends that require OpenAI chat streaming.

Atius Router GPT aliases require ``stream=true`` for chat/completions. Graphify
0.8.39 calls OpenAI-compatible custom providers without streaming in
``graphify.llm._call_llm``. This patch keeps the provider in
``~/.graphify/providers.json`` and adds a narrow dispatch branch for providers
with ``"stream": true``.
"""
from __future__ import annotations

from pathlib import Path
import os
import sys


def _ensure_graphify_path() -> None:
    for p in sys.path:
        if (Path(p) / "graphify").is_dir():
            return
    pipx_site = (
        Path.home()
        / ".local"
        / "pipx"
        / "venvs"
        / "graphifyy"
        / "lib"
        / f"python{sys.version_info.major}.{sys.version_info.minor}"
        / "site-packages"
    )
    if pipx_site.is_dir():
        sys.path.insert(0, str(pipx_site))


_ensure_graphify_path()
from graphify import llm as _llm  # noqa: E402


def _streaming_openai_llm(
    prompt: str,
    *,
    backend: str,
    model: str | None = None,
    max_tokens: int = 200,
    usage_out: dict | None = None,
) -> str:
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise ImportError(_llm._backend_pkg_hint("openai", "openai")) from exc

    cfg = _llm.BACKENDS[backend]
    key = _llm._get_backend_api_key(backend)
    if not key:
        raise ValueError(f"No API key for backend '{backend}'. Set {_llm._format_backend_env_keys(backend)}.")
    mdl = model or _llm._default_model_for_backend(backend)
    headers = cfg.get("headers") if isinstance(cfg.get("headers"), dict) else None
    client = OpenAI(
        api_key=key,
        base_url=cfg["base_url"],
        timeout=_llm._resolve_api_timeout(),
        **({"default_headers": headers} if headers else {}),
    )
    kwargs: dict = {
        "model": mdl,
        "messages": [{"role": "user", "content": prompt}],
        "max_completion_tokens": max_tokens,
        "stream": True,
        "stream_options": {"include_usage": True},
    }
    temperature = _llm._resolve_temperature(cfg.get("temperature", 0), mdl)
    if temperature is not None:
        kwargs["temperature"] = temperature
    if cfg.get("reasoning_effort"):
        kwargs["reasoning_effort"] = cfg["reasoning_effort"]
    if cfg.get("extra_body") is not None:
        kwargs["extra_body"] = cfg["extra_body"]

    parts: list[str] = []
    input_tokens = output_tokens = 0
    stream = client.chat.completions.create(**kwargs)
    for event in stream:
        usage = getattr(event, "usage", None)
        if usage is not None:
            input_tokens = getattr(usage, "prompt_tokens", 0) or input_tokens
            output_tokens = getattr(usage, "completion_tokens", 0) or output_tokens
        if not getattr(event, "choices", None):
            continue
        delta = event.choices[0].delta
        text = getattr(delta, "content", None)
        if text:
            parts.append(text)
    if usage_out is not None:
        usage_out["input"] = usage_out.get("input", 0) + input_tokens
        usage_out["output"] = usage_out.get("output", 0) + output_tokens
    return "".join(parts)


def _streaming_openai_compat(
    base_url: str,
    api_key: str,
    model: str,
    user_message: str,
    temperature: float | None = 0,
    reasoning_effort: str | None = None,
    max_completion_tokens: int = 8192,
    *,
    backend: str = "",
    deep_mode: bool = False,
    images=None,
    extra_body: dict | None = None,
) -> dict:
    from openai import OpenAI

    client = OpenAI(
        api_key=api_key,
        base_url=base_url,
        timeout=_llm._resolve_api_timeout(),
        max_retries=_llm._resolve_max_retries(),
    )
    kwargs: dict = {
        "model": model,
        "messages": [
            {"role": "system", "content": _llm._extraction_system(deep=deep_mode)},
            {"role": "user", "content": _llm._openai_content(user_message, images or [])},
        ],
        "max_completion_tokens": max_completion_tokens,
        "stream": True,
        "stream_options": {"include_usage": True},
    }
    if temperature is not None:
        kwargs["temperature"] = temperature
    if reasoning_effort is not None:
        kwargs["reasoning_effort"] = reasoning_effort
    if extra_body is not None:
        kwargs["extra_body"] = extra_body

    parts: list[str] = []
    input_tokens = output_tokens = 0
    finish_reason = None
    for event in client.chat.completions.create(**kwargs):
        usage = getattr(event, "usage", None)
        if usage is not None:
            input_tokens = getattr(usage, "prompt_tokens", 0) or input_tokens
            output_tokens = getattr(usage, "completion_tokens", 0) or output_tokens
        if not getattr(event, "choices", None):
            continue
        choice = event.choices[0]
        finish_reason = getattr(choice, "finish_reason", None) or finish_reason
        text = getattr(getattr(choice, "delta", None), "content", None)
        if text:
            parts.append(text)
    raw_content = "".join(parts)
    result = _llm._parse_llm_json(raw_content or "{}")
    result.update(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        model=model,
        finish_reason=finish_reason,
    )
    if _llm._response_is_hollow(raw_content, result) and result["finish_reason"] != "length":
        result["finish_reason"] = "length"
    return result


def apply() -> bool:
    if getattr(_llm._call_llm, "_graphify_atius_router_stream_patched", False):
        return False
    original = _llm._call_llm
    original_compat = _llm._call_openai_compat

    def patched_call_llm(
        prompt: str,
        *,
        backend: str,
        model: str | None = None,
        max_tokens: int = 200,
        usage_out: dict | None = None,
    ) -> str:
        cfg = _llm.BACKENDS.get(backend, {})
        if cfg.get("stream") is True:
            return _streaming_openai_llm(
                prompt,
                backend=backend,
                model=model,
                max_tokens=max_tokens,
                usage_out=usage_out,
            )
        return original(
            prompt,
            backend=backend,
            model=model,
            max_tokens=max_tokens,
            usage_out=usage_out,
        )

    def patched_openai_compat(*args, **kwargs):
        backend = kwargs.get("backend", "")
        cfg = _llm.BACKENDS.get(backend, {})
        if cfg.get("stream") is True:
            return _streaming_openai_compat(*args, **kwargs)
        return original_compat(*args, **kwargs)

    patched_call_llm._graphify_atius_router_stream_patched = True  # type: ignore[attr-defined]
    patched_call_llm._graphify_atius_router_stream_original = original  # type: ignore[attr-defined]
    patched_openai_compat._graphify_atius_router_stream_patched = True  # type: ignore[attr-defined]
    patched_openai_compat._graphify_atius_router_stream_original = original_compat  # type: ignore[attr-defined]
    _llm._call_llm = patched_call_llm
    _llm._call_openai_compat = patched_openai_compat
    return True


_installed = apply()


if __name__ == "__main__":
    print(f"[graphify-atius-router-patch] installed={_installed}", file=sys.stderr)
