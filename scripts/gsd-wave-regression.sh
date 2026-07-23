#!/usr/bin/env bash
set -euo pipefail

# This command is invoked by GSD's post-merge gate after every wave.
# Keep it phase-neutral: each plan still owns its task-level verification,
# while this runner catches regressions across the merged wave.

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

ran_phase_tests=0

if [[ -d scripts/embeddings-bench/tests ]]; then
  ran_phase_tests=1
  python3 -m unittest discover \
    -s scripts/embeddings-bench/tests \
    -p 'test_*.py' \
    -v
fi

# The reranker package becomes testable only after its lockfile is created by
# its plan. Do not make earlier waves depend on a not-yet-created Node install.
if [[ -f services/qwen-reranker-onnx/package-lock.json ]]; then
  ran_phase_tests=1
  npm --prefix services/qwen-reranker-onnx test
fi

if [[ "$ran_phase_tests" -eq 0 ]]; then
  printf '%s\n' 'No phase-local regression suite exists yet; task-level gates remain mandatory.'
fi
