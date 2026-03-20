#!/bin/bash
echo "Stopping all SDOS services..."

# Kill Python processes
pkill -f home.py
pkill -f dashboard.py
pkill -f server_dashboard.py
pkill -f pipeline_dashboard.py
pkill -f developer_workspace.py

# Force kill ports
sudo fuser -k 5000/tcp 2>/dev/null
sudo fuser -k 8080/tcp 2>/dev/null
sudo fuser -k 9000/tcp 2>/dev/null
sudo fuser -k 7000/tcp 2>/dev/null
sudo fuser -k 6001/tcp 2>/dev/null

echo "All services stopped!"
