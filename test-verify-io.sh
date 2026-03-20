#!/bin/bash

echo "=========================================="
echo "DISK I/O TEST & VERIFICATION"
echo "=========================================="
echo ""

VM="control-plane"

echo "Step 1: Check CURRENT I/O (should be ~0)"
echo "-------------------------------------------"
vagrant ssh $VM -c "iostat -d -m 1 2 2>/dev/null | tail -5" 2>/dev/null

echo ""
echo "Step 2: Starting HEAVY disk write..."
echo "-------------------------------------------"

# Start disk I/O in background
vagrant ssh $VM -c "
nohup sh -c '
for i in 1 2 3 4 5; do
    dd if=/dev/zero of=/tmp/iotest\$i.dat bs=1M count=200 oflag=direct 2>/dev/null &
done
sleep 20
pkill dd
rm -f /tmp/iotest*.dat
' > /dev/null 2>&1 &
" 2>/dev/null &

sleep 3

echo ""
echo "Step 3: Checking I/O DURING write (should be HIGH)"
echo "-------------------------------------------"
for i in {1..5}; do
    echo "Reading $i:"
    vagrant ssh $VM -c "iostat -d -m 1 1 2>/dev/null | grep -E 'sda|vda|xvda' | head -1" 2>/dev/null
    sleep 2
done

echo ""
echo "=========================================="
echo "NOW refresh dashboard: http://localhost:9000"
echo "control-plane Disk I/O should show 20-100 MB/s!"
echo "=========================================="
