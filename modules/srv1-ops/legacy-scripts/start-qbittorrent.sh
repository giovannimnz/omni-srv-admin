#!/bin/bash
# Start qbittorrent-nox with Google Drive mount
# Usage: ./start-qbittorrent.sh

MOUNT_POINT="/home/ubuntu/gdrive"
QDOWNLOADS="$MOUNT_POINT/downloads"

# Check if mount is active
if ! mountpoint -q "$MOUNT_POINT"; then
    echo "Mounting Google Drive first..."
    /home/ubuntu/mount-gdrive.sh start
    sleep 2
fi

# Create downloads folder if not exists
mkdir -p "$QDOWNLOADS"

echo "Starting qbittorrent-nox with downloads at: $QDOWNLOADS"
echo "Web UI: http://127.0.0.1:8080"
echo "Default credentials: admin:adminadmin"

# Start qbittorrent-nox
qbittorrent-nox -d \
    --download-save-path="$QDOWNLOADS" \
    --webui-port=8080
