#!/bin/bash

# Deploy all services to the 5-server K3s cluster

set -e

echo "========================================"
echo "Deploying Services to K3s Cluster"
echo "========================================"
echo ""

# 1. Create Namespaces
echo "Step 1: Creating namespaces..."
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Namespace
metadata:
  name: development
  labels:
    environment: dev
---
apiVersion: v1
kind: Namespace
metadata:
  name: integration
  labels:
    environment: integration
---
apiVersion: v1
kind: Namespace
metadata:
  name: production
  labels:
    environment: prod
---
apiVersion: v1
kind: Namespace
metadata:
  name: load-testing
  labels:
    environment: testing
---
apiVersion: v1
kind: Namespace
metadata:
  name: security-testing
  labels:
    environment: testing
---
apiVersion: v1
kind: Namespace
metadata:
  name: cicd
  labels:
    environment: automation
---
apiVersion: v1
kind: Namespace
metadata:
  name: monitoring
  labels:
    environment: observability
---
apiVersion: v1
kind: Namespace
metadata:
  name: ingress-nginx
EOF

echo "✓ Namespaces created"
sleep 2

# 2. Deploy Jenkins
echo "Step 2: Deploying Jenkins..."
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: jenkins-pvc
  namespace: cicd
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 5Gi
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: jenkins
  namespace: cicd
spec:
  replicas: 1
  selector:
    matchLabels:
      app: jenkins
  template:
    metadata:
      labels:
        app: jenkins
    spec:
      nodeSelector:
        node-role: cicd
      containers:
      - name: jenkins
        image: jenkins/jenkins:lts
        ports:
        - containerPort: 8080
        - containerPort: 50000
        volumeMounts:
        - name: jenkins-home
          mountPath: /var/jenkins_home
        resources:
          requests:
            memory: "512Mi"
            cpu: "500m"
      volumes:
      - name: jenkins-home
        persistentVolumeClaim:
          claimName: jenkins-pvc
---
apiVersion: v1
kind: Service
metadata:
  name: jenkins
  namespace: cicd
spec:
  type: NodePort
  ports:
  - name: http
    port: 8080
    targetPort: 8080
    nodePort: 32080
  - name: agent
    port: 50000
    targetPort: 50000
  selector:
    app: jenkins
EOF

echo "✓ Jenkins deployed"
sleep 2

# 3. Deploy Prometheus
echo "Step 3: Deploying Prometheus..."
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: ServiceAccount
metadata:
  name: prometheus
  namespace: monitoring
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: prometheus
rules:
- apiGroups: [""]
  resources: [nodes, services, endpoints, pods]
  verbs: ["get", "list", "watch"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: prometheus
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: prometheus
subjects:
- kind: ServiceAccount
  name: prometheus
  namespace: monitoring
---
apiVersion: v1
kind: ConfigMap
metadata:
  name: prometheus-config
  namespace: monitoring
data:
  prometheus.yml: |
    global:
      scrape_interval: 15s
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: prometheus
  namespace: monitoring
spec:
  replicas: 1
  selector:
    matchLabels:
      app: prometheus
  template:
    metadata:
      labels:
        app: prometheus
    spec:
      nodeSelector:
        node-role: registry-monitoring
      serviceAccountName: prometheus
      containers:
      - name: prometheus
        image: prom/prometheus:latest
        args:
          - '--config.file=/etc/prometheus/prometheus.yml'
        ports:
        - containerPort: 9090
        volumeMounts:
        - name: config
          mountPath: /etc/prometheus
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
      volumes:
      - name: config
        configMap:
          name: prometheus-config
---
apiVersion: v1
kind: Service
metadata:
  name: prometheus
  namespace: monitoring
spec:
  type: NodePort
  ports:
  - port: 9090
    targetPort: 9090
    nodePort: 32090
  selector:
    app: prometheus
EOF

echo "✓ Prometheus deployed"
sleep 2

# 4. Deploy Grafana
echo "Step 4: Deploying Grafana..."
cat <<EOF | kubectl apply -f -
apiVersion: apps/v1
kind: Deployment
metadata:
  name: grafana
  namespace: monitoring
spec:
  replicas: 1
  selector:
    matchLabels:
      app: grafana
  template:
    metadata:
      labels:
        app: grafana
    spec:
      nodeSelector:
        node-role: registry-monitoring
      containers:
      - name: grafana
        image: grafana/grafana:latest
        ports:
        - containerPort: 3000
        env:
        - name: GF_SECURITY_ADMIN_USER
          value: "admin"
        - name: GF_SECURITY_ADMIN_PASSWORD
          value: "admin123"
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
---
apiVersion: v1
kind: Service
metadata:
  name: grafana
  namespace: monitoring
spec:
  type: NodePort
  ports:
  - port: 3000
    targetPort: 3000
    nodePort: 32030
  selector:
    app: grafana
EOF

echo "✓ Grafana deployed"
sleep 2

# 5. Deploy Loki
echo "Step 5: Deploying Loki..."
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: ConfigMap
metadata:
  name: loki-config
  namespace: monitoring
data:
  loki.yaml: |
    auth_enabled: false
    server:
      http_listen_port: 3100
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: loki
  namespace: monitoring
spec:
  replicas: 1
  selector:
    matchLabels:
      app: loki
  template:
    metadata:
      labels:
        app: loki
    spec:
      nodeSelector:
        node-role: registry-monitoring
      containers:
      - name: loki
        image: grafana/loki:latest
        args:
          - -config.file=/etc/loki/loki.yaml
        ports:
        - containerPort: 3100
        volumeMounts:
        - name: config
          mountPath: /etc/loki
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
      volumes:
      - name: config
        configMap:
          name: loki-config
---
apiVersion: v1
kind: Service
metadata:
  name: loki
  namespace: monitoring
spec:
  ports:
  - port: 3100
    targetPort: 3100
  selector:
    app: loki
EOF

echo "✓ Loki deployed"
echo ""

echo "========================================"
echo "Deployment Complete!"
echo "========================================"
echo ""
echo "Waiting for pods to start..."
sleep 10
echo ""
kubectl get pods --all-namespaces
echo ""
echo "========================================"
echo "Access Points:"
echo "========================================"
echo "Jenkins:    http://192.168.121.40:32080"
echo "Grafana:    http://192.168.121.50:32030 (admin/admin123)"
echo "Prometheus: http://192.168.121.50:32090"
echo ""
echo "View pod placement:"
echo "kubectl get pods --all-namespaces -o wide"
