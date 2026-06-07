#!/bin/bash
# Mount Google Drive via rclone
# Usage: ./mount-gdrive.sh [start|stop|status]

MOUNT_POINT="/home/ubuntu/gdrive"
PID_FILE="/home/ubuntu/gdrive/.mount.pid"

start_mount() {
    if mountpoint -q "$MOUNT_POINT"; then
        echo "Already mounted at $MOUNT_POINT"
        return 0
    fi
    echo "Mounting Google Drive at $MOUNT_POINT..."
    rclone mount gdrive: "$MOUNT_POINT" \
        --config=/home/ubuntu/.config/rclone/rclone.conf \
        --allow-other \
        --read-only \
        --dir-cache-time=1h \
        --vfs-cache-mode=reads \
        --vfs-read-ahead=512M \
        --daemon-pid-file="$PID_FILE"
    echo "Mounted successfully"
}

stop_mount() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if kill -0 "$PID" 2>/dev/null; then
            kill "$PID"
            echo "Unmounted"
        fi
        rm -f "$PID_FILE"
    fi
    fusermount -uz "$MOUNT_POINT" 2>/dev/null || true
}

case "$1" in
    start) start_mount ;;
    stop) stop_mount ;;
    status) mountpoint -q "$MOUNT_POINT" && echo "Mounted" || echo "Not mounted" ;;
    *) echo "Usage: $0 [start|stop|status]" ;;
esac
