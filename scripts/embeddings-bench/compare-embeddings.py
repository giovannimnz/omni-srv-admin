#!/usr/bin/env python3
"""Controlled direct-TEI comparison for GTE and the Qwen INT8 canary."""

from __future__ import annotations

import json
import math
import re
import statistics
import subprocess
import time
import urllib.request
from pathlib import Path

from benchmark import KubernetesMetrics, make_text


PROFILES = {
    "interactive": (64, 1, 8),
    "batch": (128, 4, 5),
    "sustained_128_words": (128, 1, 3),
}
SSH = [
    "ssh",
    "-o",
    "BatchMode=yes",
    "-o",
    "GSSAPIAuthentication=no",
    "-o",
    "PreferredAuthentications=publickey",
    "-o",
    "StrictHostKeyChecking=yes",
    "atius-srv-1",
]


def post_embed(url: str, inputs: list[str], dimensions: int = 0) -> list[list[float]]:
    payload: dict[str, object] = {"inputs": inputs}
    if dimensions:
        payload["dimensions"] = dimensions
    request = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=300) as response:
        vectors = json.load(response)
    if not isinstance(vectors, list) or not vectors:
        raise RuntimeError(f"unexpected response from {url}")
    return vectors


def cosine(left: list[float], right: list[float]) -> float:
    return sum(a * b for a, b in zip(left, right))


def validate(url: str, dimensions: int) -> dict[str, object]:
    text = "A política de retenção define o prazo de armazenamento dos dados."
    single = post_embed(url, [text], dimensions)[0]
    batch = post_embed(url, [text, "O serviço deve reiniciar automaticamente após uma falha."], dimensions)[0]
    vectors = post_embed(url, [
        "O certificado digital precisa ser renovado antes do vencimento.",
        "O banco vetorial armazena embeddings normalizados.",
    ], dimensions)
    norms = [math.sqrt(sum(value * value for value in vector)) for vector in [single, batch, *vectors]]
    return {
        "dimension": len(single),
        "batch_dimension": len(vectors[0]),
        "norm_min": min(norms),
        "norm_max": max(norms),
        "single_batch_cosine": cosine(single, batch),
    }


def parse_cpu_time(value: str) -> float:
    seconds = 0.0
    number = ""
    factors = {"h": 3600.0, "m": 60.0, "s": 1.0, "ms": 0.001, "us": 0.000001}
    index = 0
    while index < len(value):
        if value[index].isdigit() or value[index] == ".":
            number += value[index]
            index += 1
            continue
        unit = "ms" if value[index:index + 2] == "ms" else "us" if value[index:index + 2] == "us" else value[index]
        if not number or unit not in factors:
            raise ValueError(f"unsupported podman cpu time: {value}")
        seconds += float(number) * factors[unit]
        number = ""
        index += len(unit)
    return seconds


def podman_stats(container: str) -> tuple[float, float]:
    command = SSH + ["/usr/bin/podman", "stats", "--no-stream", "--format", "json", container]
    completed = subprocess.run(command, check=True, capture_output=True, text=True, timeout=30)
    item = json.loads(completed.stdout)[0]
    usage = item["mem_usage"].split("/")[0].strip()
    match = re.fullmatch(r"([0-9.]+)\s*([A-Za-z]+)", usage)
    if not match:
        raise ValueError(f"unsupported podman memory usage: {usage}")
    number, unit = match.groups()
    memory_mib = float(number) * {"B": 1 / 1024**2, "KB": 1 / 1024, "MB": 1, "GB": 1024}.get(unit, 1)
    return parse_cpu_time(item["cpu_time"]), memory_mib


class PodmanMetrics:
    def __init__(self, container: str) -> None:
        self.container = container
        self.samples: list[tuple[float, float, float]] = []

    def sample(self) -> tuple[float, float, float]:
        cpu, memory = podman_stats(self.container)
        sample = (time.monotonic(), cpu, memory)
        self.samples.append(sample)
        return sample


def run_profile(url: str, dimensions: int, profile: str, metrics: object) -> dict[str, object]:
    words, batch_size, rounds = PROFILES[profile]
    inputs = [make_text(words, index) for index in range(batch_size)]
    for warmup in range(2):
        post_embed(url, [f"warmup-{warmup}: {text}" for text in inputs], dimensions)
    before = metrics.sample() if isinstance(metrics, PodmanMetrics) else metrics.start()[0]
    started = time.perf_counter()
    latencies: list[float] = []
    for round_index in range(rounds):
        marked = [f"measured-{round_index}-{index}: {text}" for index, text in enumerate(inputs)]
        request_started = time.perf_counter()
        vectors = post_embed(url, marked, dimensions)
        latencies.append(time.perf_counter() - request_started)
        if len(vectors) != batch_size or any(len(vector) != dimensions for vector in vectors):
            raise RuntimeError(f"invalid vector shape in {profile}: {[len(vector) for vector in vectors]}")
        if isinstance(metrics, PodmanMetrics):
            metrics.sample()
    wall = time.perf_counter() - started
    if isinstance(metrics, PodmanMetrics):
        after = metrics.sample()
        cpu_seconds = after[1] - before[1]
        peak_memory = max(sample[2] for sample in metrics.samples)
        mean_cpu_millicores = cpu_seconds / wall * 1000
        memory = {"peak_current_mib": peak_memory}
    else:
        after, cgroup = metrics.finish()
        cpu_seconds = after.cpu_seconds - before.cpu_seconds
        mean_cpu_millicores = cpu_seconds / wall * 1000
        memory = {
            "peak_working_set_mib": max(sample.working_set_bytes for sample in metrics.samples) / 1024**2,
            "cgroup_peak_mib": cgroup.get("container_memory_max_usage_bytes", 0) / 1024**2,
        }
    total_words = words * batch_size * rounds
    return {
        "profile": profile,
        "dimensions": dimensions,
        "words_per_input": words,
        "batch_size": batch_size,
        "rounds": rounds,
        "total_words": total_words,
        "wall_seconds": wall,
        "cpu_seconds": cpu_seconds,
        "cpu_seconds_per_1000_words": cpu_seconds * 1000 / total_words,
        "mean_cpu_millicores": mean_cpu_millicores,
        "latency_seconds": {
            "mean": statistics.fmean(latencies),
            "p50": sorted(latencies)[len(latencies) // 2],
            "max": max(latencies),
        },
        "memory": memory,
    }


def semantic_check(url: str, dimensions: int) -> dict[str, object]:
    query = "Qual é o prazo para renovar o certificado digital?"
    documents = [
        "O certificado digital deve ser renovado antes da data de vencimento.",
        "O serviço de banco de dados reinicia automaticamente após uma falha.",
        "A receita contém farinha, ovos e leite.",
    ]
    vectors = post_embed(url, [query, *documents], dimensions)
    scores = [(index, cosine(vectors[0], vector)) for index, vector in enumerate(vectors[1:])]
    scores.sort(key=lambda item: item[1], reverse=True)
    return {"top_index": scores[0][0], "scores": scores}


def run_gte() -> dict[str, object]:
    url = "http://10.21.1.21:31115/embed"
    validation = validate(url, 768)
    semantic = semantic_check(url, 768)
    profiles = []
    for profile in PROFILES:
        metrics = KubernetesMetrics(
            kubectl_prefix=("ssh -o BatchMode=yes -o StrictHostKeyChecking=yes atius-srv-1 sudo -n k3s kubectl"),
            node="horistic-srv",
            namespace="ebeddings-local",
            selector="app.kubernetes.io/name=tei-gte",
            container="text-embeddings-inference",
            interval=1.0,
        )
        profiles.append(run_profile(url, 768, profile, metrics))
    return {"model": "GTE current", "url": url, "validation": validation, "semantic": semantic, "profiles": profiles}


def run_qwen() -> dict[str, object]:
    url = "http://10.11.1.11:18215/embed"
    result: dict[str, object] = {"model": "Qwen3-Embedding-0.6B INT8 janni-t", "url": url, "dimensions": {}}
    for dimensions in (1024, 768):
        validation = validate(url, dimensions)
        semantic = semantic_check(url, dimensions)
        profiles = []
        for profile in PROFILES:
            profiles.append(run_profile(url, dimensions, profile, PodmanMetrics("qwen3-embedding-janni-bench")))
        result["dimensions"][str(dimensions)] = {"validation": validation, "semantic": semantic, "profiles": profiles}
    return result


if __name__ == "__main__":
    print(json.dumps({"gte": run_gte(), "qwen": run_qwen()}, ensure_ascii=False, indent=2))
