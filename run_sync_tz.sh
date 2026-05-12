#!/bin/bash

# 1. Set the timezone to Yekaterinburg
export TZ="Asia/Yekaterinburg"
TARGET_HOUR="05"

# 2. Get the current hour in the specified timezone
CURRENT_HOUR=$(date +%H)

# 3. Check: If hour does not match - exit
if [ "$CURRENT_HOUR" != "$TARGET_HOUR" ]; then
    exit 0
fi

# 4. If we are here — start the daily sync!
echo "[$TZ] Time match: Daily sync at $CURRENT_HOUR:XX. Starting sync_configs..."
/opt/clash-proxy-rules-gen/config-generator/.venv/bin/python /opt/clash-proxy-rules-gen/config-generator/sync_configs.py