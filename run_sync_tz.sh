#!/bin/bash
/opt/clash-proxy-rules-gen/config-generator/.venv/bin/python /opt/clash-proxy-rules-gen/config-generator/sync_configs.py

LOG_FILE="/opt/clash-proxy-rules-gen/logs/sync.log"
tail -n 1000 "$LOG_FILE" > "$LOG_FILE.tmp" && mv "$LOG_FILE.tmp" "$LOG_FILE"