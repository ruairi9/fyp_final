#!/bin/bash

echo "=========================================="
echo "TRACING DASHBOARD CPU CALCULATION"
echo "=========================================="
echo ""

echo "Step 1: Dashboard runs this command:"
echo "  subprocess.run(['top', '-bn1'])"
echo ""

echo "Step 2: Raw top output (Cpu line):"
TOP_OUTPUT=$(top -bn1 | grep "Cpu(s)")
echo "$TOP_OUTPUT"
echo ""

echo "Step 3: Dashboard regex extraction:"
python3 << EOF
import re
line = "$TOP_OUTPUT"
print(f"Input line: {line}")
idle_match = re.search(r'([\d.]+)\s*id', line)
if idle_match:
    idle = float(idle_match.group(1))
    cpu_percent = round(100 - idle, 1)
    print(f"Idle found: {idle}%")
    print(f"CPU calculated: {cpu_percent}%")
else:
    print("ERROR: No match found!")
EOF

echo ""
echo "Step 4: What dashboard actually returns:"
DASH_CPU=$(curl -s http://localhost:9000/api/server-data | python3 -c "import json,sys; print(json.load(sys.stdin)['host_stats']['cpu_usage'])")
echo "Dashboard API: ${DASH_CPU}%"

echo ""
echo "Step 5: Let's check the dashboard code:"
grep -A 15 "# CPU usage" ~/fyp-cluster/sdos-dashboard/server_dashboard.py | head -20

echo ""
echo "=========================================="
echo "CONCLUSION:"
echo "If Step 3 and Step 4 match = Working correctly"
echo "If Step 3 and Step 4 differ = Bug in code"
echo "=========================================="
