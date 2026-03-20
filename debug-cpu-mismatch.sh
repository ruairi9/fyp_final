#!/bin/bash

echo "CPU Debugging - Finding the mismatch"
echo "====================================="
echo ""

echo "1. What command does the dashboard run?"
echo "   Answer: top -bn1 | grep Cpu(s)"
echo ""

echo "2. Host CPU command (what dashboard uses):"
top -bn1 | grep "Cpu(s)"
echo ""

echo "3. Extract idle with regex (dashboard method):"
top -bn1 | grep "Cpu(s)" | python3 -c "
import re, sys
line = sys.stdin.read()
print('Full line:', line.strip())
idle_match = re.search(r'([\d.]+)\s*id', line)
if idle_match:
    idle = float(idle_match.group(1))
    print(f'Idle extracted: {idle}%')
    cpu_usage = round(100 - idle, 1)
    print(f'CPU calculated: {cpu_usage}%')
"
echo ""

echo "4. What dashboard API returns:"
curl -s http://localhost:9000/api/server-data | python3 -c "
import json, sys
data = json.load(sys.stdin)
print(f\"Dashboard CPU: {data['host_stats']['cpu_usage']}%\")
"
echo ""

echo "5. Multiple samples to see variation:"
for i in {1..5}; do
    CPU=$(top -bn1 | grep "Cpu(s)" | python3 -c "
import re, sys
line = sys.stdin.read()
idle_match = re.search(r'([\d.]+)\s*id', line)
if idle_match:
    idle = float(idle_match.group(1))
    cpu_usage = round(100 - idle, 1)
    print(cpu_usage)
")
    echo "  Sample $i: ${CPU}%"
    sleep 1
done

echo ""
echo "6. Check if dashboard is using different top command:"
grep -A 10 "def get_host_stats" ~/fyp-cluster/sdos-dashboard/server_dashboard.py | grep -A 3 "CPU usage"
