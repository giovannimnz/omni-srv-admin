#!/usr/bin/env bash
set -euo pipefail

exec env -i \
  HOME=/home/ubuntu \
  USER=ubuntu \
  LOGNAME=ubuntu \
  PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \
  PM2_HOME=/home/ubuntu/.pm2 \
  /usr/local/bin/pm2 start \
  /home/ubuntu/GitHub/oci-admin/deploy/pm2/ecosystem.config.cjs \
  "$@"
