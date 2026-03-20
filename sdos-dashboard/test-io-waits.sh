#!/bin/bash

echo "=========================================="
echo "I/O WAITS VERIFICATION"
echo "=========================================="
echo ""
echo "Testing 10 times with 2-second intervals..."
echo ""

GOOD=0
for i in {1..10}; do
    # Dashboard value
    DASH=$(curl -s http://localhost:9000/api/server-data 2>/dev/null | python3 -c "import json,sys; print(json.load(sys.stdin)['host_stats']['cpu_wait'])" 2>/dev/null)
    
    # Terminal value (same method as dashboard)
    TERM=$(top -bn1 | grep "Cpu(s)" | python3 -c "
import re, sys
line = sys.stdin.read()
wait_match = re.search(r'([\d.]+)\s+wa', line)
if wait_match:
    print(wait_match.group(1))
else:
    print(0.0)
" 2>/dev/null)
    
    DIFF=$(echo "$DASH - $TERM" | bc 2>/dev/null | sed 's/-//')
    
    printf "Test %2d: Dashboard=%5s%%  Terminal=%5s%%  Diff=%5s%%" "$i" "$DASH" "$TERM" "$DIFF"
    
    if (( $(echo "$DIFF < 5" | bc -l 2>/dev/null) )); then
        echo "  ✅"
        ((GOOD++))
    else
        echo "  ❌"
    fi
    
    sleep 2
done

echo ""
echo "=========================================="
echo "RESULT: $GOOD/10 tests passed (< 5% diff)"
if [ $GOOD -ge 7 ]; then
    echo "✅ I/O WAITS MONITORING IS WORKING"
else
    echo "❌ I/O WAITS MONITORING HAS ISSUES"
fi
echo "=========================================="
