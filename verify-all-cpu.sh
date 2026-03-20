#!/bin/bash

echo "=========================================="
echo "CPU UTILISATION VERIFICATION"
echo "=========================================="
echo ""

echo "HOST CPU:"
echo "----------"

# Get dashboard value
DASH_HOST=$(curl -s http://localhost:9000/api/server-data | python3 -c "import json,sys; print(json.load(sys.stdin)['host_stats']['cpu_usage'])")

# Get terminal value (exact same method as dashboard)
TERM_HOST=$(top -bn1 | grep "Cpu(s)" | python3 -c "
import re, sys
line = sys.stdin.read()
idle_match = re.search(r'([\d.]+)\s*id', line)
if idle_match:
    idle = float(idle_match.group(1))
    cpu = round(100 - idle, 1)
    print(cpu)
")

DIFF_HOST=$(echo "$DASH_HOST - $TERM_HOST" | bc 2>/dev/null | awk '{printf "%.1f", ($1 < 0 ? -$1 : $1)}')

echo "Dashboard: ${DASH_HOST}%"
echo "Terminal:  ${TERM_HOST}%"
echo "Difference: ${DIFF_HOST}%"

if (( $(echo "$DIFF_HOST < 10" | bc -l) )); then
    echo "✅ PASS - Difference < 10%"
else
    echo "❌ FAIL - Difference too large!"
fi

echo ""
echo "VM CPU VALUES:"
echo "--------------"

# Test each VM
for vm_pair in "control-plane:control-plane" "worker-dev:worker-dev-integration" "worker-prod:worker-production" "worker-cicd:worker-cicd" "worker-monitoring:worker-registry-monitoring"; do
    IFS=':' read -r vagrant_name display_name <<< "$vm_pair"
    
    # Dashboard value
    DASH_VM=$(curl -s http://localhost:9000/api/server-data | python3 -c "
import json, sys
data = json.load(sys.stdin)
for vm in data['vms']:
    if vm['name'] == '$display_name':
        print(vm['cpu'])
        break
")
    
    # Terminal value
    TERM_VM=$(vagrant ssh $vagrant_name -c "top -bn1 | grep 'Cpu(s)'" 2>/dev/null | python3 -c "
import re, sys
line = sys.stdin.read()
idle_match = re.search(r'([\d.]+)\s*id', line)
if idle_match:
    idle = float(idle_match.group(1))
    cpu = round(100 - idle, 1)
    print(cpu)
" 2>/dev/null)
    
    DIFF_VM=$(echo "$DASH_VM - $TERM_VM" | bc 2>/dev/null | awk '{printf "%.1f", ($1 < 0 ? -$1 : $1)}')
    
    printf "%-30s Dashboard: %5s%%  Terminal: %5s%%  Diff: %5s%%" "$display_name" "$DASH_VM" "$TERM_VM" "$DIFF_VM"
    
    if (( $(echo "$DIFF_VM < 10" | bc -l) )); then
        echo "  ✅"
    else
        echo "  ❌"
    fi
done

echo ""
echo "=========================================="
echo "SUMMARY:"
echo "Differences < 10% = WORKING CORRECTLY"
echo "Differences > 10% = Needs investigation"
echo "=========================================="
