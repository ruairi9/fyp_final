#!/bin/bash

echo "Running k6 Load Test..."

export KUBECONFIG=./k3s.yaml

# Create the test script
cat > /tmp/k6-test.js <<'K6SCRIPT'
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
  let res = http.get('http://user-code-api.production.svc.cluster.local:5000');
  
  check(res, {
    'status is 200': (r) => r.status === 200,
    'response time < 500ms': (r) => r.timings.duration < 500,
    'has content': (r) => r.body.length > 0,
  });
  
  sleep(1);
}
K6SCRIPT

# Copy to k6 pod
kubectl cp /tmp/k6-test.js load-testing/$(kubectl get pods -n load-testing -o jsonpath='{.items[0].metadata.name}'):/tmp/test.js

# Run it
kubectl exec -n load-testing $(kubectl get pods -n load-testing -o jsonpath='{.items[0].metadata.name}') -- k6 run /tmp/test.js

