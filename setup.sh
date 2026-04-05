#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
KUBECONFIG="$SCRIPT_DIR/k3s.yaml"
EXPECTED_VMS=5

echo "============================================"
echo " SDOS Project Setup"
echo "============================================"
echo ""

# Check Ubuntu
if ! grep -q "Ubuntu" /etc/os-release 2>/dev/null; then
    echo "ERROR: This setup requires Ubuntu"
    exit 1
fi

# Check virtualisation
if ! kvm-ok > /dev/null 2>&1; then
    echo "ERROR: KVM virtualisation not available"
    echo "Enable virtualisation in your BIOS and try again"
    exit 1
fi

# Install dependencies
echo "Installing dependencies..."
sudo apt-get update -q
sudo apt-get install -y \
    vagrant \
    libvirt-daemon-system \
    libvirt-clients \
    virtinst \
    qemu-kvm \
    docker.io \
    docker-compose \
    git \
    cpu-checker \
    curl

# Fix 5: Install kubectl
if ! which kubectl > /dev/null 2>&1; then
    echo "Installing kubectl..."
    curl -LO "https://dl.k8s.io/release/v1.28.5/bin/linux/amd64/kubectl"
    chmod +x kubectl
    sudo mv kubectl /usr/local/bin/
fi

# Install vagrant-libvirt plugin
vagrant plugin install vagrant-libvirt 2>/dev/null || true

# Add user to groups
sudo usermod -aG libvirt $USER
sudo usermod -aG docker $USER

# Fix 6: Check if user is already in groups before continuing
if ! groups | grep -q docker || ! groups | grep -q libvirt; then
    echo ""
    echo "============================================"
    echo " ACTION REQUIRED"
    echo "============================================"
    echo " You have been added to the docker and"
    echo " libvirt groups but you must log out and"
    echo " log back in for this to take effect."
    echo ""
    echo " After logging back in run:"
    echo "   bash setup.sh"
    echo "============================================"
    exit 0
fi

# ── Start VMs ────────────────────────────────────────────────
echo ""
echo "Starting VMs (this takes 30-60 mins first time)..."
cd "$SCRIPT_DIR"
vagrant up

echo ""
echo "Waiting for VMs to be ready..."
sleep 60

# ── Check 1: VMs running (Fix 2 + Fix 3) ─────────────────────
echo ""
echo "Checking VM status..."
RUNNING=$(vagrant status --machine-readable | grep ",state,running" | wc -l)
if [ "$RUNNING" -eq "$EXPECTED_VMS" ]; then
    echo "PASS: All $EXPECTED_VMS VMs are running"
else
    echo "FAIL: Only $RUNNING/$EXPECTED_VMS VMs running"
    vagrant status
    exit 1
fi

# ── Check 2: Kubernetes responding ───────────────────────────
echo ""
echo "Checking Kubernetes cluster..."
for i in $(seq 1 12); do
    if kubectl --kubeconfig=$KUBECONFIG get nodes >/dev/null 2>&1; then
        break
    fi
    echo "Waiting for Kubernetes API... ($i/12)"
    sleep 10
done

NODES=$(kubectl --kubeconfig=$KUBECONFIG get nodes --no-headers 2>/dev/null | wc -l)
NOT_READY=$(kubectl --kubeconfig=$KUBECONFIG get nodes --no-headers 2>/dev/null | grep -vc "Ready" || echo 99)
if [ "$NODES" -ge 1 ] && [ "$NOT_READY" -eq 0 ]; then
    echo "PASS: All $NODES nodes Ready"
else
    echo "FAIL: Some nodes not Ready"
    kubectl --kubeconfig=$KUBECONFIG get nodes
    exit 1
fi

# ── Check 3: Pods running (Fix 1) ────────────────────────────
echo ""
echo "Checking pods..."
sleep 30
TOTAL=$(kubectl --kubeconfig=$KUBECONFIG get pods --all-namespaces --no-headers 2>/dev/null | wc -l)
RUNNING_PODS=$(kubectl --kubeconfig=$KUBECONFIG get pods --all-namespaces --no-headers 2>/dev/null | grep -c Running || echo 0)
echo "Pods running: $RUNNING_PODS / $TOTAL"
BAD=$(kubectl --kubeconfig=$KUBECONFIG get pods -A --no-headers 2>/dev/null | grep -E "CrashLoopBackOff|Error|Pending" | wc -l)
if [ "$RUNNING_PODS" -eq "$TOTAL" ] && [ "$TOTAL" -gt 0 ] && [ "$BAD" -eq 0 ]; then
    echo "PASS: All pods healthy ($RUNNING_PODS/$TOTAL)"
else
    echo "FAIL: Pod issues detected ($RUNNING_PODS running, $BAD unhealthy)"
    kubectl --kubeconfig=$KUBECONFIG get pods -A
    exit 1
fi

# ── Start dashboards ─────────────────────────────────────────
echo ""
echo "Starting dashboards..."
cd "$SCRIPT_DIR/sdos-dashboard"
docker-compose up -d

echo ""
echo "Waiting for dashboards to start..."
sleep 15

# ── Check 4: Dashboard services reachable (Fix 4) ────────────
echo ""
echo "Checking dashboard services..."
ALL_UP=true
for PORT in 5000 8080 9000 7000 6001; do
    if curl -sf --max-time 5 http://localhost:$PORT > /dev/null; then
        echo "PASS: Service on port $PORT reachable"
    else
        echo "WARN: Service on port $PORT not reachable yet"
        ALL_UP=false
    fi
done

echo ""
echo "============================================"
echo " SDOS Setup Complete!"
echo "============================================"
echo " Home:      http://localhost:5000"
echo " Dashboard: http://localhost:8080"
echo " Server:    http://localhost:9000"
echo " Pipeline:  http://localhost:7000"
echo " Workspace: http://localhost:6001"
echo "============================================"
if [ "$ALL_UP" = false ]; then
    echo ""
    echo "NOTE: Some services not reachable yet."
    echo "Wait 30 seconds and try the URLs above."
fi
echo "============================================"
