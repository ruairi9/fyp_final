#!/bin/bash

echo "=========================================="
echo "CPU UTILISATION VERIFICATION"
echo "=========================================="
echo ""
echo "Testing 10 times with 2-second intervals..."
echo ""

GOOD=0
for i in {1..10}; do
    DASH=$(curl -s http://localhost:9000/api/server-data 2>/dev/null | python3 -c "import json,sys; print(json.load(sys.stdin)['host_stats']['cpu_usage'])" 2>/dev/null)
    TERM=$(top -bn1 | grep "Cpu(s)" | python3 -c "import re,sys; m=re.search(r'([\d.]+)\s+id',sys.stdin.read()); print(round(100-float(m.group(1)),1) if m else 0)" 2>/dev/null)
    
    DIFF=$(echo "$DASH - $TERM" | bc 2>/dev/null | sed 's/-//')
    
    printf "Test %2d: Dashboard=%5s%%  Terminal=%5s%%  Diff=%5s%%" "$i" "$DASH" "$TERM" "$DIFF"
    
    if (( $(echo "$DIFF < 15" | bc -l 2>/dev/null) )); then
        echo "  ✅"
        ((GOOD++))
    else
        echo "  ❌"
    fi
    
    sleep 2
done

echo ""
echo "=========================================="
echo "RESULT: $GOOD/10 tests passed (< 15% diff)"
if [ $GOOD -ge 6 ]; then
    echo "✅ CPU MONITORING IS WORKING"
else
    echo "❌ CPU MONITORING HAS ISSUES"
fi
echo "=========================================="
