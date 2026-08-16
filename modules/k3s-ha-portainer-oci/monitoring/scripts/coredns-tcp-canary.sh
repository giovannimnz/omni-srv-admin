#!/usr/bin/env bash
# Generate a real DNS-over-TCP request so the CoreDNS TCP telemetry path stays
# continuously observable in Prometheus and Grafana.
set -euo pipefail

DNS_SERVER="${COREDNS_TCP_CANARY_SERVER:-10.43.0.10}"
DNS_NAME="${COREDNS_TCP_CANARY_NAME:-kubernetes.default.svc.cluster.local}"

if ! command -v dig >/dev/null 2>&1; then
  echo "coredns_tcp_canary=FAIL reason=dig_not_found" >&2
  exit 1
fi

answer="$({ dig +tcp +short +time=2 +tries=1 "@${DNS_SERVER}" "${DNS_NAME}" A; } 2>/dev/null)"
if [[ -z "${answer}" ]]; then
  echo "coredns_tcp_canary=FAIL reason=empty_answer server=${DNS_SERVER} name=${DNS_NAME}" >&2
  exit 1
fi

echo "coredns_tcp_canary=PASS server=${DNS_SERVER} name=${DNS_NAME}"