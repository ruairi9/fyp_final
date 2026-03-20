#!/bin/bash

echo "=================================================="
echo "RUNNING TEST - 30 SECOND PIPELINE"
echo "=================================================="
echo ""
echo "Starting long-running test..."
echo "This will take approximately 30 seconds"
echo ""

# Stage 1: Initialize (5 seconds)
echo "Stage 1/6: Initializing..."
for i in {1..5}; do
    echo "  Progress: $i/5 seconds"
    sleep 1
done
echo "✓ Stage 1 complete"
echo ""

# Stage 2: Loading data (5 seconds)
echo "Stage 2/6: Loading test data..."
for i in {1..5}; do
    echo "  Loading: $((i*20))%"
    sleep 1
done
echo "✓ Stage 2 complete"
echo ""

# Stage 3: Processing (5 seconds)
echo "Stage 3/6: Processing data..."
for i in {1..5}; do
    echo "  Processing chunk $i/5"
    sleep 1
done
echo "✓ Stage 3 complete"
echo ""

# Stage 4: Running tests (5 seconds)
echo "Stage 4/6: Running tests..."
for i in {1..5}; do
    echo "  Test suite $i/5"
    sleep 1
done
echo "✓ Stage 4 complete"
echo ""

# Stage 5: Validation (5 seconds)
echo "Stage 5/6: Validating results..."
for i in {1..5}; do
    echo "  Validation step $i/5"
    sleep 1
done
echo "✓ Stage 5 complete"
echo ""

# Stage 6: Cleanup (5 seconds)
echo "Stage 6/6: Cleanup..."
for i in {1..5}; do
    echo "  Cleanup: $((i*20))%"
    sleep 1
done
echo "✓ Stage 6 complete"
echo ""

echo "=================================================="
echo "✅ ALL TESTS PASSED!"
echo "Total execution time: ~30 seconds"
echo "=================================================="
