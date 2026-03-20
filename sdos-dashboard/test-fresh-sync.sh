#!/bin/bash

echo "=========================================="
echo "FRESH DATA SYNC TEST"
echo "=========================================="
echo ""

for i in {1..10}; do
    echo "=== Test $i ==="
    
    # Get FRESH dashboard data (no cache)
    DASH_CPU=$(curl -s "http://localhost:9000/api/server-data-fresh?t=$(date +%s%N)" | python3 -c "
import json, sys
data = json.load(sys.stdin)
print(data['host_stats']['cpu_usage'])
")
    
    # IMMEDIATELY get terminal
    TERM_CPU=$(top -bn1 | grep "Cpu(s)" | python3 -c "
import re, sys
line = sys.stdin.read()
idle_match = re.search(r'([\d.]+)\s*id', line)
if idle_match:
    idle = float(idle_match.group(1))
    cpu = round(100 - idle, 1)
    print(cpu)
")
    
    DIFF=$(echo "$DASH_CPU - $TERM_CPU" | bc 2>/dev/null | awk '{printf "%.1f", ($1 < 0 ? -$1 : $1)}')
    
    printf "Dashboard: %5s%%  |  Terminal: %5s%%  |  Diff: %5s%%" "$DASH_CPU" "$TERM_CPU" "$DIFF"
    
    if (( $(echo "$DIFF < 5" | bc -l) )); then
        echo "  ✅"
    else
        echo "  ⚠️"
    fi
    
    sleep 1
done

echo ""
echo "=========================================="
echo "Count how many show ✅ (< 5% diff)"
echo "If 7+ out of 10 = WORKING CORRECTLY"
echo "=========================================="
