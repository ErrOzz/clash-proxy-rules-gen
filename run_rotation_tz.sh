#!/bin/bash
export TZ="Asia/Yekaterinburg"
TARGET_HOUR="04"
TARGET_DAY="01"

CURRENT_HOUR=$(date +%H)
CURRENT_DAY=$(date +%d)

if [ "$CURRENT_HOUR" != "$TARGET_HOUR" ] || [ "$CURRENT_DAY" != "$TARGET_DAY" ]; then
    exit 0
fi

/opt/clash-proxy-rules-gen/config-generator/.venv/bin/python /opt/clash-proxy-rules-gen/config-generator/rotate_settings.py

LOG_FILE="/opt/clash-proxy-rules-gen/logs/rotate.log"
tail -n 1000 "$LOG_FILE" > "$LOG_FILE.tmp" && mv "$LOG_FILE.tmp" "$LOG_FILE"