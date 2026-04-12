from flask import Flask, render_template_string, jsonify, redirect
import subprocess
import json
import time
import urllib.request
import os
import re
from datetime import datetime
import logging
import signal
import sys

app = Flask(__name__)

log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)
app.logger.disabled = True
log.disabled = True

JENKINS_URL = "http://192.168.121.40:32080"
KUBECONFIG_PATH = os.path.expanduser('~/fyp-cluster/k3s.yaml')

cpu_history = []
memory_history = []
disk_history = []

import json as _json_sess
import os as _os_sess

_SESSION_FILE = _os_sess.path.expanduser('~/fyp-cluster/sdos-dashboard/.sdos_session')

def _get_session():
    try:
        if _os_sess.path.exists(_SESSION_FILE):
            with open(_SESSION_FILE) as _f:
                return _json_sess.load(_f)
    except Exception:
        pass
    return {}

def signal_handler(sig, frame):
    print('\n\n' + '='*60)
    print('Dashboard stopped')
    print('='*60)
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

def get_real_node_metrics():
    """Get CPU and RAM from each VM via vagrant ssh — matches server_dashboard VM LIST values"""
    vagrant_map = get_node_names_to_vagrant()
    metrics = {}
    for k8s_name, vagrant_name in vagrant_map.items():
        try:
            result = subprocess.run(
                ['vagrant', 'ssh', vagrant_name, '-c',
                 "top -bn2 | grep Cpu | tail -1 | awk '{printf \"%.1f\", 100-$8}'; echo; free | grep Mem | awk '{printf \"%.1f\", $3/$2*100}'"],
                capture_output=True, text=True, timeout=15,
                cwd=os.path.expanduser('~/fyp-cluster')
            )
            if result.returncode == 0:
                lines = [l for l in result.stdout.strip().split('\n') if l.strip() and 'fog' not in l and 'WARNING' not in l]
                if len(lines) >= 2:
                    try:
                        cpu = float(lines[0].strip())
                        ram = float(lines[1].strip())
                        metrics[k8s_name] = {'cpu': cpu, 'memory': ram}
                    except:
                        metrics[k8s_name] = {'cpu': 0.0, 'memory': 0.0}
            else:
                metrics[k8s_name] = {'cpu': 0.0, 'memory': 0.0}
        except Exception:
            metrics[k8s_name] = {'cpu': 0.0, 'memory': 0.0}
    return metrics

def get_node_names_to_vagrant():
    return {
        'control-plane': 'control-plane',
        'worker-dev-integration': 'worker-dev',
        'worker-production': 'worker-prod',
        'worker-cicd': 'worker-cicd',
        'worker-registry-monitoring': 'worker-monitoring'
    }

def get_real_disk_usage():
    vagrant_map = get_node_names_to_vagrant()
    disk_metrics = {}
    for k8s_name, vagrant_name in vagrant_map.items():
        try:
            result = subprocess.run(
                ['vagrant', 'ssh', vagrant_name, '-c', "df -h / | tail -1 | awk '{print $5}'"],
                capture_output=True, text=True, timeout=5,
                cwd=os.path.expanduser('~/fyp-cluster')
            )
            if result.returncode == 0:
                usage = result.stdout.strip().replace('%', '')
                disk_metrics[k8s_name] = float(usage) if usage.replace('.','').isdigit() else None
            else:
                disk_metrics[k8s_name] = None
        except Exception:
            disk_metrics[k8s_name] = None
    return disk_metrics

def get_node_ips():
    try:
        result = subprocess.run(
            ['kubectl', 'get', 'nodes', '-o', 'json', f'--kubeconfig={KUBECONFIG_PATH}'],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode != 0:
            return {}
        nodes_data = json.loads(result.stdout)
        node_ips = {}
        for node in nodes_data.get('items', []):
            name = node['metadata']['name']
            for addr in node['status']['addresses']:
                if addr['type'] == 'InternalIP':
                    node_ips[name] = addr['address']
                    break
        return node_ips
    except Exception:
        return {}

def get_real_latency():
    node_ips = get_node_ips()
    latency_metrics = {}
    for node_name, ip in node_ips.items():
        try:
            ping_result = subprocess.run(
                ['ping', '-c', '3', '-W', '1', ip],
                capture_output=True, text=True, timeout=5
            )
            if ping_result.returncode == 0:
                match = re.search(r'min/avg/max/[a-z]+ = [\d.]+/([\d.]+)/', ping_result.stdout)
                latency_metrics[node_name] = round(float(match.group(1)), 3) if match else None
            else:
                latency_metrics[node_name] = None
        except Exception:
            latency_metrics[node_name] = None
    return latency_metrics

def scrape_jenkins_all_jobs():
    jobs = []
    try:
        with urllib.request.urlopen(f"{JENKINS_URL}/api/json", timeout=5) as r:
            data = json.loads(r.read().decode())
        for job in data.get("jobs", []):
            name = job["name"]
            job_url = job["url"]
            try:
                with urllib.request.urlopen(f"{job_url}api/json", timeout=5) as r:
                    job_data = json.loads(r.read().decode())
                last_build = job_data.get("lastBuild")
                if last_build:
                    build_number = last_build["number"]
                    with urllib.request.urlopen(f"{job_url}{build_number}/api/json", timeout=5) as r:
                        build_data = json.loads(r.read().decode())
                    status = build_data.get("result")
                    if status is None:
                        status = "RUNNING"
                    elif status == "ABORTED":
                        status = "CANCELLED"
                else:
                    build_number = "N/A"
                    status = "NO BUILDS"
                jobs.append({"name": name, "url": job_url, "lastBuild": build_number, "status": status})
            except:
                jobs.append({"name": name, "url": job_url, "lastBuild": "N/A", "status": "ERROR"})
        return jobs
    except:
        return []


DASHBOARD_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>SDOS Dashboard</title>
    <meta http-equiv="Cache-Control" content="no-cache">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Segoe UI', Arial, sans-serif; background: #1a1a1a; color: #222; padding: 0; }
        .outer { background: #1a1a1a; min-height: 100vh; padding: 30px; }
        .container { max-width: 1400px; margin: 0 auto; background: #2d2d2d; padding: 30px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.4); }
        .header {
            background: #2d2d2d;
            padding: 20px 30px; margin-bottom: 25px;
            display: flex; justify-content: space-between; align-items: center;
            border-bottom: 4px solid #cc0000;
        }
        .header h1 { font-size: 32px; color: #ffffff; }
        .header-left { display: flex; align-items: center; gap: 20px; }
        .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; margin-bottom: 20px; }
        .card { background: #3a3a3a; color: #e0e0e0; border-radius: 6px; padding: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.2); border: none; }
        .card h3 { color: #f0f0f0; margin-bottom: 5px; border-bottom: 1px solid #666; padding-bottom: 10px; font-size: 16px; }
        .card .subtitle { color: #999999; font-size: 11px; margin-bottom: 15px; font-style: italic; }
        .status-item { display: flex; justify-content: space-between; padding: 12px; background: #2a2a2a; border-radius: 6px; margin-bottom: 10px; }
        .value { font-size: 24px; font-weight: bold; color: #cccccc; }
        .status-success   { color: #22c55e; font-weight: bold; }
        .status-failure   { color: #ef4444; font-weight: bold; }
        .status-failed    { color: #ef4444; font-weight: bold; }
        .status-running   { color: #aaaaaa; font-weight: bold; }
        .status-cancelled  { color: #f59e0b; font-weight: bold; }
        .status-no-builds  { color: #818cf8; font-weight: bold; }
        .server-grid { display: grid; grid-template-columns: repeat(5, 1fr); gap: 12px; }
        .server-card { background: #2a2a2a; padding: 15px; border-radius: 6px; text-align: center; border: 2px solid #555; transition: all 0.3s; }
        .server-card:hover { border-color: #aaaaaa; transform: translateY(-2px); }
        .server-card h4 { color: #cccccc; margin-bottom: 10px; font-size: 13px; }
        .metric { display: flex; justify-content: space-between; margin: 6px 0; font-size: 12px; color: #cccccc; }
        .metric b { color: #999999; }
        .metric.high { color: #ef4444; font-weight: bold; }
        table { width: 100%; border-collapse: collapse; }
        th, td { padding: 12px; text-align: left; border-bottom: 1px solid #334155; }
        th { background: #2a2a2a; color: #e0e0e0; font-weight: 600; }
        td { color: #cccccc; }
        .btn { background: #555555; color: white; border: none; padding: 10px 20px; border-radius: 8px; cursor: pointer; margin: 5px; text-decoration: none; display: inline-block; transition: all 0.3s; }
        .btn:hover { background: #666666; transform: translateY(-1px); }
        .btn-home { background: #64748b; }
        .btn-home:hover { background: #555555; }
        .chart-container { height: 200px; background: #2a2a2a; border-radius: 6px; padding: 15px; margin-top: 10px; position: relative; }
        .tb-btn { background: #383838; color: #999999; border: 1px solid #555; padding: 5px 12px; border-radius: 6px; cursor: pointer; font-size: 12px; font-weight: 600; transition: all 0.2s; }
        .tb-btn:hover { border-color: #cccccc; color: #e0e0e0; }
        .tb-btn.active { background: #3a3a3a; border-color: #cccccc; color: #cccccc; }
        .tb-btn.active-running   { background: #3a3a3a; border-color: #888; color: #ccc; }
        .tb-btn.active-success   { background: #1a3a2a; border-color: #4a8a5a; color: #7abf8a; }
        .tb-btn.active-cancelled { background: #3a2a0a; border-color: #8a6a1a; color: #c49a3a; }
        .tb-btn.active-failure   { background: #3a1a1a; border-color: #8a3a3a; color: #c06060; }
        .tb-btn.active-no-builds { background: #1a1a3a; border-color: #4a4a8a; color: #7a7ac0; }
        .tb-clear-btn { background: #383838; color: #999999; border: 1px solid #555; padding: 5px 12px; border-radius: 6px; cursor: pointer; font-size: 12px; font-weight: 600; transition: all 0.2s; }
        .tb-clear-btn:hover { border-color: #cccccc; color: #e0e0e0; }
    </style>
</head>
<body>
    <div style="background:#1a1a1a;min-height:100vh;padding:30px;">
    <div class="container">
        <div class="header">
            <div class="header-left">
                <a href="http://localhost:5000" class="btn btn-home">← Home</a>
                <button onclick="logout()" style="background:#ef4444;color:white;border:none;padding:8px 18px;border-radius:8px;cursor:pointer;font-size:13px;font-weight:600;transition:all 0.3s;" onmouseover="this.style.background='#dc2626';this.style.transform='translateY(-2px)'" onmouseout="this.style.background='#ef4444';this.style.transform='translateY(0)'">Logout</button>
                <h1 style="color:white;">SDOS Dashboard</h1>
            </div>
        </div>
        <div style="margin-bottom: 20px;">
            <a href="http://192.168.121.40:32080" target="_blank" class="btn">Jenkins</a>
            <a href="http://192.168.121.50:32030" target="_blank" class="btn">Grafana</a>
            <button onclick="fetchData()" class="btn">Refresh</button>
        </div>
        <div class="grid">
            <div class="card">
                <h3>SYSTEM STATUS</h3>
                <div class="status-item"><span>Health</span><span class="status-success" id="health">Loading...</span></div>
                <div class="status-item"><span>Active Servers</span><span class="value" id="servers">-</span></div>
                <div class="status-item"><span>Active Pods</span><span class="value" id="pods">-</span></div>
                <div class="status-item"><span>Jenkins Jobs</span><span class="value" id="jobs">-</span></div>
            </div>
            <div class="card">
                <h3>CPU USAGE</h3>
                <div class="subtitle">Mean across all 5 servers over time</div>
                <div class="chart-container"><svg width="100%" height="180" id="cpu-chart"></svg></div>
            </div>
            <div class="card">
                <h3>MEMORY USAGE</h3>
                <div class="subtitle">Mean across all 5 servers over time</div>
                <div class="chart-container"><svg width="100%" height="180" id="memory-chart"></svg></div>
            </div>
            <div class="card">
                <h3>DISK USAGE</h3>
                <div class="subtitle">Mean across all 5 servers over time</div>
                <div class="chart-container"><svg width="100%" height="180" id="disk-chart"></svg></div>
            </div>
        </div>
        <div class="card" style="margin-bottom:20px;">
            <h3>SERVER STATUS</h3>
            <div class="server-grid" id="server-grid"></div>
        </div>
        <div class="card">
            <h3>JENKINS PIPELINES</h3>
            <div style="display:flex;align-items:center;gap:8px;margin-bottom:14px;flex-wrap:wrap;">
                <button class="tb-btn" id="btn-build-desc" onclick="setSort('desc')">Most Builds</button>
                <button class="tb-btn" id="btn-build-asc"  onclick="setSort('asc')">Least Builds</button>
                <div style="width:1px;height:22px;background:#334155;margin:0 4px;"></div>
                <button class="tb-btn" id="filter-RUNNING"   onclick="setFilter('RUNNING')">Running</button>
                <button class="tb-btn" id="filter-SUCCESS"   onclick="setFilter('SUCCESS')">Success</button>
                <button class="tb-btn" id="filter-CANCELLED" onclick="setFilter('CANCELLED')">Cancelled</button>
                <button class="tb-btn" id="filter-FAILURE"   onclick="setFilter('FAILURE')">Failure</button>
                <button class="tb-btn" id="filter-NOBUILDS"  onclick="setFilter('NO BUILDS')">No Builds</button>
                <div style="width:1px;height:22px;background:#334155;margin:0 4px;"></div>
                <button class="tb-clear-btn" onclick="clearControls()">Clear Filter</button>
            </div>
            <table>
                <thead><tr>
                    <th>Pipeline Name</th><th>Last Build</th><th>Status</th><th>Link</th>
                </tr></thead>
                <tbody id="jenkins-table"></tbody>
            </table>
        </div>
    </div>
    <script>
        setInterval(fetchData, 3000);

        async function logout() {
            await fetch('http://localhost:5000/api/logout', { method: 'POST' });
            window.location.href = 'http://localhost:5000';
        }

        let sortDir = null;
        let activeFilters = new Set();
        let cachedJobs = [];

        function setSort(dir) {
            if ((dir === 'asc' && sortDir === 1) || (dir === 'desc' && sortDir === -1)) {
                sortDir = null;
            } else {
                sortDir = dir === 'asc' ? 1 : -1;
            }
            document.getElementById('btn-build-asc').className  = (sortDir ===  1) ? 'tb-btn active' : 'tb-btn';
            document.getElementById('btn-build-desc').className = (sortDir === -1) ? 'tb-btn active' : 'tb-btn';
            renderJenkinsTable(cachedJobs);
        }

        const FILTER_CLS = { RUNNING:'active-running', SUCCESS:'active-success', CANCELLED:'active-cancelled', FAILURE:'active-failure', 'NO BUILDS':'active-no-builds' };

        function setFilter(status) {
            if (activeFilters.has(status)) { activeFilters.delete(status); } else { activeFilters.add(status); }
            ['RUNNING','SUCCESS','CANCELLED','FAILURE','NO BUILDS'].forEach(s => {
                const btnId = s === 'NO BUILDS' ? 'filter-NOBUILDS' : 'filter-' + s;
                const btn = document.getElementById(btnId);
                if (!btn) return;
                btn.className = activeFilters.has(s) ? 'tb-btn ' + FILTER_CLS[s] : 'tb-btn';
            });
            renderJenkinsTable(cachedJobs);
        }

        function clearControls() {
            sortDir = null;
            document.getElementById('btn-build-asc').className  = 'tb-btn';
            document.getElementById('btn-build-desc').className = 'tb-btn';
            activeFilters.clear();
            ['RUNNING','SUCCESS','CANCELLED','FAILURE','NO BUILDS'].forEach(s => {
                const bId = s === 'NO BUILDS' ? 'filter-NOBUILDS' : 'filter-' + s;
                const b = document.getElementById(bId);
                if (b) b.className = 'tb-btn';
            });
            renderJenkinsTable(cachedJobs);
        }

        function renderJenkinsTable(jobs) {
            const tbody = document.getElementById('jenkins-table');
            if (!jobs || jobs.length === 0) return;
            let display = activeFilters.size === 0 ? [...jobs]
                : jobs.filter(j => activeFilters.has(j.status) || (activeFilters.has('FAILURE') && j.status === 'FAILED'));
            if (sortDir !== null) {
                display.sort((a, b) => {
                    const aNum = a.lastBuild === 'N/A' ? -1 : parseInt(a.lastBuild);
                    const bNum = b.lastBuild === 'N/A' ? -1 : parseInt(b.lastBuild);
                    return (aNum - bNum) * sortDir;
                });
            }
            tbody.innerHTML = '';
            if (display.length === 0) {
                tbody.innerHTML = '<tr><td colspan="4" style="text-align:center;color:#475569;padding:20px;">No pipelines match this filter</td></tr>';
                return;
            }
            display.forEach(job => {
                const row = tbody.insertRow();
                row.innerHTML =
                    `<td><b>${job.name}</b></td>` +
                    `<td>${job.lastBuild !== 'N/A' ? '#' + job.lastBuild : 'N/A'}</td>` +
                    `<td><span class="status-${job.status.toLowerCase().replace(/ /g, '-')}">${job.status}</span></td>` +
                    `<td><a href="${job.url}" target="_blank" style="color:#aaaaaa">View</a></td>`;
            });
        }

        function drawChart(elementId, data, color) {
            const svg = document.getElementById(elementId);
            if (!data || data.length < 2) {
                svg.innerHTML = '<text x="150" y="90" text-anchor="middle" fill="#999999" font-size="12">Collecting data...</text>';
                return;
            }
            const width=300,height=180,pL=35,pR=10,pT=30,pB=30;
            const gW=width-pL-pR, gH=height-pT-pB;
            const maxV=Math.max(...data), minV=Math.min(...data), range=maxV-minV;
            let dMin,dMax;
            if(range<3){const c=(maxV+minV)/2;dMin=Math.max(0,c-2.5);dMax=c+2.5;}
            else{dMin=Math.max(0,minV-range*0.2);dMax=maxV+range*0.2;}
            const dR=dMax-dMin;
            const pts=data.map((v,i)=>{ const x=pL+(i/(data.length-1))*gW; const y=pT+gH-((v-dMin)/dR)*gH; return x+','+y; }).join(' ');
            let labels='',grid='';
            for(let i=0;i<=4;i++){
                const v=dMin+(dR*i/4); const y=pT+gH-(i/4)*gH;
                labels+=`<text x="${pL-5}" y="${y+4}" text-anchor="end" font-size="10" fill="#999999">${v.toFixed(1)}%</text>`;
                grid+=`<line x1="${pL}" y1="${y}" x2="${pL+gW}" y2="${y}" stroke="#555555" stroke-width="1" stroke-dasharray="3,3"/>`;
            }
            svg.innerHTML=grid+
                `<polyline points="${pts}" fill="none" stroke="${color}" stroke-width="3"/>` +
                `<line x1="${pL}" y1="${pT+gH}" x2="${pL+gW}" y2="${pT+gH}" stroke="#666666" stroke-width="2"/>` +
                `<line x1="${pL}" y1="${pT}" x2="${pL}" y2="${pT+gH}" stroke="#666666" stroke-width="2"/>` +
                labels+
                `<text x="${pL+gW/2}" y="${height-5}" text-anchor="middle" font-size="10" fill="#999999">Data Points (last 20 readings)</text>`+
                `<text x="10" y="15" text-anchor="start" font-size="9" fill="#999999">Usage (%)</text>`+
                `<text x="${pL+gW/2}" y="18" text-anchor="middle" font-size="13" fill="${color}" font-weight="bold">Current: ${data[data.length-1].toFixed(1)}%</text>`;
        }

        async function fetchData() {
            try {
                const data = await (await fetch('/api/data?v=' + Date.now())).json();
                document.getElementById('health').textContent  = data.health_status || 'N/A';
                document.getElementById('servers').textContent = data.active_servers || 'N/A';
                document.getElementById('pods').textContent    = data.active_deployments || 'N/A';
                document.getElementById('jobs').textContent    = data.jenkins_jobs ? data.jenkins_jobs.length : 'N/A';

                drawChart('cpu-chart',    data.cpu_history,    '#60a5fa');
                drawChart('memory-chart', data.memory_history, '#22c55e');
                drawChart('disk-chart',   data.disk_history,   '#f59e0b');

                const grid = document.getElementById('server-grid');
                if (data.servers) {
                    grid.innerHTML = '';
                    data.servers.forEach(s => {
                        const cpuV  = s.cpu     != null ? s.cpu.toFixed(1)  + '%'  : 'N/A';
                        const ramV  = s.ram     != null ? s.ram.toFixed(1)  + '%'  : 'N/A';
                        const diskV = s.disk    != null ? s.disk.toFixed(1) + '%'  : 'N/A';
                        const latV  = s.latency != null ? s.latency         + 'ms' : 'N/A';
                        grid.innerHTML +=
                            `<div class="server-card"><h4>${s.name}</h4>` +
                            `<div class="metric ${s.cpu>70?'high':''}"><b>vCPU %:</b> <span>${cpuV}</span></div>` +
                            `<div class="metric ${s.ram>80?'high':''}"><b>RAM %:</b> <span>${ramV}</span></div>` +
                            `<div class="metric ${s.disk>85?'high':''}"><b>Disk Usage:</b> <span>${diskV}</span></div>` +
                            `<div class="metric"><b>PING:</b> <span>${latV}</span></div>` +
                            `<div class="metric"><b>STATUS:</b> <span class="status-success">${s.status}</span></div></div>`;
                    });
                }

                if (data.jenkins_jobs && data.jenkins_jobs.length > 0) {
                    cachedJobs = data.jenkins_jobs;
                    renderJenkinsTable(cachedJobs);
                }
            } catch(e) { console.error(e); }
        }

        fetchData();

        setInterval(async function() {
            try {
                const res = await fetch('http://localhost:5000/api/check-session');
                const data = await res.json();
                if (!data.logged_in) window.location.href = 'http://localhost:5000';
            } catch(e) {}
        }, 30000);
    </script>
</body>
</html>
"""

@app.route('/')
def dashboard():
    if not _get_session().get("logged_in"):
        return redirect("http://localhost:5000")
    return render_template_string(DASHBOARD_TEMPLATE)

@app.route('/api/data')
def get_data():
    global cpu_history, memory_history, disk_history
    try:
        result = subprocess.run(['kubectl','get','nodes','-o','json',f'--kubeconfig={KUBECONFIG_PATH}'], capture_output=True, text=True, timeout=5)
        nodes_data = json.loads(result.stdout) if result.returncode == 0 else {'items': []}
        pods_result = subprocess.run(['kubectl','get','pods','--all-namespaces','-o','json',f'--kubeconfig={KUBECONFIG_PATH}'], capture_output=True, text=True, timeout=5)
        pods_data = json.loads(pods_result.stdout) if pods_result.returncode == 0 else {'items': []}
        real_metrics    = get_real_node_metrics()
        disk_metrics    = get_real_disk_usage()
        latency_metrics = get_real_latency()
        servers = []
        total_cpu = total_memory = total_disk = 0.0
        count_cpu = count_mem = count_disk = 0
        for node in nodes_data.get('items', []):
            name   = node['metadata']['name']
            status = 'OK' if any(c['type']=='Ready' and c['status']=='True' for c in node['status']['conditions']) else 'NOK'
            display_name = name.replace('worker-','').replace('-',' ').upper()
            if 'control' in name:
                display_name = 'CONTROL PLANE'
            cpu     = real_metrics.get(name,{}).get('cpu', 0.0)
            ram     = real_metrics.get(name,{}).get('memory', 0.0)
            disk    = disk_metrics.get(name)
            latency = latency_metrics.get(name)
            if cpu  is not None: total_cpu    += cpu;  count_cpu  += 1
            if ram  is not None: total_memory += ram;  count_mem  += 1
            if disk is not None: total_disk   += disk; count_disk += 1
            servers.append({'name': display_name, 'cpu': cpu, 'ram': ram, 'disk': disk, 'latency': latency, 'status': status})
        if count_cpu  > 0: cpu_history.append(round(total_cpu    / count_cpu,  1))
        if count_mem  > 0: memory_history.append(round(total_memory / count_mem,  1))
        if count_disk > 0: disk_history.append(round(total_disk   / count_disk, 1))
        if len(cpu_history)    > 20: cpu_history.pop(0)
        if len(memory_history) > 20: memory_history.pop(0)
        if len(disk_history)   > 20: disk_history.pop(0)
        running_pods  = sum(1 for pod in pods_data.get('items',[]) if pod['status']['phase']=='Running')
        jenkins_jobs  = scrape_jenkins_all_jobs()
        return jsonify({
            'health_status':      'OK' if servers else 'NOK',
            'active_servers':     len(servers),
            'active_deployments': running_pods,
            'servers':            servers,
            'jenkins_jobs':       jenkins_jobs,
            'cpu_history':        cpu_history,
            'memory_history':     memory_history,
            'disk_history':       disk_history,
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    print("="*60)
    print("SDOS Dashboard")
    print("="*60)
    print("Access: http://localhost:8080")
    print("Home Page: http://localhost:5000")
    print("Press Ctrl+C to stop")
    print("="*60)
    app.run(host='0.0.0.0', port=8080, debug=False, threaded=True, use_reloader=False)
