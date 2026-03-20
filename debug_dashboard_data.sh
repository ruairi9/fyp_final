#!/bin/bash

echo "================================================"
echo "DEBUGGING: What data does the dashboard see?"
echo "================================================"
echo ""

VM="control-plane"

echo "=== Testing exact dashboard commands ==="
echo ""

# This is what the dashboard runs
vagrant ssh $VM -c "
top -bn1 | grep 'Cpu(s)';
free | grep Mem;
df -h / | tail -1
" 2>/dev/null

echo ""
echo "=== Extracting Steal Time ==="
RESULT=$(vagrant ssh $VM -c "top -bn1 | grep 'Cpu(s)'" 2>/dev/null)
echo "Full line: $RESULT"
ST=$(echo "$RESULT" | grep -oP '[\d.]+(?=\s+st)')
echo "Steal Time extracted: ${ST:-0.0}%"

echo ""
echo "=== Testing iostat ==="
vagrant ssh $VM -c "iostat -d -m 1 1" 2>/dev/null

echo ""
echo "================================================"
