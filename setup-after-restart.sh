#!/bin/bash
# ─── SDOS Post-Restart Setup ──────────────────────────────────────────────────
# Run this every time after rebooting your machine

set -e
cd ~/fyp-cluster

echo "╔══════════════════════════════════════════════════════════╗"
echo "║           SDOS — Post-Restart Setup                     ║"
echo "╚══════════════════════════════════════════════════════════╝"

# Start VMs
echo "Starting VMs..."
vagrant up
echo "Waiting 3 minutes for K3s to initialise..."
sleep 180

# Set kubeconfig
export KUBECONFIG=~/fyp-cluster/k3s.yaml
echo "export KUBECONFIG=~/fyp-cluster/k3s.yaml" >> ~/.bashrc

# Label nodes
echo "Labelling nodes..."
kubectl label nodes worker-dev-integration node-role=development --overwrite 2>/dev/null || true
kubectl label nodes worker-production      node-role=production  --overwrite 2>/dev/null || true

# Show cluster status
echo ""
echo "Cluster status:"
kubectl get nodes

# Start SDOS dashboard
echo ""
echo "Starting SDOS dashboard..."
cd ~/fyp-cluster/sdos-dashboard
bash run-all.sh &

echo ""
echo "╔══════════════════════════════════════════════════════════╗"
echo "║  SDOS is running!                                        ║"
echo "║  Home:      http://localhost:5000                        ║"
echo "║  Jenkins:   http://192.168.121.40:32080                  ║"
echo "║  Grafana:   http://192.168.121.50:32030                  ║"
echo "╚══════════════════════════════════════════════════════════╝"

# Start Jenkins agent
echo "Starting Jenkins host-agent..."
SECRET=$(curl -s "http://192.168.121.40:32080/computer/host-agent/slave-agent.jnlp" \
--user "admin:119841289d2010c9d2b89611641fd17bef" | grep -o 'secret>[^<]*' | cut -d'>' -f2)
cd ~/jenkins-agent
java -jar remoting.jar \
  -url http://192.168.121.40:32080 \
  -secret $SECRET \
  -name host-agent \
  -workDir "/home/ruairi/jenkins-agent" \
  -webSocket > ~/jenkins-agent/agent.log 2>&1 &
echo "Jenkins agent started!"
