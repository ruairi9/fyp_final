#!/bin/bash
cd "$(dirname "$0")"
mkdir -p logs

# Kill anything already on these ports
for PORT in 5000 6001 7000 8080 9000; do
    fuser -k ${PORT}/tcp 2>/dev/null
done

echo "Starting SDOS..."

python3 home.py                > logs/home.log                2>&1 &
python3 dashboard.py           > logs/dashboard.log           2>&1 &
python3 server_dashboard.py    > logs/server_dashboard.log    2>&1 &
python3 pipeline_dashboard.py  > logs/pipeline_dashboard.log  2>&1 &
python3 developer_workspace.py > logs/developer_workspace.log 2>&1 &

echo ""
echo "Home:      http://localhost:5000"
echo "Dashboard: http://localhost:8080"
echo "Server:    http://localhost:9000"
echo "Pipeline:  http://localhost:7000"
echo "Workspace: http://localhost:6001"
echo ""
echo "Press Ctrl+C to stop"

trap "fuser -k 5000/tcp 6001/tcp 7000/tcp 8080/tcp 9000/tcp 2>/dev/null; echo 'Stopped'; exit" INT
wait
