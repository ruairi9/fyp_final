#!/bin/bash

echo "=========================================="
echo "Demo: Pipeline with Monitoring"
echo "=========================================="
echo ""

export KUBECONFIG=./k3s.yaml

echo "Step 1: Check Monitoring Stack"
echo "-------------------------------"
kubectl get pods -n monitoring | grep Running
echo ""

echo "Step 2: Jenkins Pipeline URL"
echo "----------------------------"
echo "Jenkins: http://192.168.121.40:32080"
echo "Go to: universal-microservice-pipeline"
echo "Click: Build with Parameters"
echo ""

echo "Step 3: While Pipeline Runs, View Logs"
echo "--------------------------------------"
echo "Grafana: http://192.168.121.50:32030"
echo "Navigate to: Explore → Loki"
echo "Query: {namespace=\"cicd\"} |= \"METRIC\""
echo ""

echo "Step 4: See Real-Time Metrics"
echo "-----------------------------"
echo "In Grafana Explore:"
echo "  - Filter by 'Pipeline Started'"
echo "  - Filter by 'METRIC:'"
echo "  - Filter by 'LOG:'"
echo ""

echo "What You'll See:"
echo "✅ Build duration metrics"
echo "✅ Test results (passed/failed)"
echo "✅ Deployment status"
echo "✅ Health check scores"
echo "✅ Complete log trail"
echo ""

echo "=========================================="
echo "📊 Monitoring: Visualizes performance trends"
echo "🔍 Detection: Shows failures immediately"  
echo "📝 Logging: Complete troubleshooting records"
echo "=========================================="

