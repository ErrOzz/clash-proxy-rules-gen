#!/bin/bash

echo "================================================="
echo "📅 Date: $(date +'%Y-%m-%d %H:%M:%S')"
echo "🔍 Starting smart sync check..."

# Start the sync_configs.py script without the --force flag to check for changes in external providers
/opt/clash-proxy-rules-gen/config-generator/.venv/bin/python /opt/clash-proxy-rules-gen/config-generator/sync_configs.py

echo "✅ Smart sync check finished."
echo ""

# Enter crontab -e and change the sync schedule. For example, run every 30 minutes:
# Start smart check every 30 minutes. Updates Gist only if external subs changed.
# */30 * * * * /opt/clash-proxy-rules-gen/run_sync_tz.sh >> /opt/clash-proxy-rules-gen/logs/sync.log 2>&1