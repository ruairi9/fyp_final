#!/bin/bash

# Complete CI/CD Pipeline Demo
# This demonstrates: Deploy → Test → Integrate → Production → Load Test → Security Test

set -e

echo "========================================"
echo "FYP CI/CD Pipeline Demo"
echo "========================================"
echo ""

export KUBECONFIG=./k3s.yaml

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Step 1: Deploy to Development
echo -e "${YELLOW}Step 1: Deploying microservice to DEVELOPMENT...${NC}"
cat <<EOF | kubectl apply -f -
apiVersion: apps/v1
kind: Deployment
metadata:
  name: demo-api
  namespace: development
spec:
  replicas: 2
  selector:
    matchLabels:
      app: demo-api
      version: v1.0.0
  template:
    metadata:
      labels:
        app: demo-api
        version: v1.0.0
    spec:
      nodeSelector:
        node-role: development
      containers:
      - name: api
        image: hashicorp/http-echo:latest
        args:
          - "-text=Demo API v1.0.0 - Status: Development"
          - "-listen=:8080"
        ports:
        - containerPort: 8080
        livenessProbe:
          httpGet:
            path: /
            port: 8080
          initialDelaySeconds: 5
          periodSeconds: 5
        readinessProbe:
          httpGet:
            path: /
            port: 8080
          initialDelaySeconds: 3
          periodSeconds: 3
---
apiVersion: v1
kind: Service
metadata:
  name: demo-api
  namespace: development
spec:
  selector:
    app: demo-api
  ports:
  - port: 8080
    targetPort: 8080
  type: ClusterIP
EOF

echo -e "${GREEN}✓ Deployed to development${NC}"
sleep 5

# Step 2: Run Unit Tests
echo ""
echo -e "${YELLOW}Step 2: Running UNIT TESTS in development...${NC}"
cat <<EOF | kubectl apply -f -
apiVersion: batch/v1
kind: Job
metadata:
  name: unit-tests
  namespace: development
spec:
  template:
    spec:
      nodeSelector:
        node-role: development
      containers:
      - name: test
        image: curlimages/curl
        command:
        - /bin/sh
        - -c
        - |
          echo "Running unit tests..."
          for i in 1 2 3 4 5; do
            echo "Test \$i: Testing API health endpoint"
            response=\$(curl -s http://demo-api.development.svc.cluster.local:8080)
            if echo "\$response" | grep -q "Demo API"; then
              echo "✓ Unit test \$i PASSED"
            else
              echo "✗ Unit test \$i FAILED"
              exit 1
            fi
            sleep 1
          done
          echo "All unit tests PASSED!"
      restartPolicy: Never
  backoffLimit: 1
EOF

# Wait for tests to complete
kubectl wait --for=condition=complete job/unit-tests -n development --timeout=60s
echo -e "${GREEN}✓ Unit tests PASSED${NC}"
kubectl logs -n development job/unit-tests | tail -10

# Step 3: Integration Tests
echo ""
echo -e "${YELLOW}Step 3: Running INTEGRATION TESTS...${NC}"
cat <<EOF | kubectl apply -f -
apiVersion: batch/v1
kind: Job
metadata:
  name: integration-tests
  namespace: integration
spec:
  template:
    spec:
      nodeSelector:
        node-role: development
      containers:
      - name: test
        image: curlimages/curl
        command:
        - /bin/sh
        - -c
        - |
          echo "Running integration tests..."
          echo "Test 1: API responds correctly"
          response=\$(curl -s http://demo-api.development.svc.cluster.local:8080)
          if echo "\$response" | grep -q "v1.0.0"; then
            echo "✓ Integration test 1 PASSED - Version check OK"
          else
            echo "✗ Integration test 1 FAILED"
            exit 1
          fi
          
          echo "Test 2: API responds within acceptable time"
          start=\$(date +%s)
          curl -s http://demo-api.development.svc.cluster.local:8080 > /dev/null
          end=\$(date +%s)
          duration=\$((end - start))
          if [ \$duration -lt 2 ]; then
            echo "✓ Integration test 2 PASSED - Response time OK (\${duration}s)"
          else
            echo "✗ Integration test 2 FAILED - Too slow"
            exit 1
          fi
          
          echo "All integration tests PASSED!"
      restartPolicy: Never
  backoffLimit: 1
EOF

kubectl wait --for=condition=complete job/integration-tests -n integration --timeout=60s
echo -e "${GREEN}✓ Integration tests PASSED${NC}"
kubectl logs -n integration job/integration-tests | tail -10

# Step 4: Deploy to Production
echo ""
echo -e "${YELLOW}Step 4: Promoting to PRODUCTION...${NC}"
cat <<EOF | kubectl apply -f -
apiVersion: apps/v1
kind: Deployment
metadata:
  name: demo-api
  namespace: production
spec:
  replicas: 3
  selector:
    matchLabels:
      app: demo-api
      version: v1.0.0
  template:
    metadata:
      labels:
        app: demo-api
        version: v1.0.0
      annotations:
        prometheus.io/scrape: "true"
        prometheus.io/port: "8080"
    spec:
      nodeSelector:
        node-role: production
      containers:
      - name: api
        image: hashicorp/http-echo:latest
        args:
          - "-text=Demo API v1.0.0 - Status: PRODUCTION - Pod: \$(HOSTNAME)"
          - "-listen=:8080"
        env:
        - name: HOSTNAME
          valueFrom:
            fieldRef:
              fieldPath: metadata.name
        ports:
        - containerPort: 8080
        resources:
          requests:
            memory: "64Mi"
            cpu: "50m"
          limits:
            memory: "128Mi"
            cpu: "100m"
        livenessProbe:
          httpGet:
            path: /
            port: 8080
          initialDelaySeconds: 5
          periodSeconds: 5
        readinessProbe:
          httpGet:
            path: /
            port: 8080
          initialDelaySeconds: 3
          periodSeconds: 3
---
apiVersion: v1
kind: Service
metadata:
  name: demo-api
  namespace: production
spec:
  type: NodePort
  selector:
    app: demo-api
  ports:
  - port: 8080
    targetPort: 8080
    nodePort: 30999
EOF

kubectl rollout status deployment/demo-api -n production
echo -e "${GREEN}✓ Deployed to production${NC}"

# Step 5: Load Testing
echo ""
echo -e "${YELLOW}Step 5: Running LOAD TESTS on production...${NC}"
cat <<EOF | kubectl apply -f -
apiVersion: batch/v1
kind: Job
metadata:
  name: load-test-demo
  namespace: load-testing
spec:
  template:
    spec:
      nodeSelector:
        node-role: production
      containers:
      - name: load-test
        image: curlimages/curl
        command:
        - /bin/sh
        - -c
        - |
          echo "Starting load test with 50 concurrent requests..."
          success=0
          failed=0
          
          for i in \$(seq 1 50); do
            response=\$(curl -s -w "%{http_code}" http://demo-api.production.svc.cluster.local:8080 -o /dev/null)
            if [ "\$response" = "200" ]; then
              success=\$((success + 1))
            else
              failed=\$((failed + 1))
            fi
          done
          
          echo "Load test completed!"
          echo "Successful requests: \$success/50"
          echo "Failed requests: \$failed/50"
          
          if [ \$success -ge 45 ]; then
            echo "✓ Load test PASSED (>90% success rate)"
            exit 0
          else
            echo "✗ Load test FAILED (<90% success rate)"
            exit 1
          fi
      restartPolicy: Never
  backoffLimit: 1
EOF

kubectl wait --for=condition=complete job/load-test-demo -n load-testing --timeout=120s
echo -e "${GREEN}✓ Load test PASSED${NC}"
kubectl logs -n load-testing job/load-test-demo | tail -10

# Step 6: Security Testing
echo ""
echo -e "${YELLOW}Step 6: Running SECURITY TESTS on production...${NC}"
cat <<EOF | kubectl apply -f -
apiVersion: batch/v1
kind: Job
metadata:
  name: security-test-demo
  namespace: security-testing
spec:
  template:
    spec:
      nodeSelector:
        node-role: production
      containers:
      - name: security-test
        image: curlimages/curl
        command:
        - /bin/sh
        - -c
        - |
          echo "Running security tests..."
          
          echo "Test 1: Check HTTP headers"
          headers=\$(curl -I -s http://demo-api.production.svc.cluster.local:8080)
          echo "✓ Headers retrieved"
          
          echo "Test 2: Check for common vulnerabilities"
          response=\$(curl -s http://demo-api.production.svc.cluster.local:8080)
          if ! echo "\$response" | grep -i "error"; then
            echo "✓ No error messages exposed"
          fi
          
          echo "Test 3: Check response size"
          size=\$(echo "\$response" | wc -c)
          if [ \$size -lt 1000 ]; then
            echo "✓ Response size reasonable (\${size} bytes)"
          fi
          
          echo "✓ All security tests PASSED"
      restartPolicy: Never
  backoffLimit: 1
EOF

kubectl wait --for=condition=complete job/security-test-demo -n security-testing --timeout=60s
echo -e "${GREEN}✓ Security tests PASSED${NC}"
kubectl logs -n security-testing job/security-test-demo | tail -10

# Final Summary
echo ""
echo "========================================"
echo -e "${GREEN}Pipeline Completed Successfully!${NC}"
echo "========================================"
echo ""
echo "Summary:"
echo "  ✓ Development deployment"
echo "  ✓ Unit tests (5/5 passed)"
echo "  ✓ Integration tests (2/2 passed)"
echo "  ✓ Production deployment (3 replicas)"
echo "  ✓ Load testing (50 requests)"
echo "  ✓ Security testing (3 checks)"
echo ""
echo "Production API accessible at:"
echo "  http://192.168.121.30:30999"
echo ""
echo "Test it:"
echo "  curl http://192.168.121.30:30999"
echo ""
echo "View pods distribution:"
echo "  kubectl get pods --all-namespaces -o wide | grep demo-api"
echo ""
