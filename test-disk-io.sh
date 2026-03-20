#!/bin/bash

echo "Starting heavy disk I/O on control-plane..."

vagrant ssh control-plane << 'EOF'
# Generate heavy I/O
dd if=/dev/zero of=/tmp/test1.dat bs=1M count=1000 oflag=direct 2>/dev/null &
dd if=/dev/zero of=/tmp/test2.dat bs=1M count=1000 oflag=direct 2>/dev/null &
dd if=/dev/zero of=/tmp/test3.dat bs=1M count=1000 oflag=direct 2>/dev/null &

echo "Heavy I/O running for 30 seconds..."
sleep 30

# Cleanup
pkill dd
rm -f /tmp/test*.dat

echo "Done!"
EOF

echo "Test complete. Refresh dashboard to see results."
