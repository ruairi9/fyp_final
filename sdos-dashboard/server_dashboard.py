from flask import Flask, render_template_string, jsonify, redirect
import subprocess
import json
import os
import re
import signal
import sys
import time

SESSION_FILE = os.path.expanduser('~/fyp-cluster/sdos-dashboard/.sdos_session')

def _get_session():
    try:
        if os.path.exists(SESSION_FILE):
            with open(SESSION_FILE) as f:
                return json.load(f)
    except Exception:
        pass
    return {}

app = Flask(__name__)

KUBECONFIG_PATH = os.path.expanduser('~/fyp-cluster/k3s.yaml')

_previous_network_bytes = 0
_previous_network_time = 0

def signal_handler(sig, frame):
    print('\n\n' + '='*60)
    print('Server Dashboard stopped')
    print('='*60)
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

def get_cluster_count():
    """Get real cluster count from kubeconfig"""
    try:
        result = subprocess.run(
            ['kubectl', 'config', 'get-contexts', '--no-headers',
             f'--kubeconfig={KUBECONFIG_PATH}'],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            lines = [l for l in result.stdout.strip().split('\n') if l.strip()]
            return len(lines)
        return 1
    except:
        return 1

def get_vm_cpu_ram_disk_io_steal(vagrant_name):
    try:
        result = subprocess.run(
            ['vagrant', 'ssh', vagrant_name, '-c',
             'top -bn1 | grep "Cpu(s)"; free | grep Mem; df -h / | tail -1; iostat -d -m 1 2 | grep vda | head -1'],
            capture_output=True, text=True, timeout=15,
            cwd=os.path.expanduser('~/fyp-cluster')
        )
        if result.returncode != 0:
            return {'cpu': 0.0, 'ram': 0.0, 'disk': 'N/A', 'disk_io': '0.00 MB/s', 'steal_time': '0.0%'}
        lines = result.stdout.strip().split('\n')
        cpu_usage = 0.0
        steal_time = 0.0
        if len(lines) > 0:
            cpu_line = lines[0]
            match = re.search(r'([\d.]+)\s+id', cpu_line)
            if match:
                idle = float(match.group(1))
                cpu_usage = round(100.0 - idle, 1)
            steal_match = re.search(r'([\d.]+)\s+st', cpu_line)
            if steal_match:
                steal_time = float(steal_match.group(1))
        ram_pct = 0.0
        if len(lines) > 1:
            ram_line = lines[1]
            parts = ram_line.split()
            if len(parts) >= 3 and parts[0] == 'Mem:':
                try:
                    total = float(parts[1])
                    used = float(parts[2])
                    if total > 0:
                        ram_pct = round((used / total) * 100.0, 1)
                except:
                    pass
        disk = 'N/A'
        if len(lines) > 2:
            disk_line = lines[2]
            parts = disk_line.split()
            if len(parts) >= 5:
                disk = parts[4]
        disk_io = '0.00 MB/s'
        if len(lines) > 3:
            io_line = lines[3].strip()
            if io_line and 'vda' in io_line:
                parts = io_line.split()
                if len(parts) >= 4:
                    try:
                        read_mb = float(parts[2])
                        write_mb = float(parts[3])
                        disk_io = f'{read_mb + write_mb:.2f} MB/s'
                    except Exception as e:
                        print(f"I/O parse error for {vagrant_name}: {e}")
        return {'cpu': cpu_usage, 'ram': ram_pct, 'disk': disk, 'disk_io': disk_io, 'steal_time': f'{steal_time}%'}
    except Exception as e:
        print(f"Error getting metrics for {vagrant_name}: {e}")
        return {'cpu': 0.0, 'ram': 0.0, 'disk': 'N/A', 'disk_io': '0.00 MB/s', 'steal_time': '0.0%'}

def get_vm_metrics():
    vms = {
        'control-plane': 'control-plane',
        'worker-dev-integration': 'worker-dev',
        'worker-production': 'worker-prod',
        'worker-cicd': 'worker-cicd',
        'worker-registry-monitoring': 'worker-monitoring'
    }
    vm_data = []
    for k3s_name, vagrant_name in vms.items():
        metrics = get_vm_cpu_ram_disk_io_steal(vagrant_name)
        vm_data.append({
            'name': k3s_name,
            'cpu': metrics['cpu'],
            'ram': metrics['ram'],
            'disk': metrics['disk'],
            'disk_io': metrics['disk_io'],
            'steal_time': metrics['steal_time'],
            'throughput': metrics['disk_io']
        })
    return vm_data

def get_host_stats():
    global _previous_network_bytes, _previous_network_time
    try:
        ram_result = subprocess.run(['free', '-m'], capture_output=True, text=True, timeout=3)
        total_ram = used_ram = swap_used = swap_total = 0
        if ram_result.returncode == 0:
            lines = ram_result.stdout.strip().split('\n')
            mem_line = [l for l in lines if 'Mem:' in l][0]
            parts = mem_line.split()
            total_ram = int(parts[1])
            used_ram  = int(parts[2])
            swap_line = [l for l in lines if 'Swap:' in l]
            if swap_line:
                swap_parts = swap_line[0].split()
                swap_total = int(swap_parts[1])
                swap_used  = int(swap_parts[2])
        ram_percent  = round((used_ram  / total_ram  * 100), 1) if total_ram  > 0 else 0
        swap_percent = round((swap_used / swap_total * 100), 1) if swap_total > 0 else 0

        cpu_result = subprocess.run(['top', '-bn1'], capture_output=True, text=True, timeout=3)
        cpu_percent = cpu_wait = 0
        cpu_steal = 0.0
        if cpu_result.returncode == 0:
            for line in cpu_result.stdout.split('\n'):
                if 'Cpu(s)' in line:
                    idle_match  = re.search(r'([\d.]+)\s*id', line)
                    wait_match  = re.search(r'([\d.]+)\s*wa', line)
                    steal_match = re.search(r'([\d.]+)\s*st', line)
                    if idle_match:
                        cpu_percent = round(100 - float(idle_match.group(1)), 1)
                    if wait_match:
                        cpu_wait = round(float(wait_match.group(1)), 1)
                    if steal_match:
                        cpu_steal = round(float(steal_match.group(1)), 1)
                    break

        disk_result = subprocess.run(['df', '-h', '/'], capture_output=True, text=True, timeout=3)
        disk_percent = 0
        if disk_result.returncode == 0:
            lines = disk_result.stdout.strip().split('\n')
            if len(lines) > 1:
                disk_percent = int(lines[1].split()[4].replace('%', ''))

        iostat_result = subprocess.run(
            ['iostat', '-x', '1', '1'],
            capture_output=True, text=True, timeout=5
        )
        disk_throughput = disk_iops = disk_latency = 0.0
        if iostat_result.returncode == 0:
            for line in iostat_result.stdout.split('\n'):
                parts = line.split()
                if not parts or parts[0].startswith('loop') or parts[0] in ('Device', 'Linux', 'avg-cpu:'):
                    continue
                if re.match(r'^(nvme|sd|vd|hd)', parts[0]) and len(parts) >= 12:
                    try:
                        disk_iops       = round(float(parts[1]) + float(parts[7]), 1)
                        disk_throughput = round((float(parts[2]) + float(parts[8])) / 1024, 2)
                        disk_latency    = round(float(parts[5]), 2)
                    except Exception as e:
                        print(f"iostat parse error: {e}")
                    break

        page_faults = 0
        try:
            with open('/proc/vmstat', 'r') as f:
                vmstat_data = f.read()
            pgfault = pgmajfault = 0
            for line in vmstat_data.split('\n'):
                if line.startswith('pgfault '):
                    pgfault = int(line.split()[1])
                elif line.startswith('pgmajfault '):
                    pgmajfault = int(line.split()[1])
            page_faults = (pgfault + pgmajfault) // 1000
        except:
            pass

        oom_events = 0
        try:
            dmesg_result = subprocess.run(
                ['sudo', 'dmesg'],
                capture_output=True, text=True, timeout=3
            )
            if dmesg_result.returncode == 0:
                oom_events = (
                    dmesg_result.stdout.count('Out of memory') +
                    dmesg_result.stdout.count('page allocation failure') +
                    dmesg_result.stdout.count('Memory cgroup out of memory')
                )
        except:
            pass

        cache_faults = 0
        try:
            perf_result = subprocess.run(
                ['perf', 'stat', '-e', 'cache-misses', '-a', 'sleep', '0.1'],
                capture_output=True, text=True, timeout=2
            )
            for line in perf_result.stderr.split('\n'):
                if 'cache-misses' in line:
                    parts = line.split()
                    if parts:
                        num = parts[0].replace(',', '').replace('.', '')
                        if num.isdigit():
                            cache_faults = int(num) // 1000
                            break
        except:
            pass

        network_traffic = 0.0
        try:
            current_time = time.time()
            with open('/proc/net/dev', 'r') as f:
                net_lines = f.readlines()
            current_bytes = 0
            for line in net_lines[2:]:
                if 'lo' not in line and ':' in line:
                    parts = line.split()
                    if len(parts) >= 10:
                        current_bytes = int(parts[1]) + int(parts[9])
                        break
            if _previous_network_bytes > 0 and _previous_network_time > 0:
                time_delta = current_time - _previous_network_time
                if time_delta > 0:
                    network_traffic = round(
                        ((current_bytes - _previous_network_bytes) / time_delta) / (1024 * 1024), 2
                    )
            _previous_network_bytes = current_bytes
            _previous_network_time  = current_time
        except:
            pass

        return {
            'ram_usage':      ram_percent,
            'ram_available':  round(100 - ram_percent, 1),
            'swap_usage':     swap_percent,
            'page_faults':    page_faults,
            'oom_events':     oom_events,
            'cache_faults':   cache_faults,
            'cpu_usage':      cpu_percent,
            'cpu_wait':       cpu_wait,
            'cpu_steal':      cpu_steal,
            'disk_usage':     disk_percent,
            'disk_throughput': disk_throughput,
            'disk_iops':      disk_iops,
            'disk_latency':   disk_latency,
            'network_traffic': network_traffic
        }
    except Exception as e:
        print(f"Error getting host stats: {e}")
        return {
            'ram_usage': 0, 'ram_available': 0, 'swap_usage': 0,
            'page_faults': 0, 'oom_events': 0, 'cache_faults': 0,
            'cpu_usage': 0, 'cpu_wait': 0, 'cpu_steal': 0,
            'disk_usage': 0, 'disk_throughput': 0, 'disk_iops': 0,
            'disk_latency': 0, 'network_traffic': 0
        }

def get_pod_count():
    try:
        result = subprocess.run(
            ['kubectl', 'get', 'pods', '--all-namespaces', '--no-headers',
             f'--kubeconfig={KUBECONFIG_PATH}'],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            return sum(1 for line in result.stdout.strip().split('\n') if 'Running' in line)
        return 0
    except:
        return 0

SERVER_DASHBOARD_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>SDOS Server Dashboard</title>
    <meta http-equiv="Cache-Control" content="no-cache">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Segoe UI', Arial, sans-serif; background: #1a1a1a; color: #ffffff; padding: 20px; }
        .container { max-width: 1600px; margin: 0 auto; }
        .header {
            background: #2d2d2d;
            padding: 20px 30px; border-radius: 15px; margin-bottom: 25px;
            display: flex; align-items: center;
            box-shadow: none; border-bottom: 4px solid #cc0000;
        }
        .header h1 { font-size: 32px; color: #ffffff; }
        .header-left { display: flex; align-items: center; gap: 20px; }
        .btn { background: #555555; color: white; border: none; padding: 10px 20px; border-radius: 8px; cursor: pointer; text-decoration: none; display: inline-block; transition: all 0.3s; }
        .btn:hover { background: #666666; transform: translateY(-1px); }
        .btn-home { background: #64748b; }
        .btn-home:hover { background: #555555; }
        .main-grid { display: grid; grid-template-columns: 280px 1fr; gap: 20px; }
        .sidebar { display: flex; flex-direction: column; gap: 20px; }
        .sidebar-card { background: #383838; border-radius: 12px; padding: 20px; box-shadow: 0 4px 20px rgba(0,0,0,0.3); border: 1px solid #555; }
        .sidebar-card h3 { color: #ffffff; margin-bottom: 15px; border-bottom: 2px solid #888; padding-bottom: 10px; font-size: 14px; }
        .stat-row { display: flex; justify-content: space-between; padding: 8px 0; font-size: 12px; border-bottom: 1px solid #888; }
        .stat-row:last-child { border-bottom: none; }
        .stat-label { color: #ffffff; }
        .stat-value { color: #ffffff; font-weight: 500; }
        .content-card { background: #383838; border-radius: 12px; padding: 20px; box-shadow: 0 4px 20px rgba(0,0,0,0.3); border: 1px solid #555; }
        .content-card h3 { color: #ffffff; margin-bottom: 15px; border-bottom: 2px solid #888; padding-bottom: 10px; font-size: 16px; }
        table { width: 100%; border-collapse: collapse; margin-bottom: 20px; }
        th { background: transparent; color: #ffffff; padding: 12px; text-align: left; font-size: 13px; font-weight: 600; border-bottom: 2px solid #888; }
        td { padding: 12px; border-bottom: 1px solid #888; font-size: 13px; color: #ffffff; }
        tr:hover { background: #4a4a4a; }
        .vm-name { color: #ffffff; cursor: pointer; }
        .vm-name:hover { text-decoration: underline; }
        .selected-section { padding: 12px 0; font-weight: bold; margin-bottom: 20px; color: #ffffff; border-bottom: 2px solid #555; }
        .charts-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 15px; }
        .chart-box { background: #2d2d2d; border: 1px solid #555; border-radius: 8px; padding: 15px; }
        .chart-title { font-weight: 600; font-size: 13px; margin-bottom: 10px; color: #ffffff; }
        .chart-svg { width: 100%; height: 140px; }
        .info-box { background: #2d2d2d; border: 1px solid #555; border-radius: 8px; padding: 20px; display: flex; flex-direction: column; justify-content: center; }
        .info-row { display: flex; justify-content: space-between; padding: 10px 0; font-size: 14px; border-bottom: 1px solid #4a4a4a; }
        .info-row:last-child { border-bottom: none; }
        .real-data { color: #ffffff; }
    </style>
</head>
<body>
<div style="background:#1a1a1a;min-height:100vh;padding:30px 0;">
<div style="background:#2d2d2d;max-width:1500px;margin:0 auto;padding:30px;border-radius:8px;box-shadow:0 2px 10px rgba(0,0,0,0.4);">
    <div class="container">
        <div class="header">
            <div class="header-left">
                <a href="http://localhost:5000" class="btn btn-home">← Home</a>
                <button onclick="logout()" style="background:#ef4444;color:white;border:none;padding:8px 18px;border-radius:8px;cursor:pointer;font-size:13px;font-weight:600;transition:all 0.3s;" onmouseover="this.style.background=\'#dc2626\';this.style.transform=\'translateY(-2px)\'" onmouseout="this.style.background=\'#ef4444\';this.style.transform=\'translateY(0)\'">Logout</button>
                <h1 style="color:white;" style="color:white;">Server Dashboard</h1>
            </div>
        </div>

        <div class="main-grid">
            <div class="sidebar">
                <div class="sidebar-card">
                    <h3>RAM STATUS</h3>
                    <div class="stat-row"><span class="stat-label">Total RAM Usage</span><span class="stat-value real-data" id="ram-usage">-</span></div>
                    <div class="stat-row"><span class="stat-label">Available Memory</span><span class="stat-value real-data" id="ram-available">-</span></div>
                    <div class="stat-row"><span class="stat-label">Swap Usage</span><span class="stat-value real-data" id="swap-usage">-</span></div>
                    <div class="stat-row"><span class="stat-label">Page Faults Total</span><span class="stat-value real-data" id="page-faults">-</span></div>
                    <div class="stat-row"><span class="stat-label">OOM Events</span><span class="stat-value real-data" id="oom-events">-</span></div>
                    <div class="stat-row"><span class="stat-label">Cache Faults</span><span class="stat-value real-data" id="cache-faults">-</span></div>
                </div>
                <div class="sidebar-card">
                    <h3>CPU STATUS</h3>
                    <div class="stat-row"><span class="stat-label">CPU Utilisation</span><span class="stat-value real-data" id="cpu-usage">-</span></div>
                    <div class="stat-row"><span class="stat-label">CPU Steal Time</span><span class="stat-value real-data" id="cpu-steal">-</span></div>
                    <div class="stat-row"><span class="stat-label">I/O Waits</span><span class="stat-value real-data" id="cpu-wait">-</span></div>
                </div>
                <div class="sidebar-card">
                    <h3>DISK & STORAGE</h3>
                    <div class="stat-row"><span class="stat-label">Disk Usage</span><span class="stat-value real-data" id="disk-usage">-</span></div>
                    <div class="stat-row"><span class="stat-label">I/O Throughput</span><span class="stat-value real-data" id="disk-throughput">-</span></div>
                    <div class="stat-row"><span class="stat-label">Disk IOPS</span><span class="stat-value real-data" id="disk-iops">-</span></div>
                    <div class="stat-row"><span class="stat-label">Disk Latency</span><span class="stat-value real-data" id="disk-latency">-</span></div>
                </div>
            </div>

            <div class="content-card">
                <h3>VM LIST</h3>
                <table id="vm-table">
                    <thead>
                        <tr>
                            <th>Name</th><th>vCPU %</th><th>RAM %</th>
                            <th>Disk Usage</th><th>Steal Time</th><th>Disk I/O</th>
                        </tr>
                    </thead>
                    <tbody><tr><td colspan="6">Loading...</td></tr></tbody>
                </table>
                <div id="selected-vm-label" style="padding: 12px 0; margin-bottom: 15px; font-size: 16px; font-weight: 600; color: #ffffff; border-bottom: 2px solid #888;">Selected VM: -</div>
                <div class="charts-grid">
                    <div class="chart-box"><div class="chart-title">CPU Utilisation</div><svg class="chart-svg" id="cpu-chart"></svg></div>
                    <div class="chart-box"><div class="chart-title">Memory Usage</div><svg class="chart-svg" id="memory-chart"></svg></div>
                    <div class="chart-box"><div class="chart-title">Disk I/O</div><svg class="chart-svg" id="disk-chart"></svg></div>
                    <div class="chart-box"><div class="chart-title">Disk Latency</div><svg class="chart-svg" id="latency-chart"></svg></div>
                    <div class="chart-box"><div class="chart-title">Network Traffic</div><svg class="chart-svg" id="network-chart"></svg></div>
                    <div class="info-box">
                        <div class="info-row"><span style="font-weight:bold;color:#ffffff;">PODs</span><span id="pod-count" class="real-data">-</span></div>
                        <div class="info-row"><span style="font-weight:bold;color:#ffffff;">CLUSTERS</span><span id="cluster-count" class="real-data">-</span></div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script>
        const allVMData = {};
        let selectedVM = null;
        const chartData = { cpu: [], memory: [], diskIO: [], latency: [], network: [] };

        function drawChart(elementId, dataPoints, color, yLabel, maxY, loading = false) {
            const svg = document.getElementById(elementId);
            const width = svg.clientWidth || 300;
            const height = 140;
            const padding = 40;
            if (loading || !dataPoints || dataPoints.length < 1) {
                svg.innerHTML = '<text x="' + (width/2) + '" y="' + (height/2) + '" fill="#94a3b8" font-size="14" text-anchor="middle">Collecting data...</text>';
                return;
            }
            if (dataPoints.length === 1) dataPoints = [dataPoints[0], dataPoints[0]];
            if (maxY <= 0) maxY = 1;
            const numPoints = dataPoints.length;
            const points = dataPoints.map((v, i) => {
                const x = padding + (i / Math.max(numPoints - 1, 1)) * (width - 2 * padding);
                const y = padding + (1 - v / maxY) * (height - 2 * padding);
                return x + ',' + y;
            });
            svg.innerHTML =
                '<polyline points="' + points.join(' ') + '" fill="none" stroke="' + color + '" stroke-width="2"/>' +
                '<line x1="' + padding + '" y1="' + (height-padding) + '" x2="' + (width-padding) + '" y2="' + (height-padding) + '" stroke="#475569" stroke-width="1"/>' +
                '<line x1="' + padding + '" y1="' + padding + '" x2="' + padding + '" y2="' + (height-padding) + '" stroke="#475569" stroke-width="1"/>' +
                '<text x="5" y="' + (padding-5) + '" fill="#94a3b8" font-size="10">' + Math.round(maxY) + '</text>' +
                '<text x="5" y="' + (height-padding+15) + '" fill="#94a3b8" font-size="10">0</text>' +
                '<text x="10" y="' + (height/2) + '" fill="#94a3b8" font-size="11" transform="rotate(-90 10 ' + (height/2) + ')">' + yLabel + '</text>';
        }

        function selectVM(vmName, vmData) {
            selectedVM = vmName;
            document.getElementById('selected-vm-label').textContent = 'Selected VM: ' + vmName;

            if (!allVMData[vmName]) {
                allVMData[vmName] = { cpu: [], memory: [], diskIO: [], latency: [], network: [] };
            }

            if (vmData) {
                allVMData[vmName].cpu.push(vmData.cpu);
                allVMData[vmName].memory.push(vmData.ram);
                allVMData[vmName].diskIO.push(parseFloat(vmData.disk_io) || 0);
                ['cpu','memory','diskIO','latency','network'].forEach(k => {
                    if (allVMData[vmName][k].length > 20) allVMData[vmName][k].shift();
                });
            }

            const d = allVMData[vmName];
            drawChart('cpu-chart',    d.cpu,    '#60a5fa', 'CPU %', 100, false);
            drawChart('memory-chart', d.memory, '#22c55e', 'RAM %', 100, false);
            drawChart('disk-chart',   d.diskIO, '#f59e0b', 'MB/s', Math.max(...d.diskIO, 1), false);
            drawChart('latency-chart', d.latency, '#8b5cf6', 'ms', Math.max(...d.latency, 10), false);
            drawChart('network-chart', d.network, '#ef4444', 'MB/s', Math.max(...d.network, 1), false);
        }

        async function fetchData() {
            try {
                const data = await (await fetch('/api/server-data')).json();
                document.getElementById('ram-usage').textContent       = data.host_stats.ram_usage + '%';
                document.getElementById('ram-available').textContent   = data.host_stats.ram_available + '%';
                document.getElementById('swap-usage').textContent      = data.host_stats.swap_usage + '%';
                document.getElementById('page-faults').textContent     = data.host_stats.page_faults;
                document.getElementById('oom-events').textContent      = data.host_stats.oom_events;
                document.getElementById('cache-faults').textContent    = data.host_stats.cache_faults;
                document.getElementById('cpu-usage').textContent       = data.host_stats.cpu_usage + '%';
                document.getElementById('cpu-wait').textContent        = data.host_stats.cpu_wait + '%';
                document.getElementById('cpu-steal').textContent       = data.host_stats.cpu_steal + '%';
                document.getElementById('disk-usage').textContent      = data.host_stats.disk_usage + '%';
                document.getElementById('disk-throughput').textContent = data.host_stats.disk_throughput + ' MB/s';
                document.getElementById('disk-iops').textContent       = data.host_stats.disk_iops + '/sec';
                document.getElementById('disk-latency').textContent    = data.host_stats.disk_latency + ' ms';

                document.getElementById('pod-count').textContent       = data.pod_count;
                document.getElementById('cluster-count').textContent   = data.cluster_count;

                chartData.cpu.push(data.host_stats.cpu_usage);
                chartData.memory.push(data.host_stats.ram_usage);
                chartData.diskIO.push(data.host_stats.disk_throughput);
                chartData.latency.push(data.host_stats.disk_latency);
                chartData.network.push(data.host_stats.network_traffic || 0);
                ['cpu','memory','diskIO','latency','network'].forEach(k => { if (chartData[k].length > 20) chartData[k].shift(); });

                drawChart('cpu-chart',     chartData.cpu,     '#60a5fa', 'CPU %', 100, false);
                drawChart('memory-chart',  chartData.memory,  '#22c55e', 'RAM %', 100, false);
                drawChart('disk-chart',    chartData.diskIO,  '#f59e0b', 'MB/s',  Math.max(...chartData.diskIO, 1),   false);
                drawChart('latency-chart', chartData.latency, '#8b5cf6', 'ms',    Math.max(...chartData.latency, 10), false);
                drawChart('network-chart', chartData.network, '#ef4444', 'MB/s',  Math.max(...chartData.network, 1),  false);

                const tbody = document.querySelector('#vm-table tbody');
                tbody.innerHTML = '';
                data.vms.forEach(vm => {
                    if (!allVMData[vm.name]) {
                        allVMData[vm.name] = { cpu: [], memory: [], diskIO: [], latency: [], network: [] };
                    }
                    allVMData[vm.name].cpu.push(vm.cpu);
                    allVMData[vm.name].memory.push(vm.ram);
                    allVMData[vm.name].diskIO.push(parseFloat(vm.disk_io) || 0);
                    allVMData[vm.name].latency.push(data.host_stats.disk_latency || 0.1);
                    allVMData[vm.name].network.push(data.host_stats.network_traffic || 0.0);
                    ['cpu','memory','diskIO','latency','network'].forEach(k => {
                        if (allVMData[vm.name][k].length > 20) allVMData[vm.name][k].shift();
                    });

                    const row = tbody.insertRow();
                    row.style.cursor = 'pointer';
                    const isSelected = vm.name === selectedVM;
                    if (isSelected) row.style.background = '#4a4a4a';
                    row.innerHTML =
                        '<td><span class="vm-name">' + vm.name + '</span></td>' +
                        '<td style="color:#ffffff;">' + vm.cpu + '%</td>' +
                        '<td style="color:#ffffff;">' + vm.ram + '%</td>' +
                        '<td style="color:#ffffff;">' + vm.disk + '</td>' +
                        '<td style="color:#ffffff;">' + vm.steal_time + '</td>' +
                        '<td style="color:#ffffff;">' + vm.disk_io + '</td>';
                    row.addEventListener('click', () => selectVM(vm.name, null));
                    if (!selectedVM && data.vms.indexOf(vm) === 0) {
                        selectedVM = vm.name;
                    }
                });

                if (selectedVM && allVMData[selectedVM]) {
                    document.getElementById('selected-vm-label').textContent = 'Selected VM: ' + selectedVM;
                    const d = allVMData[selectedVM];
                    drawChart('cpu-chart',    d.cpu,    '#60a5fa', 'CPU %', 100, false);
                    drawChart('memory-chart', d.memory, '#22c55e', 'RAM %', 100, false);
                    drawChart('disk-chart',   d.diskIO, '#f59e0b', 'MB/s', Math.max(...d.diskIO, 1), false);
                    drawChart('latency-chart', d.latency, '#8b5cf6', 'ms', Math.max(...d.latency, 10), false);
                    drawChart('network-chart', d.network, '#ef4444', 'MB/s', Math.max(...d.network, 1), false);
                }
            } catch (error) {
                console.error('Error fetching data:', error);
            }
        }

        async function logout() {
            await fetch('http://localhost:5000/api/logout', { method: 'POST' });
            window.location.href = 'http://localhost:5000';
        }

        setInterval(async function() {
            try {
                const res = await fetch('http://localhost:5000/api/check-session');
                const data = await res.json();
                if (!data.logged_in) window.location.href = 'http://localhost:5000';
            } catch(e) {}
        }, 30000);

        drawChart('cpu-chart',     [], '#60a5fa', 'CPU %', 100, true);
        drawChart('memory-chart',  [], '#22c55e', 'RAM %', 100, true);
        drawChart('disk-chart',    [], '#f59e0b', 'MB/s',  1,   true);
        drawChart('latency-chart', [], '#8b5cf6', 'ms',    10,  true);
        drawChart('network-chart', [], '#ef4444', 'MB/s',  1,   true);

        fetchData();
        setInterval(fetchData, 5000);
    </script>
    </div>
    </div>
</div></div></body>
</html>
'''

@app.route('/')
def server_dashboard():
    if not _get_session().get('logged_in'):
        return redirect('http://localhost:5000')
    return render_template_string(SERVER_DASHBOARD_TEMPLATE)

@app.route('/api/server-data')
def get_server_data():
    try:
        return jsonify({
            'host_stats':    get_host_stats(),
            'vms':           get_vm_metrics(),
            'pod_count':     get_pod_count(),
            'cluster_count': get_cluster_count()
        })
    except Exception as e:
        print(f"Error: {e}")
        import traceback; traceback.print_exc()
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    import logging
    logging.getLogger('werkzeug').setLevel(logging.ERROR)
    print("="*60)
    print("SDOS Server Dashboard")
    print("="*60)
    print("Access: http://localhost:9000")
    print("Press Ctrl+C to stop")
    print("="*60)
    try:
        app.run(host='0.0.0.0', port=9000, debug=False, threaded=True, use_reloader=False)
    except KeyboardInterrupt:
        print("\n" + "="*60)
        print("Server Dashboard stopped")
        print("="*60)
        sys.exit(0)
