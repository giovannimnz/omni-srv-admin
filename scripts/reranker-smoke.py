#!/usr/bin/env python3
"""Redacted smoke test for native TEI or the public ATIUS rerank contract."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request


DOCUMENTS = [
    "Marte e um planeta rochoso do Sistema Solar.",
    "Jupiter e o maior planeta do Sistema Solar.",
    "A receita usa farinha, ovos e leite.",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--base-url",
        default="https://router.atius.com.br/v1",
        help="Router /v1 base URL, or native TEI base URL with --native.",
    )
    parser.add_argument("--native", action="store_true", help="Use TEI /rerank directly.")
    parser.add_argument("--query", default="Qual texto fala sobre o planeta Marte?")
    parser.add_argument("--top-n", type=int, default=3)
    parser.add_argument("--timeout", type=float, default=90.0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    base_url = args.base_url.rstrip("/")
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "ATIUS-Reranker-Smoke/1.0",
    }
    if args.native:
        url = f"{base_url}/rerank"
        payload = {
            "query": args.query,
            "texts": DOCUMENTS,
            "raw_scores": False,
            "return_text": False,
            "truncate": True,
            "truncation_direction": "Right",
        }
    else:
        token = os.environ.get("ATIUS_ROUTER_TOKEN") or os.environ.get("NEW_API_KEY")
        if not token:
            print("Set ATIUS_ROUTER_TOKEN or NEW_API_KEY; the value is never printed.", file=sys.stderr)
            return 2
        url = f"{base_url}/rerank"
        headers["Authorization"] = f"Bearer {token}"
        headers["X-Rerank-Workload"] = "interactive"
        payload = {
            "model": "reranker-gte-multilingual-v1",
            "query": args.query,
            "documents": DOCUMENTS,
            "top_n": max(1, min(args.top_n, len(DOCUMENTS))),
            "return_documents": True,
        }

    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    started = time.monotonic()
    try:
        with urllib.request.urlopen(request, timeout=args.timeout) as response:
            status = response.status
            body = json.load(response)
    except urllib.error.HTTPError as exc:
        print(json.dumps({"status": exc.code, "error": "HTTP error"}))
        return 1
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": None, "error": type(exc).__name__}))
        return 1

    elapsed_ms = round((time.monotonic() - started) * 1000)
    native_results = body if args.native else body.get("results", [])
    results = [
        {
            "index": item.get("index"),
            "score": round(float(item.get("score", item.get("relevance_score", 0.0))), 6),
        }
        for item in native_results
    ]
    results.sort(key=lambda item: item["score"], reverse=True)
    print(
        json.dumps(
            {
                "status": status,
                "mode": "native-tei" if args.native else "public-router",
                "model": "reranker-gte-multilingual-v1",
                "documents": len(DOCUMENTS),
                "elapsed_ms": elapsed_ms,
                "results": results,
                "error": None,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if status == 200 and results and results[0]["index"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
