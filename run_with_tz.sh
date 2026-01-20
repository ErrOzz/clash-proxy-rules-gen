#!/bin/bash

# 1. Setting the timezone to Asia/Yekaterinburg
export TZ="Asia/Yekaterinburg"
TARGET_HOUR="04"
TARGET_DAYS=("01" "15")  # List of days to run the script

# 2. Get current hour and day in the specified timezone
CURRENT_HOUR=$(date +%H)
CURRENT_DAY=$(date +%d)

# 3. Check hour
if [ "$CURRENT_HOUR" != "$TARGET_HOUR" ]; then
    exit 0
fi

# 4. Check day
MATCH_DAY=false
for day in "${TARGET_DAYS[@]}"; do
    if [ "$CURRENT_DAY" == "$day" ]; then
        MATCH_DAY=true
        break
    fi
done

if [ "$MATCH_DAY" = false ]; then
    exit 0
fi

# 5. IF WE ARE HERE — IT'S TIME!
# Run the main Python script
echo "[$TZ] Time match: $CURRENT_DAY at $CURRENT_HOUR:XX. Starting rotation..."
/opt/clash-proxy-rules-gen/config-generator/.venv/bin/python /opt/clash-proxy-rules-gen/config-generator/rotate_settings.py