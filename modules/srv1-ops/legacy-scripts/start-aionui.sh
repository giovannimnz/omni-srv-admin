#!/bin/bash
# Wrapper script to run AionUI in headless mode with virtual display (DEV mode)
cd ~/GitHub/forks/AionUi
exec /usr/bin/xvfb-run --auto-servernum --server-args="-screen 0 1280x1024x24" \
  /home/ubuntu/.nvm/versions/node/v24.13.1/bin/node \
  ~/GitHub/forks/AionUi/node_modules/.bin/electron-vite dev -- --webui --remote
