# Complete Pipeline Testing Guide

This guide will walk you through testing your complete CI/CD pipeline with a microservice.

## What We'll Test:

1. Deploy microservice to Development
2. Run tests in Development
3. Promote to Production
4. Run load tests on Production
5. Run security tests on Production
6. Monitor everything in Grafana

## Step 1: Deploy Microservice to Development

```bash
cd ~/fyp-cluster
export KUBECONFIG=./k3s.yaml

# Deploy a simple Python microservice to development
cat <<EOF | kubectl apply -f -
apiVersion: apps/v1
kind: Deployment
metadata:
  name: hello-api
  namespace: development
spec:
  replicas: 2
  selector:
    matchLabels:
      app: hello-api
      version: v1
  template:
    metadata:
      labels:
        app: hello-api
        version: v1
    spec:
      nodeSelector:
        node-role: development
      containers:
      - name: api
        image: hashicorp/http-echo
        args:
        - "-text=Hello from Development! Version: 1.0.0 | Pod: \$(HOSTNAME)"
        - "-listen=:8080"
        env:
        - name: HOSTNAME
          valueFrom:
            fieldRef:
              fieldPath: metadata.name
        ports:
        - containerPort: 8080
        readinessProbe:
          httpGet:
            path: /
            port: 8080
          initialDelaySeconds: 5
          periodSeconds: 5
        livenessProbe:
          httpGet:
            path: /
            port: 8080
          initialDelaySeconds: 10
          periodSeconds: 10
---
apiVersion: v1
kind: Service
metadata:
  name: hello-api
  namespace: development
spec:
  type: NodePort
  selector:
    app: hello-api
  ports:
  - port: 8080
    targetPort: 8080
    nodePort: 30800
EOF

# Wait for deployment
kubectl rollout status deployment/hello-api -n development

# Test it
echo "Development API URL: http://192.168.121.20:30800"
curl http://192.168.121.20:30800
```

## Step 2: Run Integration Tests

```bash
# Create an integration test job
cat <<EOF | kubectl apply -f -
apiVersion: batch/v1
kind: Job
metadata:
  name: integration-test
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
          for i in 1 2 3 4 5; do
            echo "Test \$i: Testing development API"
            response=\$(curl -s http://hello-api.development.svc.cluster.local:8080)
            if echo "\$response" | grep -q "Hello"; then
              echo "✓ Test \$i passed"
            else
              echo "✗ Test \$i failed"
              exit 1
            fi
            sleep 1
          done
          echo "All integration tests passed!"
      restartPolicy: Never
  backoffLimit: 2
EOF

# Watch the test
kubectl wait --for=condition=complete job/integration-test -n integration --timeout=60s
kubectl logs -n integration job/integration-test
```

## Step 3: Promote to Production

```bash
# After tests pass, deploy to production
cat <<EOF | kubectl apply -f -
apiVersion: apps/v1
kind: Deployment
metadata:
  name: hello-api
  namespace: production
spec:
  replicas: 3
  selector:
    matchLabels:
      app: hello-api
      version: v1
  template:
    metadata:
      labels:
        app: hello-api
        version: v1
      annotations:
        prometheus.io/scrape: "true"
        prometheus.io/port: "8080"
    spec:
      nodeSelector:
        node-role: production
      containers:
      - name: api
        image: hashicorp/http-echo
        args:
        - "-text=Hello from Production! Version: 1.0.0 | Pod: \$(HOSTNAME)"
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
        readinessProbe:
          httpGet:
            path: /
            port: 8080
          initialDelaySeconds: 5
          periodSeconds: 5
        livenessProbe:
          httpGet:
            path: /
            port: 8080
          initialDelaySeconds: 10
          periodSeconds: 10
---
apiVersion: v1
kind: Service
metadata:
  name: hello-api
  namespace: production
spec:
  type: NodePort
  selector:
    app: hello-api
  ports:
  - port: 8080
    targetPort: 8080
    nodePort: 31800
EOF

# Wait for production deployment
kubectl rollout status deployment/hello-api -n production

# Test production
echo "Production API URL: http://192.168.121.30:31800"
curl http://192.168.121.30:31800
```

## Step 4: Run Load Tests on Production

```bash
# Update k6 load test to target our new API
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: ConfigMap
metadata:
  name: k6-hello-api-test
  namespace: load-testing
data:
  test.js: |
    import http from 'k6/http';
    import { check, sleep } from 'k6';
    
    export let options = {
      stages: [
        { duration: '30s', target: 10 },
        { duration: '1m', target: 20 },
        { duration: '30s', target: 0 },
      ],
      thresholds: {
        http_req_duration: ['p(95)<500'],
        http_req_failed: ['rate<0.01'],
      },
    };
    
    export default function () {
      let res = http.get('http://hello-api.production.svc.cluster.local:8080');
      
      check(res, {
        'status is 200': (r) => r.status === 200,
        'response contains Hello': (r) => r.body.includes('Hello'),
      });
      
      sleep(1);
    }
EOF

# Run the load test
kubectl exec -n load-testing $(kubectl get pods -n load-testing -o jsonpath='{.items[0].metadata.name}') -- k6 run /scripts/test.js
```

## Step 5: Run Security Scan

```bash
# Run security scan on production API
kubectl exec -n security-testing $(kubectl get pods -n security-testing -o jsonpath='{.items[0].metadata.name}') -- curl -v http://hello-api.production.svc.cluster.local:8080

# Check security scan logs
kubectl logs -n security-testing -l app=security-scanner --tail=30
```

## Step 6: Verify Complete Pipeline

```bash
# Check all deployments
echo "=== Development ==="
kubectl get pods -n development -o wide | grep hello-api

echo ""
echo "=== Production ==="
kubectl get pods -n production -o wide | grep hello-api

echo ""
echo "=== Integration Tests ==="
kubectl get jobs -n integration

echo ""
echo "=== Load Tests ==="
kubectl get pods -n load-testing -o wide

echo ""
echo "=== Security Tests ==="
kubectl get pods -n security-testing -o wide
```

## Step 7: Test Load Balancing

```bash
# Make multiple requests to see different pods respond
echo "Testing load balancing in development:"
for i in {1..5}; do
  echo "Request $i:"
  curl http://192.168.121.20:30800
  echo ""
done

echo ""
echo "Testing load balancing in production:"
for i in {1..5}; do
  echo "Request $i:"
  curl http://192.168.121.30:31800
  echo ""
done
```

## Step 8: Simulate Code Update (Version 2)

```bash
# Update to version 2.0.0 in development
kubectl patch deployment hello-api -n development -p '{"spec":{"template":{"spec":{"containers":[{"name":"api","args":["-text=Hello from Development! Version: 2.0.0 | Pod: $(HOSTNAME)","-listen=:8080"]}]}}}}'

# Watch rolling update
kubectl rollout status deployment/hello-api -n development

# Test new version
curl http://192.168.121.20:30800

# After testing, promote to production
kubectl patch deployment hello-api -n production -p '{"spec":{"template":{"spec":{"containers":[{"name":"api","args":["-text=Hello from Production! Version: 2.0.0 | Pod: $(HOSTNAME)","-listen=:8080"]}]}}}}'

# Watch production update
kubectl rollout status deployment/hello-api -n production

# Test production version
curl http://192.168.121.30:31800
```

## Step 9: Monitor in Grafana

1. Open Grafana: http://192.168.121.50:32030
2. Login: admin / admin123
3. Go to Explore
4. Select Prometheus data source
5. Query: `rate(http_requests_total[5m])`
6. See your API requests in real-time

## Step 10: View Logs in Loki

1. In Grafana, go to Explore
2. Select Loki data source
3. Query: `{namespace="production", app="hello-api"}`
4. See logs from your production pods

## Complete Pipeline Flow Diagram

```
┌─────────────────────────────────────────────────────────┐
│                    Pipeline Flow                         │
└─────────────────────────────────────────────────────────┘

1. Deploy to Development (worker-dev-integration)
   ↓
2. Run Integration Tests (worker-dev-integration)
   ↓
3. ✓ Tests Pass
   ↓
4. Deploy to Production (worker-production)
   ↓
5. Run Load Tests (worker-production)
   ↓
6. Run Security Tests (worker-production)
   ↓
7. ✓ All Tests Pass
   ↓
8. Monitor in Grafana (worker-registry-monitoring)
```

## Success Criteria

Your pipeline is working if:
- ✅ Microservice deploys to development
- ✅ Integration tests pass
- ✅ Microservice deploys to production
- ✅ Load tests complete successfully
- ✅ Security scans show no critical issues
- ✅ Different pods respond (load balancing works)
- ✅ Rolling updates work without downtime
- ✅ Monitoring shows metrics in Grafana

## What This Demonstrates for Your FYP

1. **CI/CD Pipeline**: Automated deployment from dev → prod
2. **Environment Isolation**: Dev and prod physically separated
3. **Automated Testing**: Integration, load, and security tests
4. **High Availability**: Multiple replicas, load balancing
5. **Zero-Downtime Deployments**: Rolling updates
6. **Monitoring & Observability**: Prometheus + Grafana + Loki
7. **5-Server Architecture**: Each workload on dedicated server
