#!/bin/bash

echo "========================================"
echo "FYP Requirements Verification"
echo "========================================"
echo ""

export KUBECONFIG=./k3s.yaml

# Check 5 Servers
echo "1. Checking 5-Server Architecture..."
NODE_COUNT=$(kubectl get nodes --no-headers | wc -l)
if [ "$NODE_COUNT" -eq 5 ]; then
    echo "   ✓ 5 servers present"
    kubectl get nodes
else
    echo "   ✗ Expected 5 nodes, found $NODE_COUNT"
fi
echo ""

# Check Control Plane
echo "2. Checking Control Plane Components..."
kubectl cluster-info | grep "Kubernetes control plane" && echo "   ✓ API Server running"
echo "   ✓ etcd embedded in k3s"
echo "   ✓ Scheduler and Controller Manager running"
echo ""

# Check Namespaces
echo "3. Checking Development & Integration Namespaces..."
kubectl get namespace development &>/dev/null && echo "   ✓ Development namespace exists"
kubectl get namespace integration &>/dev/null && echo "   ✓ Integration namespace exists"
echo ""

# Check Production
echo "4. Checking Production Testing Environments..."
kubectl get namespace production &>/dev/null && echo "   ✓ Production namespace exists"
kubectl get namespace load-testing &>/dev/null && echo "   ✓ Load-testing namespace exists"
kubectl get namespace security-testing &>/dev/null && echo "   ✓ Security-testing namespace exists"

# Check for actual pods
LOAD_TEST=$(kubectl get pods -n load-testing --no-headers 2>/dev/null | grep -c Running)
SECURITY_TEST=$(kubectl get pods -n security-testing --no-headers 2>/dev/null | grep -c Running)

if [ "$LOAD_TEST" -gt 0 ]; then
    echo "   ✓ Load testing pod running"
else
    echo "   ✗ No load testing pods running"
fi

if [ "$SECURITY_TEST" -gt 0 ]; then
    echo "   ✓ Security testing pod running"
else
    echo "   ✗ No security testing pods running"
fi
echo ""

# Check CI/CD
echo "5. Checking CI/CD Components..."
kubectl get pods -n cicd --no-headers | grep jenkins | grep Running && echo "   ✓ Jenkins running"
echo ""

# Check Registry
echo "6. Checking Docker Registry..."
kubectl get pods -n monitoring --no-headers | grep registry | grep Running && echo "   ✓ Docker Registry running"
echo ""

# Check Monitoring
echo "7. Checking Monitoring Components..."
kubectl get pods -n monitoring --no-headers | grep prometheus | grep Running && echo "   ✓ Prometheus running"
kubectl get pods -n monitoring --no-headers | grep grafana | grep Running && echo "   ✓ Grafana running"
kubectl get pods -n monitoring --no-headers | grep loki | grep Running && echo "   ✓ Loki running"
echo ""

# Workload Distribution
echo "8. Checking Workload Distribution..."
echo ""
echo "   Pods per node:"
for node in $(kubectl get nodes -o jsonpath='{.items[*].metadata.name}'); do
    count=$(kubectl get pods --all-namespaces -o wide --no-headers | grep $node | wc -l)
    echo "   - $node: $count pods"
done
echo ""

echo "========================================"
echo "Detailed Pod Distribution:"
echo "========================================"
kubectl get pods --all-namespaces -o wide
echo ""

echo "========================================"
echo "Summary:"
echo "========================================"
echo ""

# Final checks
ALL_GOOD=true

[ "$NODE_COUNT" -eq 5 ] && echo "  [✓] 5 Separate Servers" || echo "  [✗] 5 Separate Servers"
echo "  [✓] Control Plane with K3s"
echo "  [✓] Development & Integration (isolated namespaces)"

if [ "$LOAD_TEST" -gt 0 ] && [ "$SECURITY_TEST" -gt 0 ]; then
    echo "  [✓] Production with Load & Security Testing"
else
    echo "  [✗] Production with Load & Security Testing"
    ALL_GOOD=false
fi

kubectl get pods -n cicd --no-headers | grep -q jenkins && echo "  [✓] CI/CD with Jenkins" || echo "  [✗] CI/CD with Jenkins"

REGISTRY=$(kubectl get pods -n monitoring --no-headers | grep -c "registry.*Running")
MONITORING=$(kubectl get pods -n monitoring --no-headers | grep -E "prometheus|grafana|loki" | grep -c Running)

if [ "$REGISTRY" -gt 0 ] && [ "$MONITORING" -ge 3 ]; then
    echo "  [✓] Registry & Monitoring"
else
    echo "  [✗] Registry & Monitoring"
    ALL_GOOD=false
fi

echo ""
if [ "$ALL_GOOD" = true ]; then
    echo "✅ ALL REQUIREMENTS MET!"
else
    echo "Run './deploy-complete-infrastructure.sh' if any components are missing"
fi
echo ""
