#!/bin/bash
# ─── SDOS Setup Script ────────────────────────────────────────────────────────
# Run this once on a new machine to get everything up and running.

set -e
echo "╔══════════════════════════════════════════════════════════╗"
echo "║              SDOS — Initial Setup Script                 ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""

# ── Check dependencies ────────────────────────────────────────────────────────
check() {
    if command -v "$1" &>/dev/null; then
        echo "  ✓ $1 found"
    else
        echo "  ✗ $1 NOT found — please install it first"
        MISSING=1
    fi
}

echo "Checking dependencies..."
check vagrant
check docker
check kubectl
[ "$MISSING" = "1" ] && echo "" && echo "Install missing dependencies then re-run." && exit 1
echo ""

# ── Start the cluster ─────────────────────────────────────────────────────────
echo "Starting Vagrant VMs..."
vagrant up
echo ""
echo "Waiting 3 minutes for K3s to initialise..."
sleep 180

# ── Configure kubectl ─────────────────────────────────────────────────────────
export KUBECONFIG="$(pwd)/k3s.yaml"
echo "export KUBECONFIG=$(pwd)/k3s.yaml" >> ~/.bashrc
echo "Kubeconfig set to $(pwd)/k3s.yaml"
echo ""

# ── Label nodes ───────────────────────────────────────────────────────────────
echo "Labelling worker nodes..."
kubectl label nodes worker-dev-integration node-role=development --overwrite
kubectl label nodes worker-production      node-role=production  --overwrite
echo ""

# ── Show cluster status ───────────────────────────────────────────────────────
echo "Cluster status:"
kubectl get nodes
echo ""

# ── Start SDOS dashboard ──────────────────────────────────────────────────────
echo "Starting SDOS dashboard..."
if command -v docker &>/dev/null && docker compose version &>/dev/null 2>&1; then
    docker compose up --build -d
    echo ""
    echo "╔══════════════════════════════════════════════════════════╗"
    echo "║  SDOS is running!                                        ║"
    echo "║                                                          ║"
    echo "║  Home:      http://localhost:5000                        ║"
    echo "║  Dashboard: http://localhost:8080                        ║"
    echo "║  Server:    http://localhost:9000                        ║"
    echo "║  Pipeline:  http://localhost:7000                        ║"
    echo "║  Workspace: http://localhost:6001                        ║"
    echo "╚══════════════════════════════════════════════════════════╝"
else
    pip install -r requirements.txt
    bash run-all.sh
fi
