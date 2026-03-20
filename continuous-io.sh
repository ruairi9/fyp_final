#!/bin/bash

echo "========================================"
echo "Starting CONTINUOUS I/O for 2 minutes"
echo "========================================"

vagrant ssh control-plane << 'EOF' &
# Run continuous I/O in a loop for 120 seconds
END=$((SECONDS+120))
while [ $SECONDS -lt $END ]; do
    dd if=/dev/zero of=/tmp/iotest.dat bs=1M count=100 oflag=direct 2>/dev/null
    sync
done
rm -f /tmp/iotest.dat
echo "I/O test complete"
EOF

echo ""
echo "✅ Continuous I/O is now running for 2 MINUTES"
echo ""
echo "NOW:"
echo "  1. Refresh dashboard: http://localhost:9000"
echo "  2. You should see Disk I/O at 20-80 MB/s"
echo "  3. Keep refreshing - it will stay high for 2 minutes"
echo ""
echo "To monitor in terminal:"
echo "  vagrant ssh control-plane -c 'iostat -d -m 2'"
echo ""
echo "========================================"
