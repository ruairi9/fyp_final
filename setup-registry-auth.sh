#!/bin/bash
# ============================================
# SDOS Registry Authentication Setup (K3s)
# Run from host: bash setup-registry-auth.sh
# ============================================

set -e

VAGRANT_DIR="$HOME/fyp-cluster"
export KUBECONFIG="$HOME/fyp-cluster/k3s.yaml"

echo "============================================"
echo " SDOS Registry Authentication Setup (K3s)"
echo "============================================"

cd $VAGRANT_DIR

echo ""
echo "Step 1 — Installing htpasswd on worker-monitoring..."
vagrant ssh worker-monitoring -c "sudo apt-get install -y apache2-utils -q" 2>/dev/null
echo "Done"

echo ""
echo "Step 2 — Generating htpasswd credentials..."
vagrant ssh worker-monitoring -c "
    htpasswd -Bbn admin passadmin > /tmp/htpasswd
    htpasswd -Bbn ruairi 1234 >> /tmp/htpasswd
    echo 'Credentials generated:'
    cat /tmp/htpasswd
" 2>/dev/null

echo ""
echo "Step 3 — Copying htpasswd file to host..."
vagrant ssh worker-monitoring -c "cat /tmp/htpasswd" 2>/dev/null > /tmp/registry-htpasswd
echo "htpasswd file saved"
cat /tmp/registry-htpasswd

echo ""
echo "Step 4 — Creating Kubernetes secret with htpasswd..."
kubectl delete secret registry-auth -n monitoring 2>/dev/null || true
kubectl create secret generic registry-auth \
    --from-file=htpasswd=/tmp/registry-htpasswd \
    -n monitoring
echo "Secret created"

echo ""
echo "Step 5 — Patching registry deployment to enable auth..."
kubectl patch deployment docker-registry -n monitoring --type=json -p='[
  {
    "op": "add",
    "path": "/spec/template/spec/containers/0/env/-",
    "value": {
      "name": "REGISTRY_AUTH",
      "value": "htpasswd"
    }
  },
  {
    "op": "add",
    "path": "/spec/template/spec/containers/0/env/-",
    "value": {
      "name": "REGISTRY_AUTH_HTPASSWD_REALM",
      "value": "SDOS Registry"
    }
  },
  {
    "op": "add",
    "path": "/spec/template/spec/containers/0/env/-",
    "value": {
      "name": "REGISTRY_AUTH_HTPASSWD_PATH",
      "value": "/auth/htpasswd"
    }
  },
  {
    "op": "add",
    "path": "/spec/template/spec/volumes/-",
    "value": {
      "name": "registry-auth",
      "secret": {
        "secretName": "registry-auth"
      }
    }
  },
  {
    "op": "add",
    "path": "/spec/template/spec/containers/0/volumeMounts/-",
    "value": {
      "name": "registry-auth",
      "mountPath": "/auth",
      "readOnly": true
    }
  }
]'
echo "Deployment patched"

echo ""
echo "Step 6 — Waiting for registry pod to restart..."
kubectl rollout status deployment/docker-registry -n monitoring --timeout=60s
echo "Registry restarted"

echo ""
echo "Step 7 — Testing authentication..."
sleep 3
REGISTRY_IP="192.168.121.50"

echo "Testing unauthenticated access (should fail with 401):"
curl -s -o /dev/null -w "HTTP status: %{http_code}\n" http://$REGISTRY_IP:5000/v2/

echo ""
echo "Testing admin credentials (should return 200):"
curl -s -o /dev/null -w "HTTP status: %{http_code}\n" -u admin:passadmin http://$REGISTRY_IP:5000/v2/

echo ""
echo "Testing ruairi credentials (should return 200):"
curl -s -o /dev/null -w "HTTP status: %{http_code}\n" -u ruairi:1234 http://$REGISTRY_IP:5000/v2/

echo ""
echo "============================================"
echo " Setup complete!"
echo "============================================"
echo ""
echo " Registry:  192.168.121.50:5000"
echo " Auth:      htpasswd (bcrypt)"
echo ""
echo " Accounts:"
echo "   admin  / passadmin"
echo "   ruairi / 1234"
echo ""
echo " To login from any VM:"
echo "   docker login 192.168.121.50:5000"
echo "   Username: admin"
echo "   Password: passadmin"
echo ""
echo " To push an image:"
echo "   docker tag nginx:alpine 192.168.121.50:5000/nginx:alpine"
echo "   docker push 192.168.121.50:5000/nginx:alpine"
echo "============================================"
