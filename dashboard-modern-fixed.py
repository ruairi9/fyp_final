from flask import Flask, render_template_string, jsonify
import subprocess
import json
import time
import urllib.request
import os
import re
from datetime import datetime
import logging

app = Flask(__name__)

# Disable Flask logging
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

JENKINS_URL = "http://192.168.121.40:32080"
KUBECONFIG_PATH = os.path.expanduser('~/fyp-cluster/k3s.yaml')

cpu_history = []
memory_history = []
disk_history = []

def get_real_node_metrics():
    """Get REAL CPU and Memory from kubectl top nodes"""
    try:
        result = subprocess.run(
            ['kubectl', 'top', 'nodes', '--no-headers', f'--kubeconfig={KUBECONFIG_PATH}'],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if result.returncode != 0:
            return {}
        
        metrics = {}
        for line in result.stdout.strip().split('\n'):
            if line:
                parts = line.split()
                if len(parts) >= 5:
                    node_name = parts[0]
                    cpu_percent = parts[2].replace('%', '')
                    mem_percent = parts[4].replace('%', '')
                    
                    metrics[node_name] = {
                        'cpu': float(cpu_percent) if cpu_percent.replace('.','').isdigit() else 0.0,
                        'memory': float(mem_percent) if mem_percent.replace('.','').isdigit() else 0.0
                    }
        
        return metrics
    except Exception as e:
        print(f"Error getting metrics: {e}")
        return {}

def get_node_names_to_vagrant():
    """Map K8s node names to Vagrant VM names"""
    mapping = {
        'control-plane': 'control-plane',
        'worker-dev-integration': 'worker-dev',
        'worker-production': 'worker-prod',
        'worker-cicd': 'worker-cicd',
        'worker-registry-monitoring': 'worker-monitoring'
    }
    return mapping

def get_real_disk_usage():
    """Get REAL disk usage using Vagrant SSH"""
    vagrant_map = get_node_names_to_vagrant()
    disk_metrics = {}
    
    for k8s_name, vagrant_name in vagrant_map.items():
        try:
            result = subprocess.run(
                ['vagrant', 'ssh', vagrant_name, '-c', 'df -h / | tail -1 | awk \'{print $5}\''],
                capture_output=True,
                text=True,
                timeout=5,
                cwd=os.path.expanduser('~/fyp-cluster')
            )
            
            if result.returncode == 0:
                usage = result.stdout.strip().replace('%', '')
                if usage.replace('.','').isdigit():
                    disk_metrics[k8s_name] = float(usage)
            else:
                disk_metrics[k8s_name] = None
        except Exception as e:
            disk_metrics[k8s_name] = None
    
    return disk_metrics

def get_node_ips():
    """Get internal IPs of all nodes"""
    try:
        result = subprocess.run(
            ['kubectl', 'get', 'nodes', '-o', 'json', f'--kubeconfig={KUBECONFIG_PATH}'],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if result.returncode != 0:
            return {}
        
        nodes_data = json.loads(result.stdout)
        node_ips = {}
        
        for node in nodes_data.get('items', []):
            name = node['metadata']['name']
            addresses = node['status']['addresses']
            for addr in addresses:
                if addr['type'] == 'InternalIP':
                    node_ips[name] = addr['address']
                    break
        
        return node_ips
    except Exception as e:
        print(f"Error getting IPs: {e}")
        return {}

def get_real_latency():
    """Get REAL network latency with exact precision"""
    node_ips = get_node_ips()
    latency_metrics = {}
    
    for node_name, ip in node_ips.items():
        try:
            ping_result = subprocess.run(
                ['ping', '-c', '3', '-W', '1', ip],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if ping_result.returncode == 0:
                match = re.search(r'min/avg/max/[a-z]+ = [\d.]+/([\d.]+)/', ping_result.stdout)
                if match:
                    latency = float(match.group(1))
                    latency_metrics[node_name] = round(latency, 3)
                else:
                    latency_metrics[node_name] = None
            else:
                latency_metrics[node_name] = None
        except Exception as e:
            latency_metrics[node_name] = None
    
    return latency_metrics

def scrape_jenkins_all_jobs():
    """Fetch Jenkins jobs using API"""
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
                else:
                    build_number = "N/A"
                    status = "NO BUILDS"

                jobs.append({"name": name, "url": job_url, "lastBuild": build_number, "status": status})
            except:
                jobs.append({"name": name, "url": job_url, "lastBuild": "N/A", "status": "ERROR"})

        return jobs
    except:
        return []

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>SDOS Dashboard</title>
    <meta http-equiv="Cache-Control" content="no-cache">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Segoe UI', Arial, sans-serif; background: #0f172a; color: #e2e8f0; padding: 20px; }
        .container { max-width: 1400px; margin: 0 auto; }
        .header {
            background: linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%);
            padding: 20px 30px;
            border-radius: 15px;
            margin-bottom: 25px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            box-shadow: 0 8px 32px rgba(59, 130, 246, 0.3);
        }
        .header h1 { font-size: 32px; }
        .header-right { text-align: right; font-size: 13px; opacity: 0.9; }
        .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; margin-bottom: 20px; }
        .card { background: #1e293b; border-radius: 12px; padding: 20px; box-shadow: 0 4px 20px rgba(0,0,0,0.3); border: 1px solid #334155; }
        .card h3 { color: #60a5fa; margin-bottom: 5px; border-bottom: 2px solid #3b82f6; padding-bottom: 10px; font-size: 16px; }
        .card .subtitle { color: #94a3b8; font-size: 11px; margin-bottom: 15px; font-style: italic; }
        .status-item { display: flex; justify-content: space-between; padding: 12px; background: #0f172a; border-radius: 8px; margin-bottom: 10px; }
        .value { font-size: 24px; font-weight: bold; color: #60a5fa; }
        .status-success { color: #22c55e; font-weight: bold; }
        .status-failure { color: #ef4444; font-weight: bold; }
        .status-running { color: #3b82f6; font-weight: bold; }
        .server-grid { display: grid; grid-template-columns: repeat(5, 1fr); gap: 12px; }
        .server-card { background: #0f172a; padding: 15px; border-radius: 10px; text-align: center; border: 2px solid #334155; transition: all 0.3s; }
        .server-card:hover { border-color: #3b82f6; transform: translateY(-2px); }
        .server-card h4 { color: #60a5fa; margin-bottom: 10px; font-size: 13px; }
        .metric { display: flex; justify-content: space-between; margin: 6px 0; font-size: 12px; color: #cbd5e1; }
        .metric b { color: #94a3b8; }
        .metric.high { color: #ef4444; font-weight: bold; }
        table { width: 100%; border-collapse: collapse; }
        th, td { padding: 12px; text-align: left; border-bottom: 1px solid #334155; }
        th { background: #0f172a; color: #60a5fa; font-weight: 600; }
        td { color: #cbd5e1; }
        .btn { background: #3b82f6; color: white; border: none; padding: 10px 20px; border-radius: 8px; cursor: pointer; margin: 5px; text-decoration: none; display: inline-block; transition: all 0.3s; }
        .btn:hover { background: #2563eb; transform: translateY(-1px); }
        .chart-container { height: 200px; background: #0f172a; border-radius: 10px; padding: 15px 15px 15px 5px; margin-top: 10px; position: relative; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>SDOS Dashboard</h1>
            <div class="header-right">
                <div>Last Update: <span id="lastUpdate">Loading...</span></div>
                <div>Next: <span id="nextUpdate">5s</span></div>
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
                <h3>CPU USAGE (CLUSTER AVERAGE)</h3>
                <div class="subtitle">Mean across all 5 servers over time</div>
                <div class="chart-container"><svg width="100%" height="180" id="cpu-chart"></svg></div>
            </div>

            <div class="card">
                <h3>MEMORY USAGE (CLUSTER AVERAGE)</h3>
                <div class="subtitle">Mean across all 5 servers over time</div>
                <div class="chart-container"><svg width="100%" height="180" id="memory-chart"></svg></div>
            </div>

            <div class="card">
                <h3>DISK USAGE (CLUSTER AVERAGE)</h3>
                <div class="subtitle">Mean across all 5 servers over time</div>
                <div class="chart-container"><svg width="100%" height="180" id="disk-chart"></svg></div>
            </div>
        </div>

        <div class="card">
            <h3>SERVER STATUS</h3>
            <div class="server-grid" id="server-grid"></div>
        </div>

        <div class="card">
            <h3>JENKINS PIPELINES</h3>
            <table>
                <thead><tr><th>Pipeline Name</th><th>Last Build</th><th>Status</th><th>Link</th></tr></thead>
                <tbody id="jenkins-table"></tbody>
            </table>
        </div>
    </div>

    <script>
        let countdown = 5;
        setInterval(() => { countdown--; if (countdown <= 0) { countdown = 5; fetchData(); } document.getElementById('nextUpdate').textContent = countdown + 's'; }, 1000);
        
        function drawChart(elementId, data, color) {
            const svg = document.getElementById(elementId);
            if (!data || data.length < 2) { 
                svg.innerHTML = '<text x="150" y="90" text-anchor="middle" fill="#64748b" font-size="12">Collecting data...</text>'; 
                return; 
            }
            
            const width = 310;
            const height = 180;
            const paddingLeft = 40;
            const paddingRight = 10;
            const paddingTop = 30;
            const paddingBottom = 30;
            const graphWidth = width - paddingLeft - paddingRight;
            const graphHeight = height - paddingTop - paddingBottom;
            
            const maxVal = Math.max(...data);
            const minVal = Math.min(...data);
            const dataRange = maxVal - minVal;
            
            let displayMin, displayMax;
            if (dataRange < 3) {
                const center = (maxVal + minVal) / 2;
                displayMin = Math.max(0, center - 2.5);
                displayMax = center + 2.5;
            } else {
                displayMin = Math.max(0, minVal - dataRange * 0.2);
                displayMax = maxVal + dataRange * 0.2;
            }
            
            const displayRange = displayMax - displayMin;
            
            const points = data.map((val, idx) => {
                const x = paddingLeft + (idx / (data.length - 1)) * graphWidth;
                const y = paddingTop + graphHeight - ((val - displayMin) / displayRange) * graphHeight;
                return x + ',' + y;
            }).join(' ');
            
            const yLabels = [];
            for (let i = 0; i <= 4; i++) {
                const val = displayMin + (displayRange * i / 4);
                const y = paddingTop + graphHeight - (i / 4) * graphHeight;
                yLabels.push('<text x="' + (paddingLeft - 5) + '" y="' + (y + 4) + '" text-anchor="end" font-size="10" fill="#64748b">' + val.toFixed(1) + '%</text>');
            }
            
            const gridLines = [];
            for (let i = 0; i <= 4; i++) {
                const y = paddingTop + (i / 4) * graphHeight;
                gridLines.push('<line x1="' + paddingLeft + '" y1="' + y + '" x2="' + (paddingLeft + graphWidth) + '" y2="' + y + '" stroke="#334155" stroke-width="1" stroke-dasharray="3,3"/>');
            }
            
            svg.innerHTML = gridLines.join('') +
                '<polyline points="' + points + '" fill="none" stroke="' + color + '" stroke-width="3"/>' +
                '<line x1="' + paddingLeft + '" y1="' + (paddingTop + graphHeight) + '" x2="' + (paddingLeft + graphWidth) + '" y2="' + (paddingTop + graphHeight) + '" stroke="#475569" stroke-width="2"/>' +
                '<line x1="' + paddingLeft + '" y1="' + paddingTop + '" x2="' + paddingLeft + '" y2="' + (paddingTop + graphHeight) + '" stroke="#475569" stroke-width="2"/>' +
                yLabels.join('') +
                '<text x="' + (paddingLeft + graphWidth / 2) + '" y="' + (height - 5) + '" text-anchor="middle" font-size="10" fill="#94a3b8">Time (last 20 readings, 5s interval)</text>' +
                '<text x="5" y="' + (paddingTop + graphHeight / 2) + '" text-anchor="start" font-size="9" fill="#94a3b8" transform="rotate(-90, 10, ' + (paddingTop + graphHeight / 2) + ')">Usage (%)</text>' +
                '<text x="' + (paddingLeft + graphWidth / 2) + '" y="18" text-anchor="middle" font-size="13" fill="' + color + '" font-weight="bold">Current: ' + data[data.length - 1].toFixed(1) + '%</text>';
        }
        
        async function fetchData() {
            try {
                const data = await (await fetch('/api/data?v=' + Date.now())).json();
                document.getElementById('health').textContent = data.health_status || 'N/A';
                document.getElementById('servers').textContent = data.active_servers || 'N/A';
                document.getElementById('pods').textContent = data.active_deployments || 'N/A';
                document.getElementById('jobs').textContent = data.jenkins_jobs ? data.jenkins_jobs.length : 'N/A';
                document.getElementById('lastUpdate').textContent = new Date().toLocaleTimeString();
                
                drawChart('cpu-chart', data.cpu_history, '#60a5fa');
                drawChart('memory-chart', data.memory_history, '#22c55e');
                drawChart('disk-chart', data.disk_history, '#f59e0b');
                
                const grid = document.getElementById('server-grid');
                if (data.servers) {
                    grid.innerHTML = '';
                    data.servers.forEach(s => {
                        const cpuVal = s.cpu !== null ? s.cpu.toFixed(1) + '%' : 'N/A';
                        const ramVal = s.ram !== null ? s.ram.toFixed(1) + '%' : 'N/A';
                        const diskVal = s.disk !== null ? s.disk.toFixed(1) + '%' : 'N/A';
                        const latVal = s.latency !== null ? s.latency + 'ms' : 'N/A';
                        
                        grid.innerHTML += '<div class="server-card"><h4>' + s.name + '</h4>' +
                            '<div class="metric ' + (s.cpu > 70 ? 'high' : '') + '"><b>CPU:</b> <span>' + cpuVal + '</span></div>' +
                            '<div class="metric ' + (s.ram > 80 ? 'high' : '') + '"><b>RAM:</b> <span>' + ramVal + '</span></div>' +
                            '<div class="metric ' + (s.disk > 85 ? 'high' : '') + '"><b>DISK:</b> <span>' + diskVal + '</span></div>' +
                            '<div class="metric"><b>PING:</b> <span>' + latVal + '</span></div>' +
                            '<div class="metric"><b>STATUS:</b> <span class="status-success">' + s.status + '</span></div></div>';
                    });
                }
                
                const tbody = document.getElementById('jenkins-table');
                if (data.jenkins_jobs && data.jenkins_jobs.length > 0) {
                    tbody.innerHTML = '';
                    data.jenkins_jobs.forEach(job => {
                        const row = tbody.insertRow();
                        row.innerHTML = '<td><b>' + job.name + '</b></td><td>' + (job.lastBuild !== 'N/A' ? '#' + job.lastBuild : 'N/A') + '</td><td><span class="status-' + job.status.toLowerCase() + '">' + job.status + '</span></td><td><a href="' + job.url + '" target="_blank" style="color:#60a5fa">View</a></td>';
                    });
                }
            } catch (error) { console.error(error); }
        }
        fetchData();
    </script>
</body>
</html>
'''

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/data')
def get_data():
    global cpu_history, memory_history, disk_history
    
    try:
        result = subprocess.run(['kubectl', 'get', 'nodes', '-o', 'json', f'--kubeconfig={KUBECONFIG_PATH}'], capture_output=True, text=True, timeout=5)
        nodes_data = json.loads(result.stdout) if result.returncode == 0 else {'items': []}
        
        pods_result = subprocess.run(['kubectl', 'get', 'pods', '--all-namespaces', '-o', 'json', f'--kubeconfig={KUBECONFIG_PATH}'], capture_output=True, text=True, timeout=5)
        pods_data = json.loads(pods_result.stdout) if pods_result.returncode == 0 else {'items': []}
        
        real_metrics = get_real_node_metrics()
        disk_metrics = get_real_disk_usage()
        latency_metrics = get_real_latency()
        
        servers = []
        total_cpu = total_memory = total_disk = 0.0
        count_cpu = count_mem = count_disk = 0
        
        for node in nodes_data.get('items', []):
            name = node['metadata']['name']
            status = 'OK' if any(c['type'] == 'Ready' and c['status'] == 'True' for c in node['status']['conditions']) else 'NOK'
            display_name = name.replace('worker-', '').replace('-', ' ').upper()
            if 'control' in name:
                display_name = 'CONTROL PLANE'
            
            cpu = real_metrics.get(name, {}).get('cpu', 0.0)
            ram = real_metrics.get(name, {}).get('memory', 0.0)
            disk = disk_metrics.get(name)
            latency = latency_metrics.get(name)
            
            if cpu is not None:
                total_cpu += cpu
                count_cpu += 1
            if ram is not None:
                total_memory += ram
                count_mem += 1
            if disk is not None:
                total_disk += disk
                count_disk += 1
            
            servers.append({'name': display_name, 'cpu': cpu, 'ram': ram, 'disk': disk, 'latency': latency, 'status': status})
        
        if count_cpu > 0:
            cpu_history.append(round(total_cpu / count_cpu, 1))
        if count_mem > 0:
            memory_history.append(round(total_memory / count_mem, 1))
        if count_disk > 0:
            disk_history.append(round(total_disk / count_disk, 1))
            
        if len(cpu_history) > 20: cpu_history.pop(0)
        if len(memory_history) > 20: memory_history.pop(0)
        if len(disk_history) > 20: disk_history.pop(0)
        
        running_pods = sum(1 for pod in pods_data.get('items', []) if pod['status']['phase'] == 'Running')
        jenkins_jobs = scrape_jenkins_all_jobs()
        
        return jsonify({
            'health_status': 'OK' if servers else 'NOK',
            'active_servers': len(servers),
            'active_deployments': running_pods,
            'servers': servers,
            'jenkins_jobs': jenkins_jobs,
            'cpu_history': cpu_history,
            'memory_history': memory_history,
            'disk_history': disk_history,
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    print("="*60)
    print("SDOS Dashboard")
    print("="*60)
    print("Access: http://localhost:8080")
    print("Press Ctrl+C to stop")
    print("="*60)
    app.run(host='0.0.0.0', port=8080, debug=False)
