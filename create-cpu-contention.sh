#!/bin/bash

echo "=========================================="
echo "Creating CPU Contention (20 seconds)"
echo "=========================================="
echo ""
echo "Starting heavy CPU load on all 5 VMs..."
echo ""

for vm in control-plane worker-dev worker-prod worker-cicd worker-monitoring; do
    echo "Starting on $vm..."
    vagrant ssh $vm -c "
        # Start 8 CPU-intensive processes (more than vCPUs)
        for i in {1..8}; do
            dd if=/dev/zero of=/dev/null &
        done
        
        # Let them run for 20 seconds
        sleep 20
        
        # Kill all dd processes
        pkill dd
        sudo pkill -9 dd
        
        echo '$vm CPU stress complete'
    " 2>/dev/null &
done

echo ""
echo "All VMs running heavy CPU load..."
echo ""
echo "Check steal time now:"
echo "  Terminal: for vm in control-plane worker-dev worker-prod worker-cicd worker-monitoring; do vagrant ssh \$vm -c \"top -bn1 | grep Cpu\"; done"
echo "  Dashboard: http://localhost:9000"
echo ""
echo "Wait 20 seconds for test to complete..."
echo "=========================================="
