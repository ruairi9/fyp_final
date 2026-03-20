#!/bin/bash

echo "Synchronized CPU Comparison (Press Ctrl+C to stop):"
echo "===================================================="
echo ""

while true; do
    TIMESTAMP=$(date +%H:%M:%S)
    
    # Get BOTH values at the same moment
    DASHBOARD=$(curl -s http://localhost:9000/api/server-data | python3 -c "import json, sys; data=json.load(sys.stdin); print(data['host_stats']['cpu_usage'])" 2>/dev/null)
    
    TERMINAL=$(top -bn1 | grep "Cpu(s)" | python3 -c "
import re, sys
line = sys.stdin.read()
idle_match = re.search(r'([\d.]+)\s*id', line)
if idle_match:
    idle = float(idle_match.group(1))
    cpu_usage = round(100 - idle, 1)
    print(cpu_usage)
" 2>/dev/null)
    
    # Compare
    if [ "$DASHBOARD" == "$TERMINAL" ]; then
        STATUS="✅ MATCH"
    else
        DIFF=$(echo "$DASHBOARD - $TERMINAL" | bc 2>/dev/null || echo "?")
        STATUS="❌ DIFF: ${DIFF}%"
    fi
    
    echo "[$TIMESTAMP] Dashboard: ${DASHBOARD}%  |  Terminal: ${TERMINAL}%  |  $STATUS"
    
    sleep 2
done
