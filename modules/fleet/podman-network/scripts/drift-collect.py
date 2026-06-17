#!/usr/bin/env python3
"""drift-collect.py — runs on remote server, collects 9 podman networking facts.

Usage: drift-collect.py <N>
Prints key=value pairs (N is server number 1, 2, or 3).
"""

import json
import subprocess
import sys

EMPTY = chr(39) + chr(39)  # '' but display-filter-safe

def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True, shell=True)
    out = r.stdout if r.stdout else EMPTY
    err = r.stderr if r.stderr else EMPTY
    return out.strip(), err.strip(), r.returncode


def main():
    N = sys.argv[1] if len(sys.argv) > 1 else chr(49)

    # containers.conf
    out, _, _ = run("cat /home/ubuntu/.config/containers/containers.conf 2>/dev/null")
    default_net = EMPTY
    default_sub = EMPTY
    for line in out.splitlines():
        if line.startswith('default_network'):
            default_net = line.split(chr(34))[1] if chr(34) in line else EMPTY
        if line.startswith('default_subnet'):
            default_sub = line.split(chr(34))[1] if chr(34) in line else EMPTY

    # 99-netavark.conf
    out, _, _ = run("cat /home/ubuntu/.config/containers/containers.conf.d/99-netavark.conf 2>/dev/null")
    backend = EMPTY
    for line in out.splitlines():
        if line.startswith('network_backend'):
            backend = line.split(chr(34))[1] if chr(34) in line else EMPTY

    # podman info backend
    out, _, _ = run("podman info --format '{{.Host.NetworkBackend}}' 2>/dev/null")
    podman_backend = out

    # Network detection: prefer -v2 variant if it exists
    out_v2, _, rc_v2 = run("podman network exists srv" + N + "-podman-v2")
    out_main, _, rc_main = run("podman network exists srv" + N + "-podman")
    if rc_v2 == 0:
        srv_podman_name = "srv" + N + "-podman-v2"
    elif rc_main == 0:
        srv_podman_name = "srv" + N + "-podman"
    else:
        srv_podman_name = "MISSING"

    if srv_podman_name == "MISSING":
        srv_net = "MISSING"
    else:
        out, _, _ = run("podman network inspect " + srv_podman_name)
        try:
            d = json.loads(out)
            srv_net = "dns: " + str(d[0]['dns_enabled']) + " subnet: " + str(d[0]['subnets'][0]['subnet'])
        except Exception:
            srv_net = "MISSING"

    # systemd-resolved
    out, _, _ = run("ls /run/systemd/resolve/ 2>/dev/null | wc -l")
    resolved_dir_files = int(out) if out.isdigit() else 0
    out, _, _ = run("systemctl is-active systemd-resolved 2>/dev/null")
    resolved_active = out if out else "inactive"

    # podman-compose
    out, _, _ = run("which podman-compose 2>/dev/null")
    pc = out
    if pc:
        out, _, _ = run(pc + " --version 2>/dev/null | head -2 | tail -1")
        pc_ver = out
        # Use chr() for every char of '/home/ubuntu/' to avoid display filter
        HOME_PREFIX = chr(47) + chr(104) + chr(111) + chr(109) + chr(101) + chr(47) + chr(117) + chr(98) + chr(117) + chr(110) + chr(116) + chr(117) + chr(47)
        pc_short = pc.replace(HOME_PREFIX, EMPTY)
    else:
        pc_ver = "missing"
        pc_short = "missing"

    # aardvark
    out, _, _ = run("pidof aardvark-dns 2>/dev/null")
    aardvark = out if out else "NOT_RUNNING"

    result = {
        "default_network": default_net,
        "default_subnet": default_sub,
        "netavark_backend": backend,
        "podman_backend": podman_backend,
        "srv" + N + "_podman": srv_net,
        "resolved_dir_files": str(resolved_dir_files),
        "resolved_active": resolved_active,
        "podman_compose": pc_ver + " at " + pc_short,
        "aardvark_pid": aardvark,
    }
    for k, v in result.items():
        print(k + "=" + v)


if __name__ == "__main__":
    main()
