#!/bin/bash

echo "Testing Registry, Monitoring & Logging Stack"
echo "============================================="
echo ""

export KUBECONFIG=./k3s.yaml

echo "1. Testing Docker Registry..."
REGISTRY_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://192.168.121.50:30500/v2/)
if [ "$REGISTRY_STATUS" = "200" ]; then
    echo "✅ Docker Registry: Working"
else
    echo "❌ Docker Registry: Failed (HTTP $REGISTRY_STATUS)"
fi

echo ""
echo "2. Testing Prometheus..."
PROM_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://192.168.121.50:32090/-/healthy)
if [ "$PROM_STATUS" = "200" ]; then
    echo "✅ Prometheus: Working"
else
    echo "❌ Prometheus: Failed (HTTP $PROM_STATUS)"
fi

echo ""
echo "3. Testing Grafana..."
GRAFANA_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://192.168.121.50:32030/login)
if [ "$GRAFANA_STATUS" = "200" ]; then
    echo "✅ Grafana: Working"
else
    echo "❌ Grafana: Failed (HTTP $GRAFANA_STATUS)"
fi

echo ""
echo "4. Checking Pod Status..."
kubectl get pods -n monitoring -o wide

echo ""
echo "5. All Services:"
kubectl get svc -n monitoring

echo ""
echo "=========================================="
echo "Access URLs:"
echo "=========================================="
echo "Docker Registry: http://192.168.121.50:30500"
echo "Prometheus:      http://192.168.121.50:32090"
echo "Grafana:         http://192.168.121.50:32030"
echo "                 (admin/admin123)"
echo ""
