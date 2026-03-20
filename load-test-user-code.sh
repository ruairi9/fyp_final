#!/bin/bash

echo "=========================================="
echo "Load Testing User Code API"
echo "=========================================="
echo ""

export KUBECONFIG=./k3s.yaml

# Check deployment
echo "Checking deployment status..."
kubectl get pods -n production -l app=user-code-api
echo ""

# Quick test
echo "Testing endpoint..."
curl -s http://192.168.121.30:31400
echo ""
echo ""

# Load test with curl (simple version)
echo "Running simple load test (100 requests)..."
echo "=========================================="

SUCCESS=0
FAILED=0

for i in $(seq 1 100); do
  RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" http://192.168.121.30:31400)
  
  if [ "$RESPONSE" = "200" ]; then
    SUCCESS=$((SUCCESS + 1))
  else
    FAILED=$((FAILED + 1))
  fi
  
  # Progress indicator
  if [ $((i % 10)) -eq 0 ]; then
    echo "Progress: $i/100 requests ($SUCCESS successful, $FAILED failed)"
  fi
done

echo ""
echo "=========================================="
echo "Load Test Results"
echo "=========================================="
echo "Total Requests: 100"
echo "Successful: $SUCCESS"
echo "Failed: $FAILED"
echo "Success Rate: $((SUCCESS * 100 / 100))%"
echo ""

if [ $SUCCESS -eq 100 ]; then
  echo "🎉 All requests successful!"
else
  echo "⚠️  Some requests failed"
fi

# Test load balancing
echo ""
echo "Testing load balancing..."
echo "=========================================="
for i in {1..10}; do
  curl -s http://192.168.121.30:31400 | grep -o '"pod":"[^"]*"' | cut -d'"' -f4
done
