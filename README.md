# SDOS — Software Defined Operating System

A Kubernetes cluster management and monitoring platform built on a 5-VM K3s cluster with a web-based dashboard, CI/CD pipeline monitoring, and an integrated developer workspace.

---

 Architecture

5 VMs managed by Vagrant and KVM/libvirt:

    control-plane      192.168.121.10   K3s master
    worker-dev         192.168.121.20   development workloads
    worker-production  192.168.121.30   production workloads
    worker-cicd        192.168.121.40   Jenkins :32080
    worker-monitoring  192.168.121.50   Prometheus :32090  Grafana :32030

SDOS Dashboard running on the host machine:

    Home Page            port 5000
    Cluster Dashboard    port 8080
    Server Dashboard     port 9000
    Pipeline Dashboard   port 7000
    Developer Workspace  port 6001
---

## Requirements

### Host machine
- Ubuntu 20.04+ (or similar Linux)
- KVM/libvirt enabled in BIOS
- Vagrant + vagrant-libvirt plugin
- Python 3.11+
- kubectl

### Install dependencies

    sudo apt-get install -y vagrant libvirt-daemon-system libvirt-clients qemu-kvm
    vagrant plugin install vagrant-libvirt
    curl -LO "https://dl.k8s.io/release/v1.28.5/bin/linux/amd64/kubectl"
    chmod +x kubectl && sudo mv kubectl /usr/local/bin/
    pip install flask requests

---

## Tokens Required

Before running SDOS you need to configure the following tokens:

### 1. Jenkins API Token
Used by the Developer Workspace to trigger and monitor pipelines.

1. Start the cluster and open Jenkins at http://192.168.121.40:32080
2. Log in with admin / admin
3. Click your username -> Configure -> API Token -> Add new Token -> Generate
4. Open sdos-dashboard/developer_workspace.py and replace YOUR_JENKINS_TOKEN with the generated token

### 2. Jenkins Agent Token
Used by setup-after-restart.sh to connect the host Jenkins agent.

1. Open Jenkins at http://192.168.121.40:32080
2. Manage Jenkins -> Nodes -> host-agent -> Status -> copy the secret
3. Open setup-after-restart.sh and replace YOUR_JENKINS_TOKEN with the copied secret

### 3. GitHub Personal Access Token (optional)
Used by the Developer Workspace to browse and edit GitHub repositories.

1. Go to https://github.com/settings/tokens
2. Generate a new token with repo scope
3. Paste it into the Developer Workspace UI when adding a repository

---

## Quick Start

Run these commands in order:

    git clone https://github.com/YOUR_USERNAME/fyp.git
    cd fyp
    bash host-setup.sh
    vagrant up
    sleep 180
    vagrant ssh control-plane -c "sudo cat /etc/rancher/k3s/k3s.yaml" 2>/dev/null | grep -v fog | grep -v WARNING > k3s.yaml
    sed -i 's/0.0.0.0/192.168.121.220/' k3s.yaml
    export KUBECONFIG=~/fyp/k3s.yaml
    kubectl label nodes worker-dev-integration node-role=development --overwrite
    kubectl label nodes worker-production node-role=production --overwrite
    cd sdos-dashboard && bash run-all.sh

Then open http://localhost:5000

---

## After every host restart

    cd ~/fyp
    bash setup-after-restart.sh

This will start all VMs, wait for K3s, label nodes, start dashboards and connect the Jenkins agent.

---

## Webpage

Home               port 5000    Login page linking to all dashboards
Cluster Dashboard  port 8080    K3s node metrics, Jenkins pipelines, resource charts
Server Dashboard   port 9000    Per-VM CPU/RAM/disk metrics and charts
Pipeline Dashboard port 7000    Jenkins CI/CD pipeline status and stage tracking
Developer Workspace port 6001   Monaco editor with GitHub integration and Jenkins pipeline linking

---

## Jenkins

Jenkins runs on worker-cicd at http://192.168.121.40:32080

Default credentials: admin / admin

---

## Registry

The private Docker registry runs at 192.168.121.50:30500

Default credentials: admin / passadmin

---

## Logs

Logs are written to the sdos-dashboard/logs/ directory:

    logs/home.log
    logs/dashboard.log
    logs/server_dashboard.log
    logs/pipeline_dashboard.log
    logs/developer_workspace.log
