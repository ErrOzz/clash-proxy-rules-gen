#!/bin/bash

# 1. Seting the timezone to Yekaterinburg
export TZ="Asia/Yekaterinburg"
TARGET_HOUR="04"
TARGET_DAY="01"  # Set the target day of the month

# 2. Get the current hour and day in the specified timezone
CURRENT_HOUR=$(date +%H)
CURRENT_DAY=$(date +%d)

# 3. Check: If hour does not match - exit
if [ "$CURRENT_HOUR" != "$TARGET_HOUR" ]; then
    exit 0
fi

# 4. Check: If day does not match - exit
if [ "$CURRENT_DAY" != "$TARGET_DAY" ]; then
    exit 0
fi

# 5. If we are here — stars have aligned. Start the rotation!
echo "[$TZ] Time match: Day $CURRENT_DAY at $CURRENT_HOUR:XX. Starting rotation..."
/opt/clash-proxy-rules-gen/config-generator/.venv/bin/python /opt/clash-proxy-rules-gen/config-generator/rotate_settings.py

# crontab -e
# paste the following line to schedule the script:
# # Start check every hour in :30 minuts.
# # The run_with_tz.sh script will decide whether something needs to be done based on the Ekb time.
# 30 * * * * /opt/clash-proxy-rules-gen/run_with_tz.sh >> /opt/clash-proxy-rules-gen/logs/rotate.log 2>&1
