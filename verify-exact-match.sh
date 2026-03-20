#!/bin/bash

echo "=========================================="
echo "EXACT VALUE COMPARISON"
echo "=========================================="
echo ""

# Fetch dashboard data via API
echo "Fetching dashboard data..."
DASHBOARD_DATA=$(curl -s http://localhost:9000/api/server-data)

echo ""
echo "Dashboard values (from API):"
echo "$DASHBOARD_DATA" | python3 -c "
import json, sys
data = json.load(sys.stdin)
for vm in data['vms']:
    print(f\"{vm['name']:30s} Disk I/O: {vm['disk_io']}\")
"

echo ""
echo "=========================================="
echo ""

# Now fetch terminal values
echo "Terminal values (iostat -d -m 1 2):"
for vm_pair in "control-plane:control-plane" "worker-dev-integration:worker-dev" "worker-production:worker-prod" "worker-cicd:worker-cicd" "worker-registry-monitoring:worker-monitoring"; do
    IFS=':' read -r display_name vagrant_name <<< "$vm_pair"
    
    TOTAL=$(vagrant ssh $vagrant_name -c "iostat -d -m 1 2 | grep vda | tail -1 | awk '{printf \"%.2f\", \$3+\$4}'" 2>/dev/null)
    printf "%-30s Disk I/O: %s MB/s\n" "$display_name" "$TOTAL"
done

echo ""
echo "=========================================="
echo "NOTE: Values may differ by a few MB/s due to"
echo "the dashboard and terminal sampling at"
echo "slightly different moments (5-10 seconds apart)"
echo "=========================================="
