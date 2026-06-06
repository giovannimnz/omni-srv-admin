#!/bin/sh
# startwm.sh - LXDE with XRDP

# Unset problematic variables
unset DBUS_SESSION_BUS_ADDRESS
unset XDG_RUNTIME_DIR

# Ensure HOME is correct
if [ -z "$HOME" ] || [ "$HOME" = "/tmp" ]; then
    export HOME=$(getent passwd $(whoami) | cut -d: -f6)
fi

# Set XAUTHORITY properly
export XAUTHORITY="$HOME/.Xauthority"

# Load user profile if exists
if [ -r /etc/profile ]; then
    . /etc/profile
fi

# Force HOME again after profile
export HOME=$(getent passwd $(whoami) | cut -d: -f6)
export XAUTHORITY="$HOME/.Xauthority"

# Set up XDG directories
export XDG_SESSION_TYPE=x11
export XDG_SESSION_CLASS=user
export XDG_SESSION_DESKTOP=LXDE
export XDG_CURRENT_DESKTOP=LXDE
export DESKTOP_SESSION=LXDE
export XDG_DATA_DIRS=/usr/local/share:/usr/share:/var/lib/snapd/desktop
export XDG_CONFIG_DIRS=/etc/xdg

# Start D-Bus session bus
if [ -z "$DBUS_SESSION_BUS_ADDRESS" ]; then
    eval $(dbus-launch --sh-syntax --exit-with-session)
fi

# Force ABNT2 keyboard layout - DISPLAY is set by xrdp before this runs
# Using while loop to wait for X to be ready (max 10 seconds)
for i in $(seq 1 10); do
    if [ -n "$DISPLAY" ] && /usr/bin/setxkbmap -model pc105 -layout br -variant abnt2 -option -option lv3:ralt_switch 2>/dev/null; then
        break
    fi
    sleep 1
done

# Keep ABNT2 enforced during the whole XRDP session. This prevents client
# layout autodetection or GUI tools from leaving the session in another layout.
if [ -x "$HOME/bin/setxkbmap-abnt2.sh" ]; then
    "$HOME/bin/setxkbmap-abnt2.sh" --watch &
fi

# Start LXDE session
exec startlxde
