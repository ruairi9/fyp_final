#!/bin/bash

echo "Generating CPU load on all VMs..."
echo "This will max out CPUs for 20 seconds"
echo ""

for vm in control-plane worker-dev worker-prod worker-cicd worker-monitoring; do
    echo "Starting CPU stress on $vm..."
    vagrant ssh $vm -c "
        # CPU stress - run 4 threads at 100%
        for i in {1..4}; do
            dd if=/dev/zero of=/dev/null &
        done
        
        sleep 20
        pkill dd
        echo 'CPU stress on $vm complete'
    " &
done

echo ""
echo "NOW: Refresh the dashboard at http://localhost:9000"
echo "CPU usage should spike to 80-100%!"
echo ""
echo "Wait 20 seconds for test to complete..."

wait
echo ""
echo "All tests complete!"
