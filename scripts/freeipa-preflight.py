#!/usr/bin/env python3
"""Render the Phase 33 FreeIPA preflight checklist.

This script is read-only. It does not install packages, open ports, change DNS
or start containers.
"""
from __future__ import annotations

import json

PORTS = {
    "dns": ["53/tcp", "53/udp"],
    "kerberos": ["88/tcp", "88/udp", "464/tcp", "464/udp"],
    "ldap": ["389/tcp", "636/tcp"],
    "web": ["80/tcp", "443/tcp"],
    "ntp": ["123/udp"],
}

CHECKS = [
    "static fully-qualified hostname",
    "forward DNS resolves to the FreeIPA endpoint",
    "reverse DNS resolves back to the FreeIPA hostname",
    "NTP synchronized",
    "dedicated data volume or VM disk backup path",
    "no conflict with Apache, Landscape, CoreDNS, LXD dnsmasq or K3s",
    "admin password stored outside repo/docs/logs",
    "rollback for DNS and client enrollment",
]


def main() -> None:
    print(
        json.dumps(
            {
                "mode": "read-only",
                "recommended_target": "atius-srv-3 isolated LXD container or VM, gated",
                "ports": PORTS,
                "checks": CHECKS,
                "blocked_until": [
                    "FQDN and realm confirmed",
                    "reachable dedicated IP model selected",
                    "DNS authority/forwarding model selected",
                    "backup and rollback path approved",
                ],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()

