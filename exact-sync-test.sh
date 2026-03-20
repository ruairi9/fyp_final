#!/bin/bash

echo "=========================================="
echo "EXACT SYNCHRONIZED CPU TEST"
echo "=========================================="
echo ""
echo "Strategy: Trigger dashboard refresh, then"
echo "immediately sample terminal within 0.1 sec"
echo ""

for i in {1..5}; do
    echo "=== Test $i ==="
    
    # Trigger dashboard refresh by calling the API
    # This forces it to fetch fresh data RIGHT NOW
    DASH_DATA=$(curl -s http://localhost:9000/api/server-data)
    
    # IMMEDIATELY get terminal value (within milliseconds)
    TERM_CPU=$(top -bn1 | grep "Cpu(s)" | python3 -c "
import re, sys
line = sys.stdin.read()
idle_match = re.search(r'([\d.]+)\s*id', line)
if idle_match:
    idle = float(idle_match.group(1))
    cpu = round(100 - idle, 1)
    print(cpu)
")
    
    # Extract dashboard value from the data we just fetched
    DASH_CPU=$(echo "$DASH_DATA" | python3 -c "
import json, sys
data = json.load(sys.stdin)
print(data['host_stats']['cpu_usage'])
")
    
    DIFF=$(echo "$DASH_CPU - $TERM_CPU" | bc 2>/dev/null | awk '{printf "%.1f", ($1 < 0 ? -$1 : $1)}')
    
    echo "Dashboard: ${DASH_CPU}%  |  Terminal: ${TERM_CPU}%  |  Diff: ${DIFF}%"
    
    sleep 2
done

echo ""
echo "=========================================="
echo "If most tests show <5% difference = WORKING"
echo "If most tests show >10% difference = BUG"
echo "=========================================="
