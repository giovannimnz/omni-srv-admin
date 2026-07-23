#!/usr/bin/env python3
"""Measure embedding latency and container CPU/memory without saving vectors."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import shlex
import statistics
import struct
import subprocess
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


BASE_TEXT = (
    "A busca semântica local precisa preservar significado em português, inglês e código. "
    "O serviço roda em Kubernetes com orçamento estrito de processador, memória observável "
    "e contratos estáveis de modelo, dimensão, normalização, pooling e chunking. "
    "Cada medição deve separar latência, throughput e CPU total para evitar otimizações enganosas. "
)

PROFILE_DEFAULTS = {
    "interactive": {"words": 64, "batch": 1, "rounds": 8},
    "batch": {"words": 128, "batch": 4, "rounds": 5},
    "long": {"words": 2048, "batch": 1, "rounds": 3},
}

METRIC_LINE = re.compile(
    r"^(?P<name>[a-zA-Z_:][a-zA-Z0-9_:]*)\{(?P<labels>[^}]*)\}\s+"
    r"(?P<value>[-+0-9.eE]+)(?:\s+(?P<timestamp>\d+))?$"
)
LABEL = re.compile(r'(\w+)="((?:\\.|[^"\\])*)"')


def percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def make_text(word_count: int, variant: int) -> str:
    source = (BASE_TEXT + f" Amostra determinística número {variant}. ").split()
    words: list[str] = []
    while len(words) < word_count:
        words.extend(source)
    return " ".join(words[:word_count])


def marked_inputs(inputs: list[str], phase: str, round_index: int) -> list[str]:
    return [
        f"ATIUS-{phase}-{round_index}-{item_index}: {value}"
        for item_index, value in enumerate(inputs)
    ]


def parse_prometheus(
    text: str,
) -> list[tuple[str, dict[str, str], float, float | None]]:
    parsed: list[tuple[str, dict[str, str], float, float | None]] = []
    for line in text.splitlines():
        match = METRIC_LINE.match(line)
        if not match:
            continue
        labels = {
            item.group(1): bytes(item.group(2), "utf-8").decode("unicode_escape")
            for item in LABEL.finditer(match.group("labels"))
        }
        timestamp = match.group("timestamp")
        parsed.append(
            (
                match.group("name"),
                labels,
                float(match.group("value")),
                float(timestamp) / 1000.0 if timestamp else None,
            )
        )
    return parsed


@dataclass
class ResourceSample:
    monotonic: float
    cpu_seconds: float
    working_set_bytes: float


class KubernetesMetrics:
    def __init__(
        self,
        kubectl_prefix: str,
        node: str,
        namespace: str,
        selector: str,
        container: str,
        interval: float,
    ) -> None:
        self.command = shlex.split(kubectl_prefix)
        self.node = node
        self.namespace = namespace
        self.selector = selector
        self.container = container
        self.interval = interval
        self.pod = self._resolve_pod()
        self.samples: list[ResourceSample] = []
        self.errors: list[str] = []
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def _run(self, arguments: list[str]) -> str:
        completed = subprocess.run(
            self.command + arguments,
            check=True,
            capture_output=True,
            text=True,
            timeout=90,
        )
        return completed.stdout

    def _resolve_pod(self) -> str:
        raw = self._run(
            [
                "-n",
                self.namespace,
                "get",
                "pods",
                "-l",
                self.selector,
                "-o",
                "json",
            ]
        )
        pods = json.loads(raw).get("items", [])
        running = [item for item in pods if item.get("status", {}).get("phase") == "Running"]
        if len(running) != 1:
            names = [item.get("metadata", {}).get("name") for item in pods]
            raise RuntimeError(f"expected one Running pod for {self.selector}, found {names}")
        return str(running[0]["metadata"]["name"])

    def _matching_metrics(
        self, endpoint: str
    ) -> dict[str, tuple[float, float | None]]:
        raw = self._run(
            ["get", "--raw", f"/api/v1/nodes/{self.node}/proxy/metrics/{endpoint}"]
        )
        result: dict[str, tuple[float, float | None]] = {}
        for name, labels, value, timestamp in parse_prometheus(raw):
            if labels.get("namespace") != self.namespace:
                continue
            if labels.get("pod") != self.pod:
                continue
            if labels.get("container") != self.container:
                continue
            if name == "container_cpu_usage_seconds_total" and labels.get("cpu", "total") != "total":
                continue
            result[name] = (value, timestamp)
        return result

    def resource_sample(self) -> ResourceSample:
        metrics = self._matching_metrics("resource")
        cpu_value, _ = metrics["container_cpu_usage_seconds_total"]
        return ResourceSample(
            monotonic=time.monotonic(),
            cpu_seconds=cpu_value,
            working_set_bytes=metrics["container_memory_working_set_bytes"][0],
        )

    def cgroup_snapshot(self) -> tuple[ResourceSample, dict[str, float]]:
        exec_prefix = [
            "-n",
            self.namespace,
            "exec",
            self.pod,
            "-c",
            self.container,
            "--",
            "cat",
        ]
        cpu_raw = self._run(exec_prefix + ["/sys/fs/cgroup/cpu.stat"])
        cpu_observed_at = time.monotonic()
        memory_current = float(
            self._run(exec_prefix + ["/sys/fs/cgroup/memory.current"]).strip()
        )
        memory_peak = float(
            self._run(exec_prefix + ["/sys/fs/cgroup/memory.peak"]).strip()
        )
        cpu = {}
        for line in cpu_raw.splitlines():
            key, value = line.split(maxsplit=1)
            cpu[key] = float(value)
        sample = ResourceSample(
            monotonic=cpu_observed_at,
            cpu_seconds=cpu["usage_usec"] / 1_000_000.0,
            working_set_bytes=memory_current,
        )
        counters = {
            "container_cpu_cfs_periods_total": cpu.get("nr_periods", 0.0),
            "container_cpu_cfs_throttled_periods_total": cpu.get(
                "nr_throttled", 0.0
            ),
            "container_cpu_cfs_throttled_seconds_total": cpu.get(
                "throttled_usec", 0.0
            )
            / 1_000_000.0,
            "container_memory_max_usage_bytes": memory_peak,
        }
        return sample, counters

    def start(self) -> tuple[ResourceSample, dict[str, float]]:
        first, cgroup = self.cgroup_snapshot()
        self.samples.append(first)
        self._thread = threading.Thread(target=self._sample_loop, daemon=True)
        self._thread.start()
        return first, cgroup

    def _sample_loop(self) -> None:
        while not self._stop.wait(self.interval):
            try:
                self.samples.append(self.resource_sample())
            except Exception as exc:  # Metrics failure must not abort inference calls.
                self.errors.append(str(exc))

    def finish(self) -> tuple[ResourceSample, dict[str, float]]:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=max(5.0, self.interval * 2.0))
        final, cgroup = self.cgroup_snapshot()
        self.samples.append(final)
        return final, cgroup


def post_json(url: str, payload: dict[str, Any], timeout: float) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        body = exc.read(2000).decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} from {url}: {body}") from exc


def extract_vectors(api: str, response: dict[str, Any]) -> list[list[float]]:
    if api == "ollama":
        vectors = response.get("embeddings")
    else:
        vectors = [item.get("embedding") for item in response.get("data", [])]
    if not isinstance(vectors, list) or not vectors:
        raise RuntimeError(f"embedding response has no vectors: keys={sorted(response)}")
    return vectors


def request_embeddings(
    base_url: str,
    api: str,
    model: str,
    inputs: list[str],
    timeout: float,
    request_dimensions: int,
    ollama_num_thread: int,
    ollama_num_ctx: int,
) -> tuple[dict[str, Any], float]:
    if api == "ollama":
        url = base_url.rstrip("/") + "/api/embed"
        payload = {"model": model, "input": inputs, "truncate": False, "keep_alive": -1}
        options = {}
        if ollama_num_thread > 0:
            options["num_thread"] = ollama_num_thread
        if ollama_num_ctx > 0:
            options["num_ctx"] = ollama_num_ctx
        if options:
            payload["options"] = options
    else:
        url = base_url.rstrip("/") + "/v1/embeddings"
        payload = {"model": model, "input": inputs, "encoding_format": "float"}
        if request_dimensions > 0:
            payload["dimensions"] = request_dimensions
    started = time.perf_counter()
    response = post_json(url, payload, timeout)
    return response, time.perf_counter() - started


def vector_summary(vectors: list[list[float]], expected_dimensions: int) -> dict[str, Any]:
    norms: list[float] = []
    hashes: list[str] = []
    for vector in vectors:
        if len(vector) != expected_dimensions:
            raise RuntimeError(
                f"expected {expected_dimensions} dimensions, received {len(vector)}"
            )
        if not all(math.isfinite(value) for value in vector):
            raise RuntimeError("embedding contains NaN or infinity")
        norms.append(math.sqrt(sum(value * value for value in vector)))
        digest = hashlib.sha256()
        for value in vector:
            digest.update(struct.pack("!f", float(value)))
        hashes.append(digest.hexdigest())
    return {
        "norm_min": min(norms),
        "norm_max": max(norms),
        "first_vector_sha256": hashes[0],
    }


def usage_tokens(api: str, response: dict[str, Any]) -> int:
    if api == "ollama":
        return int(response.get("prompt_eval_count") or 0)
    usage = response.get("usage") or {}
    return int(usage.get("prompt_tokens") or usage.get("total_tokens") or 0)


def delta(after: dict[str, float], before: dict[str, float], name: str) -> float:
    return max(0.0, after.get(name, 0.0) - before.get(name, 0.0))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--api", choices=("openai", "ollama"), default="openai")
    parser.add_argument("--model", required=True)
    parser.add_argument("--expected-dimensions", type=int, required=True)
    parser.add_argument(
        "--request-dimensions",
        type=int,
        default=0,
        help="OpenAI dimensions field; 0 omits it from the request",
    )
    parser.add_argument("--profile", choices=tuple(PROFILE_DEFAULTS), required=True)
    parser.add_argument("--rounds", type=int)
    parser.add_argument("--words", type=int)
    parser.add_argument("--warmup-rounds", type=int, default=2)
    parser.add_argument("--timeout", type=float, default=300.0)
    parser.add_argument("--node", default="horistic-srv")
    parser.add_argument("--namespace", required=True)
    parser.add_argument("--selector", required=True)
    parser.add_argument("--container", required=True)
    parser.add_argument(
        "--kubectl-prefix",
        default=(
            "ssh -o BatchMode=yes -o StrictHostKeyChecking=yes atius-srv-1 "
            "sudo -n k3s kubectl"
        ),
    )
    parser.add_argument("--sample-interval", type=float, default=1.0)
    parser.add_argument("--cpu-limit-millicores", type=float, default=500.0)
    parser.add_argument("--ollama-num-thread", type=int, default=1)
    parser.add_argument("--ollama-num-ctx", type=int, default=1024)
    args = parser.parse_args()

    profile = dict(PROFILE_DEFAULTS[args.profile])
    if args.rounds is not None:
        profile["rounds"] = args.rounds
    if args.words is not None:
        profile["words"] = args.words
    inputs = [make_text(profile["words"], index) for index in range(profile["batch"])]

    last_summary: dict[str, Any] = {}
    for round_index in range(args.warmup_rounds):
        response, _ = request_embeddings(
            args.base_url,
            args.api,
            args.model,
            marked_inputs(inputs, "warmup", round_index),
            args.timeout,
            args.request_dimensions,
            args.ollama_num_thread,
            args.ollama_num_ctx,
        )
        vectors = extract_vectors(args.api, response)
        last_summary = vector_summary(vectors, args.expected_dimensions)

    metrics = KubernetesMetrics(
        kubectl_prefix=args.kubectl_prefix,
        node=args.node,
        namespace=args.namespace,
        selector=args.selector,
        container=args.container,
        interval=args.sample_interval,
    )
    first_resource, first_cgroup = metrics.start()
    wall_started = time.perf_counter()
    latencies: list[float] = []
    total_tokens = 0
    total_vectors = 0
    try:
        for round_index in range(profile["rounds"]):
            response, latency = request_embeddings(
                args.base_url,
                args.api,
                args.model,
                marked_inputs(inputs, "measured", round_index),
                args.timeout,
                args.request_dimensions,
                args.ollama_num_thread,
                args.ollama_num_ctx,
            )
            vectors = extract_vectors(args.api, response)
            last_summary = vector_summary(vectors, args.expected_dimensions)
            total_vectors += len(vectors)
            total_tokens += usage_tokens(args.api, response)
            latencies.append(latency)
    finally:
        wall_seconds = time.perf_counter() - wall_started
        final_resource, final_cgroup = metrics.finish()

    cpu_seconds = max(0.0, final_resource.cpu_seconds - first_resource.cpu_seconds)
    cpu_measurement_wall_seconds = max(
        0.0, final_resource.monotonic - first_resource.monotonic
    )
    mean_cpu_cores = (
        cpu_seconds / cpu_measurement_wall_seconds
        if cpu_measurement_wall_seconds
        else 0.0
    )
    peak_cpu_cores = 0.0
    for previous, current in zip(metrics.samples, metrics.samples[1:]):
        elapsed = current.monotonic - previous.monotonic
        if elapsed > 0:
            peak_cpu_cores = max(
                peak_cpu_cores,
                max(0.0, current.cpu_seconds - previous.cpu_seconds) / elapsed,
            )
    # Kubelet resource counters refresh more slowly than short requests. The
    # workload mean is a strict lower bound for its peak and avoids reporting a
    # stale sampled rate below that mean.
    peak_cpu_cores = max(peak_cpu_cores, mean_cpu_cores)
    peak_cpu_cores = min(peak_cpu_cores, args.cpu_limit_millicores / 1000.0)

    periods = delta(final_cgroup, first_cgroup, "container_cpu_cfs_periods_total")
    throttled_periods = delta(
        final_cgroup, first_cgroup, "container_cpu_cfs_throttled_periods_total"
    )
    peak_working_set = max(sample.working_set_bytes for sample in metrics.samples)
    result = {
        "model": args.model,
        "api": args.api,
        "profile": args.profile,
        "dimensions": args.expected_dimensions,
        "request_dimensions": args.request_dimensions or None,
        "rounds": profile["rounds"],
        "batch_size": profile["batch"],
        "target_words_per_input": profile["words"],
        "requests": len(latencies),
        "vectors": total_vectors,
        "prompt_tokens": total_tokens,
        "wall_seconds": wall_seconds,
        "cpu_seconds": cpu_seconds,
        "cpu_measurement_wall_seconds": cpu_measurement_wall_seconds,
        "cpu_seconds_per_1k_tokens": (
            cpu_seconds * 1000.0 / total_tokens if total_tokens else None
        ),
        "tokens_per_cpu_second": total_tokens / cpu_seconds if cpu_seconds else None,
        "tokens_per_wall_second": total_tokens / wall_seconds if wall_seconds else None,
        "mean_cpu_millicores": mean_cpu_cores * 1000.0,
        "peak_cpu_millicores": peak_cpu_cores * 1000.0,
        "latency_seconds": {
            "mean": statistics.fmean(latencies),
            "p50": percentile(latencies, 0.50),
            "p95": percentile(latencies, 0.95),
            "max": max(latencies),
        },
        "memory": {
            "peak_working_set_mib": peak_working_set / 1024.0 / 1024.0,
            "container_lifetime_max_mib": final_cgroup.get(
                "container_memory_max_usage_bytes", 0.0
            )
            / 1024.0
            / 1024.0,
        },
        "throttling": {
            "seconds": delta(
                final_cgroup,
                first_cgroup,
                "container_cpu_cfs_throttled_seconds_total",
            ),
            "period_ratio": throttled_periods / periods if periods else 0.0,
        },
        "vector_validation": last_summary,
        "metrics_samples": len(metrics.samples),
        "metrics_errors": metrics.errors,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
