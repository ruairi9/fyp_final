#!/bin/bash

echo "=========================================="
echo "STRESS TESTING User Code API"
echo "=========================================="
echo ""

export KUBECONFIG=./k3s.yaml

# Create results directory
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
RESULTS_DIR="stress-test-results-$TIMESTAMP"
mkdir -p "$RESULTS_DIR"

echo "Results will be saved to: $RESULTS_DIR"
echo ""

# Configuration
TARGET_URL="http://192.168.121.30:31400"
REPORT_FILE="$RESULTS_DIR/stress-test-report.txt"

# Start report
cat > "$REPORT_FILE" <<REPORT
==========================================
STRESS TEST REPORT
==========================================
Date: $(date)
Target: $TARGET_URL
Test Duration: 5 minutes
==========================================

REPORT

echo "Phase 1: Baseline Test (10 requests/second)"
echo "=============================================="

# Phase 1: Light load (10 req/sec for 30 seconds)
echo ""
echo "Running Phase 1: Light Load (10 req/sec)..."
PHASE1_SUCCESS=0
PHASE1_FAILED=0
PHASE1_TOTAL_TIME=0

for i in $(seq 1 300); do
  START_TIME=$(date +%s%N)
  RESPONSE=$(curl -s -o /dev/null -w "%{http_code}:%{time_total}" $TARGET_URL)
  END_TIME=$(date +%s%N)
  
  HTTP_CODE=$(echo $RESPONSE | cut -d':' -f1)
  RESPONSE_TIME=$(echo $RESPONSE | cut -d':' -f2)
  
  if [ "$HTTP_CODE" = "200" ]; then
    PHASE1_SUCCESS=$((PHASE1_SUCCESS + 1))
  else
    PHASE1_FAILED=$((PHASE1_FAILED + 1))
  fi
  
  PHASE1_TOTAL_TIME=$(echo "$PHASE1_TOTAL_TIME + $RESPONSE_TIME" | bc)
  
  if [ $((i % 30)) -eq 0 ]; then
    echo "  Progress: $i/300 requests"
  fi
  
  sleep 0.1
done

PHASE1_AVG_TIME=$(echo "scale=3; $PHASE1_TOTAL_TIME / 300" | bc)

echo ""
echo "Phase 1 Results:"
echo "  Total: 300 requests"
echo "  Successful: $PHASE1_SUCCESS"
echo "  Failed: $PHASE1_FAILED"
echo "  Avg Response Time: ${PHASE1_AVG_TIME}s"
echo ""

# Save to report
cat >> "$REPORT_FILE" <<REPORT

PHASE 1: Light Load (10 req/sec)
------------------------------------------
Total Requests:     300
Successful:         $PHASE1_SUCCESS
Failed:             $PHASE1_FAILED
Success Rate:       $((PHASE1_SUCCESS * 100 / 300))%
Avg Response Time:  ${PHASE1_AVG_TIME}s

REPORT

echo "Phase 2: Medium Load (50 requests/second)"
echo "=============================================="

# Phase 2: Medium load (50 req/sec for 1 minute)
echo ""
echo "Running Phase 2: Medium Load (50 req/sec)..."
PHASE2_SUCCESS=0
PHASE2_FAILED=0
PHASE2_TOTAL_TIME=0
PHASE2_MIN_TIME=999
PHASE2_MAX_TIME=0

for i in $(seq 1 3000); do
  START=$(date +%s%N)
  RESPONSE=$(curl -s -o /dev/null -w "%{http_code}:%{time_total}" $TARGET_URL 2>/dev/null)
  
  HTTP_CODE=$(echo $RESPONSE | cut -d':' -f1)
  RESPONSE_TIME=$(echo $RESPONSE | cut -d':' -f2)
  
  if [ "$HTTP_CODE" = "200" ]; then
    PHASE2_SUCCESS=$((PHASE2_SUCCESS + 1))
  else
    PHASE2_FAILED=$((PHASE2_FAILED + 1))
  fi
  
  PHASE2_TOTAL_TIME=$(echo "$PHASE2_TOTAL_TIME + $RESPONSE_TIME" | bc)
  
  # Track min/max
  if (( $(echo "$RESPONSE_TIME < $PHASE2_MIN_TIME" | bc -l) )); then
    PHASE2_MIN_TIME=$RESPONSE_TIME
  fi
  if (( $(echo "$RESPONSE_TIME > $PHASE2_MAX_TIME" | bc -l) )); then
    PHASE2_MAX_TIME=$RESPONSE_TIME
  fi
  
  if [ $((i % 300)) -eq 0 ]; then
    echo "  Progress: $i/3000 requests"
  fi
  
  sleep 0.02
done

PHASE2_AVG_TIME=$(echo "scale=3; $PHASE2_TOTAL_TIME / 3000" | bc)

echo ""
echo "Phase 2 Results:"
echo "  Total: 3000 requests"
echo "  Successful: $PHASE2_SUCCESS"
echo "  Failed: $PHASE2_FAILED"
echo "  Avg Response Time: ${PHASE2_AVG_TIME}s"
echo "  Min Response Time: ${PHASE2_MIN_TIME}s"
echo "  Max Response Time: ${PHASE2_MAX_TIME}s"
echo ""

cat >> "$REPORT_FILE" <<REPORT

PHASE 2: Medium Load (50 req/sec)
------------------------------------------
Total Requests:     3000
Successful:         $PHASE2_SUCCESS
Failed:             $PHASE2_FAILED
Success Rate:       $((PHASE2_SUCCESS * 100 / 3000))%
Avg Response Time:  ${PHASE2_AVG_TIME}s
Min Response Time:  ${PHASE2_MIN_TIME}s
Max Response Time:  ${PHASE2_MAX_TIME}s

REPORT

echo "Phase 3: Heavy Load (100 requests/second)"
echo "=============================================="

# Phase 3: Heavy load (concurrent requests)
echo ""
echo "Running Phase 3: Heavy Load (100 concurrent)..."
PHASE3_SUCCESS=0
PHASE3_FAILED=0

for batch in $(seq 1 50); do
  # Launch 100 concurrent requests
  for i in $(seq 1 100); do
    (
      RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" $TARGET_URL 2>/dev/null)
      if [ "$RESPONSE" = "200" ]; then
        echo "SUCCESS" >> "$RESULTS_DIR/phase3_results.tmp"
      else
        echo "FAILED" >> "$RESULTS_DIR/phase3_results.tmp"
      fi
    ) &
  done
  
  wait
  echo "  Batch $batch/50 complete ($(($batch * 100)) requests)"
done

PHASE3_SUCCESS=$(grep -c "SUCCESS" "$RESULTS_DIR/phase3_results.tmp" 2>/dev/null || echo 0)
PHASE3_FAILED=$(grep -c "FAILED" "$RESULTS_DIR/phase3_results.tmp" 2>/dev/null || echo 0)

echo ""
echo "Phase 3 Results:"
echo "  Total: 5000 requests (100 concurrent)"
echo "  Successful: $PHASE3_SUCCESS"
echo "  Failed: $PHASE3_FAILED"
echo ""

cat >> "$REPORT_FILE" <<REPORT

PHASE 3: Heavy Load (100 concurrent)
------------------------------------------
Total Requests:     5000
Successful:         $PHASE3_SUCCESS
Failed:             $PHASE3_FAILED
Success Rate:       $((PHASE3_SUCCESS * 100 / 5000))%

REPORT

# Check pod status during stress
echo "Checking Pod Status During Stress..."
kubectl get pods -n production -l app=user-code-api -o wide > "$RESULTS_DIR/pod-status.txt"

# Get pod resource usage
kubectl top pods -n production -l app=user-code-api 2>/dev/null > "$RESULTS_DIR/resource-usage.txt" || echo "Metrics not available"

# Final Summary
TOTAL_REQUESTS=$((300 + 3000 + 5000))
TOTAL_SUCCESS=$((PHASE1_SUCCESS + PHASE2_SUCCESS + PHASE3_SUCCESS))
TOTAL_FAILED=$((PHASE1_FAILED + PHASE2_FAILED + PHASE3_FAILED))
SUCCESS_RATE=$((TOTAL_SUCCESS * 100 / TOTAL_REQUESTS))

cat >> "$REPORT_FILE" <<REPORT

==========================================
OVERALL SUMMARY
==========================================
Total Requests:     $TOTAL_REQUESTS
Successful:         $TOTAL_SUCCESS
Failed:             $TOTAL_FAILED
Overall Success Rate: ${SUCCESS_RATE}%

Phase Breakdown:
- Phase 1 (Light):  $PHASE1_SUCCESS/$((300)) = $((PHASE1_SUCCESS * 100 / 300))%
- Phase 2 (Medium): $PHASE2_SUCCESS/$((3000)) = $((PHASE2_SUCCESS * 100 / 3000))%
- Phase 3 (Heavy):  $PHASE3_SUCCESS/$((5000)) = $((PHASE3_SUCCESS * 100 / 5000))%

PERFORMANCE METRICS:
- Average Response Time: ${PHASE2_AVG_TIME}s
- Fastest Response: ${PHASE2_MIN_TIME}s
- Slowest Response: ${PHASE2_MAX_TIME}s

CONCLUSION:
REPORT

if [ $SUCCESS_RATE -ge 95 ]; then
  echo "✅ EXCELLENT - System handled stress well" >> "$REPORT_FILE"
elif [ $SUCCESS_RATE -ge 80 ]; then
  echo "✓ GOOD - System stable under load" >> "$REPORT_FILE"
elif [ $SUCCESS_RATE -ge 60 ]; then
  echo "⚠️  FAIR - System struggled under heavy load" >> "$REPORT_FILE"
else
  echo "❌ POOR - System failed under stress" >> "$REPORT_FILE"
fi

echo "" >> "$REPORT_FILE"
echo "Test completed: $(date)" >> "$REPORT_FILE"
echo "===========================================" >> "$REPORT_FILE"

# Display final report
echo ""
echo "=========================================="
echo "STRESS TEST COMPLETE!"
echo "=========================================="
cat "$REPORT_FILE"

echo ""
echo "📁 Results saved to: $RESULTS_DIR/"
echo ""
echo "Files created:"
ls -lh "$RESULTS_DIR/"

# Cleanup temp files
rm -f "$RESULTS_DIR/phase3_results.tmp"

