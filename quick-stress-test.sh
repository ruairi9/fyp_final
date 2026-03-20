#!/bin/bash

echo "Quick Stress Test (1 minute)"
echo "=============================="

export KUBECONFIG=./k3s.yaml

RESULTS_FILE="quick-stress-results-$(date +%Y%m%d_%H%M%S).txt"

TARGET="http://192.168.121.30:31400"

echo "Stress Test Report" > "$RESULTS_FILE"
echo "Date: $(date)" >> "$RESULTS_FILE"
echo "Target: $TARGET" >> "$RESULTS_FILE"
echo "================================" >> "$RESULTS_FILE"
echo "" >> "$RESULTS_FILE"

SUCCESS=0
FAILED=0
TOTAL=500

echo "Sending 500 requests as fast as possible..."

for i in $(seq 1 $TOTAL); do
  RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" $TARGET)
  
  if [ "$RESPONSE" = "200" ]; then
    SUCCESS=$((SUCCESS + 1))
  else
    FAILED=$((FAILED + 1))
  fi
  
  if [ $((i % 50)) -eq 0 ]; then
    echo "Progress: $i/$TOTAL"
  fi
done

SUCCESS_RATE=$((SUCCESS * 100 / TOTAL))

echo ""  >> "$RESULTS_FILE"
echo "Results:" >> "$RESULTS_FILE"
echo "--------" >> "$RESULTS_FILE"
echo "Total Requests: $TOTAL" >> "$RESULTS_FILE"
echo "Successful: $SUCCESS" >> "$RESULTS_FILE"
echo "Failed: $FAILED" >> "$RESULTS_FILE"
echo "Success Rate: ${SUCCESS_RATE}%" >> "$RESULTS_FILE"

cat "$RESULTS_FILE"

echo ""
echo "✓ Results saved to: $RESULTS_FILE"

