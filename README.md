# SDOS — Software Defined Operating System

A Kubernetes cluster management and monitoring platform built on a 5-VM K3s cluster with a web-based dashboard, CI/CD pipeline monitoring, and an integrated developer workspace.

---

## Architecture

```
Host Machine
├── 5x Vagrant VMs (libvirt)
│   ├── control-plane      192.168.121.10  (K3s master)
│   ├── worker-dev         192.168.121.20  (development workloads)
│   ├── worker-production  192.168.121.30  (production workloads)
│   ├── worker-cicd        192.168.121.40  (Jenkins :32080)
│   └── worker-monitoring  192.168.121.50  (Prometheus :32090, Grafana :32030)
│
└── SDOS Dashboard (Docker or bare Python)
    ├── Home Page           :5000
    ├── Cluster Dashboard   :8080
    ├── Server Dashboard    :9000
    ├── Pipeline Dashboard  :7000
    └── Developer Workspace :6001
```

---

## Requirements

### Host machine
- Ubuntu 20.04+ (or similar Linux)
- [Vagrant](https://www.vagrantup.com/) + [libvirt](https://libvirt.org/)
- Docker + Docker Compose (for containerised deployment)
- OR Python 3.11+ (for bare metal deployment)

---

## Quick Start

### 1. Clone the repo
```bash
git clone https://github.com/YOUR_USERNAME/fyp.git
cd fyp
```

### 2. Start the K3s cluster
```bash
vagrant up
sleep 180   # wait for cluster to fully initialise

# Label the worker nodes
export KUBECONFIG=./k3s.yaml
kubectl label nodes worker-dev-integration node-role=development --overwrite
kubectl label nodes worker-production      node-role=production  --overwrite
```

### 3a. Run with Docker (recommended)
```bash
docker compose up --build
```
Open http://localhost:5000

### 3b. Run without Docker
```bash
pip install -r requirements.txt
bash run-all.sh
```
Open http://localhost:5000

---

## Running on a separate PC

If you want to run the SDOS dashboard on a **different machine** from the VMs:

1. Copy `k3s.yaml` from the host machine to the dashboard machine
2. Edit `k3s.yaml` — change the server IP from `127.0.0.1` to `192.168.121.10`
3. Make sure the dashboard machine can reach `192.168.121.x` (same network / VPN)
4. Run the dashboard normally with Docker or Python

---

## Services

| Service | Port | Description |
|---------|------|-------------|
| Home | 5000 | Landing page linking to all dashboards |
| Cluster Dashboard | 8080 | K3s node metrics, Jenkins pipelines, resource charts |
| Server Dashboard | 9000 | Per-VM CPU/RAM/disk metrics and charts |
| Pipeline Dashboard | 7000 | Jenkins CI/CD pipeline status and stage tracking |
| Developer Workspace | 6001 | Monaco editor with GitHub integration and Jenkins pipeline linking |

---

## Jenkins

Jenkins runs on `worker-cicd` at `http://192.168.121.40:32080`

Default credentials: `admin / admin`

To get your API token for the Developer Workspace:
1. Log in to Jenkins
2. Click your username → Configure
3. API Token → Add new Token → Generate
4. Paste the token into `developer_workspace.py` under `JENKINS_TOKEN`

---

## Logs

When running with `run-all.sh`, logs are written to the `logs/` directory:
```
logs/home.log
logs/dashboard.log
logs/server_dashboard.log
logs/pipeline_dashboard.log
logs/developer_workspace.log
```

---

## After every host restart

```bash
cd ~/fyp
vagrant up
sleep 180
export KUBECONFIG=./k3s.yaml
kubectl label nodes worker-dev-integration node-role=development --overwrite
kubectl label nodes worker-production      node-role=production  --overwrite
docker compose up -d   # or: bash run-all.sh
```
