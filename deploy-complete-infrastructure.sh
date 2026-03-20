#!/bin/bash

# Complete FYP Infrastructure Deployment
# Deploys all required components for 5-server architecture

set -e

echo "========================================"
echo "Deploying Complete FYP Infrastructure"
echo "========================================"
echo ""

export KUBECONFIG=./k3s.yaml

# 1. Deploy Docker Registry
echo "Step 1: Deploying Docker Registry..."
cat <<EOF | kubectl apply -f -
apiVersion: apps/v1
kind: Deployment
metadata:
  name: docker-registry
  namespace: monitoring
spec:
  replicas: 1
  selector:
    matchLabels:
      app: docker-registry
  template:
    metadata:
      labels:
        app: docker-registry
    spec:
      nodeSelector:
        node-role: registry-monitoring
      containers:
      - name: registry
        image: registry:2
        ports:
        - containerPort: 5000
        env:
        - name: REGISTRY_STORAGE_FILESYSTEM_ROOTDIRECTORY
          value: /var/lib/registry
        - name: REGISTRY_STORAGE_DELETE_ENABLED
          value: "true"
        volumeMounts:
        - name: registry-storage
          mountPath: /var/lib/registry
        resources:
          requests:
            memory: "256Mi"
            cpu: "200m"
      volumes:
      - name: registry-storage
        emptyDir: {}
---
apiVersion: v1
kind: Service
metadata:
  name: docker-registry
  namespace: monitoring
spec:
  type: NodePort
  selector:
    app: docker-registry
  ports:
  - port: 5000
    targetPort: 5000
    nodePort: 30500
    name: registry
EOF

echo "✓ Docker Registry deployed"
echo ""

# 2. Deploy Load Testing Tool (k6)
echo "Step 2: Deploying Load Testing Tool..."
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: ConfigMap
metadata:
  name: k6-script
  namespace: load-testing
data:
  script.js: |
    import http from 'k6/http';
    import { check, sleep } from 'k6';

    export let options = {
      stages: [
        { duration: '30s', target: 20 },
        { duration: '1m', target: 50 },
        { duration: '30s', target: 0 },
      ],
    };

    export default function () {
      let res = http.get('http://fyp-microservice.production.svc.cluster.local:5000');
      check(res, { 'status was 200': (r) => r.status == 200 });
      sleep(1);
    }
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: k6-loadtest
  namespace: load-testing
spec:
  replicas: 1
  selector:
    matchLabels:
      app: k6-loadtest
  template:
    metadata:
      labels:
        app: k6-loadtest
    spec:
      nodeSelector:
        node-role: production
      containers:
      - name: k6
        image: grafana/k6:latest
        command: ["/bin/sh"]
        args: ["-c", "while true; do sleep 3600; done"]
        volumeMounts:
        - name: k6-script
          mountPath: /scripts
      volumes:
      - name: k6-script
        configMap:
          name: k6-script
EOF

echo "✓ Load Testing deployed"
echo ""

# 3. Deploy Security Testing Tool (OWASP ZAP)
echo "Step 3: Deploying Security Testing Tool..."
cat <<EOF | kubectl apply -f -
apiVersion: apps/v1
kind: Deployment
metadata:
  name: zap-security-test
  namespace: security-testing
spec:
  replicas: 1
  selector:
    matchLabels:
      app: zap-security-test
  template:
    metadata:
      labels:
        app: zap-security-test
    spec:
      nodeSelector:
        node-role: production
      containers:
      - name: zap
        image: owasp/zap2docker-stable
        command: ["/bin/sh"]
        args: ["-c", "while true; do sleep 3600; done"]
        resources:
          requests:
            memory: "512Mi"
            cpu: "250m"
---
apiVersion: v1
kind: Service
metadata:
  name: zap-security-test
  namespace: security-testing
spec:
  type: NodePort
  selector:
    app: zap-security-test
  ports:
  - port: 8080
    targetPort: 8080
    nodePort: 30600
EOF

echo "✓ Security Testing deployed"
echo ""

# 4. Verify Namespace Isolation
echo "Step 4: Verifying namespace isolation..."
cat <<EOF | kubectl apply -f -
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: isolate-development
  namespace: development
spec:
  podSelector: {}
  policyTypes:
  - Ingress
  - Egress
  ingress:
  - from:
    - namespaceSelector:
        matchLabels:
          environment: dev
  egress:
  - to:
    - namespaceSelector: {}
---
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: isolate-integration
  namespace: integration
spec:
  podSelector: {}
  policyTypes:
  - Ingress
  - Egress
  ingress:
  - from:
    - namespaceSelector:
        matchLabels:
          environment: integration
  egress:
  - to:
    - namespaceSelector: {}
EOF

echo "✓ Namespace isolation configured"
echo ""

echo "========================================"
echo "Deployment Complete!"
echo "========================================"
echo ""
echo "Infrastructure Summary:"
echo "========================================"
echo ""
echo "Control Plane (192.168.121.10):"
echo "  - K3s API Server"
echo "  - etcd Database"
echo "  - Scheduler"
echo "  - Controller Manager"
echo ""
echo "Worker: Development & Integration (192.168.121.20):"
echo "  - Namespace: development (isolated)"
echo "  - Namespace: integration (isolated)"
echo ""
echo "Worker: Production (192.168.121.30):"
echo "  - Production workloads"
echo "  - Load testing (k6)"
echo "  - Security testing (OWASP ZAP)"
echo ""
echo "Worker: CI/CD (192.168.121.40):"
echo "  - Jenkins: http://192.168.121.40:32080"
echo ""
echo "Worker: Registry & Monitoring (192.168.121.50):"
echo "  - Docker Registry: http://192.168.121.50:30500"
echo "  - Prometheus: http://192.168.121.50:32090"
echo "  - Grafana: http://192.168.121.50:32030"
echo "  - Loki (logs)"
echo ""
echo "========================================"
echo ""
echo "Check deployment status:"
echo "  kubectl get pods --all-namespaces -o wide"
echo ""
