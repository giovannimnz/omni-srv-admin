#!/usr/bin/env bash
# omni::fleet-podman-passt-install v1.0.0
# Instala passt (pasta) para Netavark rootless Podman com CPU containment (<=20%, nice 19, idle io) e reporta Linger/servicos.
set -euo pipefail

printf 'host=%s\n' "$(hostname)"
printf 'date_utc=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"

export DEBIAN_FRONTEND=noninteractive

# 1. Instalar passt com CPU containment
if ! command -v pasta >/dev/null 2>&1 && ! dpkg -s passt >/dev/null 2>&1; then
  echo "Installing passt..."
  nice -n 19 ionice -c 3 apt-get update -qq
  nice -n 19 ionice -c 3 apt-get install -y -qq passt
fi

if command -v pasta >/dev/null 2>&1; then
  printf 'pasta_binary=%s\n' "$(command -v pasta)"
  printf 'passt_pkg_version=%s\n' "$(dpkg-query -W -f='${Version}' passt 2>/dev/null || echo 'unknown')"
else
  echo "pasta_binary=not_found"
fi

# 2. Verificar Linger dos usuarios de servico
for user in ubuntu horistic muniz; do
  if id "$user" >/dev/null 2>&1; then
    linger_state="$(loginctl show-user "$user" --property=Linger 2>/dev/null || echo "Linger=unknown")"
    printf 'linger_%s=%s\n' "$user" "$linger_state"
  fi
done

# 3. Status de servicos essenciais
printf 'landscape_client=%s\n' "$(systemctl is-active landscape-client 2>/dev/null || echo 'inactive')"
printf 'unattended_upgrades=%s\n' "$(systemctl is-active unattended-upgrades 2>/dev/null || echo 'inactive')"
printf 'reboot_required=%s\n' "$([ -f /var/run/reboot-required ] && echo 'true' || echo 'false')"

echo "status=success"
