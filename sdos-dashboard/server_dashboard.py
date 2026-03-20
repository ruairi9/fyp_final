from flask import Flask, render_template_string, jsonify
import subprocess
import json
import os
import re
import signal
import sys
import time

app = Flask(__name__)

KUBECONFIG_PATH = os.path.expanduser('~/fyp-cluster/k3s.yaml')

# Global variables to track previous network bytes for rate calculation
_previous_network_bytes = 0
_previous_network_time = 0

def signal_handler(sig, frame):
    print('\n\n' + '='*60)
    print('Server Dashboard stopped')
    print('='*60)
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

def get_vm_cpu_ram_disk_io_steal(vagrant_name):
    """Get CPU, RAM, Disk, Disk I/O, and Steal Time"""
    try:
        result = subprocess.run(
            ['vagrant', 'ssh', vagrant_name, '-c', 
             'top -bn1 | grep "Cpu(s)"; free | grep Mem; df -h / | tail -1; iostat -d -m 1 2 | grep vda | tail -1'],
            capture_output=True,
            text=True,
            timeout=15,
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
                        total_io = read_mb + write_mb
                        disk_io = f'{total_io:.2f} MB/s'
                    except Exception as e:
                        print(f"I/O parse error for {vagrant_name}: {e}")
                        disk_io = '0.00 MB/s'
        
        return {
            'cpu': cpu_usage,
            'ram': ram_pct,
            'disk': disk,
            'disk_io': disk_io,
            'steal_time': f'{steal_time}%'
        }
        
    except Exception as e:
        print(f"Error getting metrics for {vagrant_name}: {e}")
        return {'cpu': 0.0, 'ram': 0.0, 'disk': 'N/A', 'disk_io': '0.00 MB/s', 'steal_time': '0.0%'}

def get_vm_metrics():
    """Get real metrics for each VM"""
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
    """Get host server statistics"""
    global _previous_network_bytes, _previous_network_time
    
    try:
        ram_result = subprocess.run(['free', '-m'], capture_output=True, text=True, timeout=3)
        
        total_ram = 0
        used_ram = 0
        swap_used = 0
        swap_total = 0
        
        if ram_result.returncode == 0:
            lines = ram_result.stdout.strip().split('\n')
            mem_line = [l for l in lines if 'Mem:' in l][0]
            parts = mem_line.split()
            total_ram = int(parts[1])
            used_ram = int(parts[2])
            
            swap_line = [l for l in lines if 'Swap:' in l]
            if swap_line:
                swap_parts = swap_line[0].split()
                swap_total = int(swap_parts[1])
                swap_used = int(swap_parts[2])
        
        ram_percent = round((used_ram / total_ram * 100), 1) if total_ram > 0 else 0
        swap_percent = round((swap_used / swap_total * 100), 1) if swap_total > 0 else 0
        
        cpu_result = subprocess.run(['top', '-bn1'], capture_output=True, text=True, timeout=3)
        
        cpu_percent = 0
        cpu_wait = 0
        cpu_steal = 0.0
        
        if cpu_result.returncode == 0:
            for line in cpu_result.stdout.split('\n'):
                if 'Cpu(s)' in line:
                    idle_match = re.search(r'([\d.]+)\s*id', line)
                    wait_match = re.search(r'([\d.]+)\s*wa', line)
                    steal_match = re.search(r'([\d.]+)\s*st', line)
                    
                    if idle_match:
                        idle = float(idle_match.group(1))
                        cpu_percent = round(100 - idle, 1)
                    if wait_match:
                        cpu_wait = float(wait_match.group(1))
                    if steal_match:
                        cpu_steal = float(steal_match.group(1))
                    break
        
        cpu_ready = 0.0
        
        disk_result = subprocess.run(['df', '-h', '/'], capture_output=True, text=True, timeout=3)
        
        disk_percent = 0
        if disk_result.returncode == 0:
            lines = disk_result.stdout.strip().split('\n')
            if len(lines) > 1:
                parts = lines[1].split()
                disk_str = parts[4].replace('%', '')
                disk_percent = int(disk_str)
        
        iostat_result = subprocess.run(['iostat', '-d', '-x', '1', '1'], capture_output=True, text=True, timeout=3)
        
        disk_throughput = 0
        disk_iops = 0
        disk_latency = 0.0
        
        if iostat_result.returncode == 0:
            lines = iostat_result.stdout.strip().split('\n')
            for i, line in enumerate(lines):
                if 'Device' in line:
                    # Find first real disk (skip loop devices)
                    for j in range(i + 1, len(lines)):
                        data_line = lines[j].strip()
                        if data_line and not data_line.split()[0].startswith('loop'):
                            parts = data_line.split()
                            if len(parts) >= 14:
                                disk_iops = float(parts[3]) + float(parts[4])
                                disk_throughput = (float(parts[5]) + float(parts[6])) / 1024
                                disk_latency = float(parts[9])
                            break
                    break
        
        # Page Faults Total
        page_faults = 0
        try:
            with open('/proc/vmstat', 'r') as f:
                vmstat_data = f.read()
            pgfault = 0
            pgmajfault = 0
            for line in vmstat_data.split('\n'):
                if line.startswith('pgfault '):
                    pgfault = int(line.split()[1])
                elif line.startswith('pgmajfault '):
                    pgmajfault = int(line.split()[1])
            page_faults = (pgfault + pgmajfault) // 1000
        except:
            page_faults = 0
        
        # OOM Events (from dmesg)
        oom_events = 0
        try:
            dmesg_result = subprocess.run(['sudo', 'dmesg'], capture_output=True, text=True, timeout=3)
            if dmesg_result.returncode == 0:
                oom_kills = dmesg_result.stdout.count('Out of memory')
                alloc_failures = dmesg_result.stdout.count('page allocation failure')
                mem_pressure = dmesg_result.stdout.count('Memory cgroup out of memory')
                
                oom_events = oom_kills + alloc_failures + mem_pressure
        except:
            oom_events = 0
        
        # Cache Faults
        cache_faults = 0
        try:
            perf_result = subprocess.run(
                ['perf', 'stat', '-e', 'cache-misses', '-a', 'sleep', '0.1'],
                capture_output=True,
                text=True,
                timeout=2
            )
            if perf_result.returncode == 0 or perf_result.stderr:
                for line in perf_result.stderr.split('\n'):
                    if 'cache-misses' in line:
                        parts = line.split()
                        if parts:
                            num = parts[0].replace(',', '').replace('.', '')
                            if num.isdigit():
                                cache_faults = int(num)
                                break
        except:
            cache_faults = 0

        # Network traffic (MB/s rate, not cumulative)
        network_traffic = 0.0
        try:
            current_time = time.time()
            with open('/proc/net/dev', 'r') as f:
                lines = f.readlines()
            current_bytes = 0
            for line in lines[2:]:
                if 'lo' not in line and ':' in line:
                    parts = line.split()
                    if len(parts) >= 10:
                        rx_bytes = int(parts[1])
                        tx_bytes = int(parts[9])
                        current_bytes = rx_bytes + tx_bytes
                        break
            
            # Calculate MB/s rate
            if _previous_network_bytes > 0 and _previous_network_time > 0:
                bytes_delta = current_bytes - _previous_network_bytes
                time_delta = current_time - _previous_network_time
                if time_delta > 0:
                    network_traffic = (bytes_delta / time_delta) / (1024 * 1024)  # MB/s
            
            _previous_network_bytes = current_bytes
            _previous_network_time = current_time
        except:
            network_traffic = 0.0

        return {
            'ram_usage': ram_percent,
            'ram_available': round(100 - ram_percent, 1),
            'swap_usage': swap_percent,
            'page_faults': page_faults,
            'oom_events': oom_events,
            'cache_faults': cache_faults,
            'cpu_usage': cpu_percent,
            'cpu_wait': cpu_wait,
            'cpu_steal': cpu_steal,
            'cpu_ready': cpu_ready,
            'disk_usage': disk_percent,
            'disk_throughput': round(disk_throughput, 2),
            'disk_iops': round(disk_iops, 1),
            'disk_latency': round(disk_latency, 2),
            'network_traffic': round(network_traffic, 2)
        }
    except Exception as e:
        print(f"Error getting host stats: {e}")
        return {
            'ram_usage': 0,
            'ram_available': 0,
            'swap_usage': 0,
            'page_faults': 0,
            'oom_events': 0,
            'cache_faults': 0,
            'cpu_usage': 0,
            'cpu_wait': 0,
            'cpu_steal': 0,
            'cpu_ready': 0,
            'disk_usage': 0,
            'disk_throughput': 0,
            'disk_iops': 0,
            'disk_latency': 0,
            'network_traffic': 0
        }

def get_pod_count():
    """Get number of running pods"""
    try:
        result = subprocess.run(
            ['kubectl', 'get', 'pods', '--all-namespaces', '--no-headers', f'--kubeconfig={KUBECONFIG_PATH}'],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if result.returncode == 0:
            lines = result.stdout.strip().split('\n')
            running = sum(1 for line in lines if 'Running' in line)
            return running
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
        body { 
            font-family: 'Segoe UI', Arial, sans-serif; 
            background: #0f172a; 
            color: #e2e8f0; 
            padding: 20px;
        }
        .container { max-width: 1600px; margin: 0 auto; }
        .header {
            background: linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%);
            padding: 20px 30px;
            border-radius: 15px;
            margin-bottom: 25px;
            display: flex;
            align-items: center;
            box-shadow: 0 8px 32px rgba(59, 130, 246, 0.3);
        }
        .header h1 { font-size: 32px; }
        .header-left { display: flex; align-items: center; gap: 20px; }
        .btn { 
            background: #3b82f6; 
            color: white; 
            border: none; 
            padding: 10px 20px; 
            border-radius: 8px; 
            cursor: pointer; 
            text-decoration: none; 
            display: inline-block; 
            transition: all 0.3s; 
        }
        .btn:hover { background: #2563eb; transform: translateY(-1px); }
        .btn-home { background: #64748b; }
        .btn-home:hover { background: #475569; }
        .main-grid { display: grid; grid-template-columns: 280px 1fr; gap: 20px; }
        .sidebar { display: flex; flex-direction: column; gap: 20px; }
        .sidebar-card {
            background: #1e293b;
            border-radius: 12px;
            padding: 20px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.3);
            border: 1px solid #334155;
        }
        .sidebar-card h3 {
            color: #60a5fa;
            margin-bottom: 15px;
            border-bottom: 2px solid #3b82f6;
            padding-bottom: 10px;
            font-size: 14px;
        }
        .stat-row {
            display: flex;
            justify-content: space-between;
            padding: 8px 0;
            font-size: 12px;
            border-bottom: 1px solid #334155;
        }
        .stat-row:last-child { border-bottom: none; }
        .stat-label { color: #94a3b8; }
        .stat-value { color: #e2e8f0; font-weight: 500; }
        .content-card {
            background: #1e293b;
            border-radius: 12px;
            padding: 20px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.3);
            border: 1px solid #334155;
        }
        .content-card h3 {
            color: #60a5fa;
            margin-bottom: 15px;
            border-bottom: 2px solid #3b82f6;
            padding-bottom: 10px;
            font-size: 16px;
        }
        table { width: 100%; border-collapse: collapse; margin-bottom: 20px; }
        th {
            background: #0f172a;
            color: #60a5fa;
            padding: 12px;
            text-align: left;
            font-size: 13px;
            font-weight: 600;
        }
        td {
            padding: 12px;
            border-bottom: 1px solid #334155;
            font-size: 13px;
            color: #cbd5e1;
        }
        tr:hover { background: #334155; }
        .vm-name { color: #3b82f6; cursor: pointer; }
        .vm-name:hover { text-decoration: underline; }
        .selected-section {
            background: #334155;
            padding: 12px;
            border-radius: 8px;
            font-weight: bold;
            margin-bottom: 20px;
            color: #60a5fa;
        }
        .charts-grid {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 15px;
        }
        .chart-box {
            background: #0f172a;
            border: 1px solid #334155;
            border-radius: 8px;
            padding: 15px;
        }
        .chart-title {
            font-weight: 600;
            font-size: 13px;
            margin-bottom: 10px;
            color: #94a3b8;
        }
        .chart-svg { width: 100%; height: 140px; }
        .info-box {
            background: #0f172a;
            border: 1px solid #334155;
            border-radius: 8px;
            padding: 20px;
            display: flex;
            flex-direction: column;
            justify-content: center;
        }
        .info-row {
            display: flex;
            justify-content: space-between;
            padding: 10px 0;
            font-size: 14px;
            border-bottom: 1px solid #334155;
        }
        .info-row:last-child { border-bottom: none; }
        .real-data { color: #22c55e; }
        .placeholder-data { color: #f59e0b; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="header-left">
                <a href="http://localhost:5000" class="btn btn-home">← Home</a>
                <h1>Server Dashboard</h1>
            </div>
        </div>

        <div class="main-grid">
            <div class="sidebar">
                <div class="sidebar-card">
                    <h3>RAM STATUS</h3>
                    <div class="stat-row">
                        <span class="stat-label">Total RAM Usage</span>
                        <span class="stat-value real-data" id="ram-usage">-</span>
                    </div>
                    <div class="stat-row">
                        <span class="stat-label">Available Memory</span>
                        <span class="stat-value real-data" id="ram-available">-</span>
                    </div>
                    <div class="stat-row">
                        <span class="stat-label">Swap Usage</span>
                        <span class="stat-value real-data" id="swap-usage">-</span>
                    </div>
                    <div class="stat-row">
                        <span class="stat-label">Page Faults Total</span>
                        <span class="stat-value real-data" id="page-faults">-</span>
                    </div>
                    <div class="stat-row">
                        <span class="stat-label">OOM Events</span>
                        <span class="stat-value real-data" id="oom-events">-</span>
                    </div>
                    <div class="stat-row">
                        <span class="stat-label">Cache Faults</span>
                        <span class="stat-value real-data" id="cache-faults">-</span>
                    </div>
                </div>

                <div class="sidebar-card">
                    <h3>CPU STATUS</h3>
                    <div class="stat-row">
                        <span class="stat-label">CPU Utilisation</span>
                        <span class="stat-value real-data" id="cpu-usage">-</span>
                    </div>
                    <div class="stat-row">
                        <span class="stat-label">CPU Steal Time</span>
                        <span class="stat-value real-data" id="cpu-steal">-</span>
                    </div>
                    <div class="stat-row">
                        <span class="stat-label">I/O Waits</span>
                        <span class="stat-value real-data" id="cpu-wait">-</span>
                    </div>
                    <div class="stat-row">
                        <span class="stat-label">CPU Ready Time</span>
                        <span class="stat-value real-data" id="cpu-ready">-</span>
                    </div>
                </div>

                <div class="sidebar-card">
                    <h3>DISK & STORAGE</h3>
                    <div class="stat-row">
                        <span class="stat-label">Disk Usage</span>
                        <span class="stat-value real-data" id="disk-usage">-</span>
                    </div>
                    <div class="stat-row">
                        <span class="stat-label">I/O Throughput</span>
                        <span class="stat-value real-data" id="disk-throughput">-</span>
                    </div>
                    <div class="stat-row">
                        <span class="stat-label">Disk IOPS</span>
                        <span class="stat-value real-data" id="disk-iops">-</span>
                    </div>
                    <div class="stat-row">
                        <span class="stat-label">Disk Latency</span>
                        <span class="stat-value real-data" id="disk-latency">-</span>
                    </div>
                    <div class="stat-row">
                        <span class="stat-label">I/O Waits</span>
                        <span class="stat-value real-data" id="io-wait">-</span>
                    </div>
                </div>
            </div>

            <div class="content-card">
                <h3>VM LIST</h3>
                
                <table id="vm-table">
                    <thead>
                        <tr>
                            <th>Name</th>
                            <th>vCPU %</th>
                            <th>RAM %</th>
                            <th>Disk Usage</th>
                            <th>Steal Time</th>
                            <th>Disk I/O</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr><td colspan="6">Loading...</td></tr>
                    </tbody>
                </table>

                <div class="selected-section">Selected VM: control-plane</div>

                <div class="charts-grid">
                    <div class="chart-box">
                        <div class="chart-title">CPU Utilisation</div>
                        <svg class="chart-svg" id="cpu-chart"></svg>
                    </div>
                    <div class="chart-box">
                        <div class="chart-title">Memory Usage</div>
                        <svg class="chart-svg" id="memory-chart"></svg>
                    </div>
                    <div class="chart-box">
                        <div class="chart-title">Disk I/O</div>
                        <svg class="chart-svg" id="disk-chart"></svg>
                    </div>
                    <div class="chart-box">
                        <div class="chart-title">Disk Latency</div>
                        <svg class="chart-svg" id="latency-chart"></svg>
                    </div>
                    <div class="chart-box">
                        <div class="chart-title">Network Traffic</div>
                        <svg class="chart-svg" id="network-chart"></svg>
                    </div>
                    <div class="info-box">
                        <div class="info-row">
                            <span style="font-weight: bold; color: #60a5fa;">PODs</span>
                            <span id="pod-count" class="real-data">-</span>
                        </div>
                        <div class="info-row">
                            <span style="font-weight: bold; color: #60a5fa;">CLUSTERS</span>
                            <span class="real-data">1</span>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script>
        // Store historical data for charts (last 20 data points)
        const chartData = {
            cpu: [],
            memory: [],
            diskIO: [],
            latency: [],
            network: []
        };
        
        function drawChart(elementId, dataPoints, color, yLabel, maxY, loading = false) {
            const svg = document.getElementById(elementId);
            const width = svg.clientWidth || 300;
            const height = 140;
            const padding = 40;
            
            // Show loading message if no data or less than 2 points
            if (loading || !dataPoints || dataPoints.length < 2) {
                svg.innerHTML = 
                    '<text x="' + (width / 2) + '" y="' + (height / 2) + '" fill="#94a3b8" font-size="14" text-anchor="middle">Collecting data...</text>';
                return;
            }
            
            const points = [];
            const numPoints = dataPoints.length;
            
            for (let i = 0; i < numPoints; i++) {
                const x = padding + (i / Math.max(numPoints - 1, 1)) * (width - 2 * padding);
                const value = dataPoints[i];
                const y = padding + (1 - value / maxY) * (height - 2 * padding);
                points.push(x + ',' + y);
            }
            
            const maxVal = maxY;  // Use fixed Y-axis max
            
            svg.innerHTML = 
                '<polyline points="' + points.join(' ') + '" fill="none" stroke="' + color + '" stroke-width="2"/>' +
                '<line x1="' + padding + '" y1="' + (height - padding) + '" x2="' + (width - padding) + '" y2="' + (height - padding) + '" stroke="#475569" stroke-width="1"/>' +
                '<line x1="' + padding + '" y1="' + padding + '" x2="' + padding + '" y2="' + (height - padding) + '" stroke="#475569" stroke-width="1"/>' +
                '<text x="5" y="' + (padding - 5) + '" fill="#94a3b8" font-size="10">' + Math.round(maxVal) + '</text>' +
                '<text x="5" y="' + (height - padding + 15) + '" fill="#94a3b8" font-size="10">0</text>' +
                '<text x="' + (padding - 10) + '" y="' + (height - padding + 20) + '" fill="#94a3b8" font-size="10">0s</text>' +
                '<text x="' + (width - padding - 20) + '" y="' + (height - padding + 20) + '" fill="#94a3b8" font-size="10">' + ((numPoints - 1) * 5) + 's</text>' +
                '<text x="10" y="' + (height / 2) + '" fill="#94a3b8" font-size="11" transform="rotate(-90 10 ' + (height / 2) + ')">' + yLabel + '</text>';
        }
        
        async function fetchData() {
            try {
                const data = await (await fetch('/api/server-data')).json();
                
                // Update sidebar stats
                document.getElementById('ram-usage').textContent = data.host_stats.ram_usage + '%';
                document.getElementById('ram-available').textContent = data.host_stats.ram_available + '%';
                document.getElementById('swap-usage').textContent = data.host_stats.swap_usage + '%';
                document.getElementById('page-faults').textContent = data.host_stats.page_faults;
                document.getElementById('oom-events').textContent = data.host_stats.oom_events;
                document.getElementById('cache-faults').textContent = data.host_stats.cache_faults;
                document.getElementById('cpu-usage').textContent = data.host_stats.cpu_usage + '%';
                document.getElementById('cpu-wait').textContent = data.host_stats.cpu_wait + '%';
                document.getElementById('cpu-steal').textContent = data.host_stats.cpu_steal + '%';
                document.getElementById('cpu-ready').textContent = data.host_stats.cpu_ready + '%';
                document.getElementById('disk-usage').textContent = data.host_stats.disk_usage + '%';
                document.getElementById('disk-throughput').textContent = data.host_stats.disk_throughput + ' MB/s';
                document.getElementById('disk-iops').textContent = data.host_stats.disk_iops + '/sec';
                document.getElementById('disk-latency').textContent = data.host_stats.disk_latency + ' ms';
                document.getElementById('io-wait').textContent = data.host_stats.cpu_wait + '%';
                document.getElementById('pod-count').textContent = data.pod_count;
                
                // Update chart data (keep last 20 points)
                chartData.cpu.push(data.host_stats.cpu_usage);
                chartData.memory.push(data.host_stats.ram_usage);
                chartData.diskIO.push(data.host_stats.disk_throughput);
                chartData.latency.push(data.host_stats.disk_latency);
                chartData.network.push(data.host_stats.network_traffic || 0);
                
                // Keep only last 20 data points
                if (chartData.cpu.length > 20) chartData.cpu.shift();
                if (chartData.memory.length > 20) chartData.memory.shift();
                if (chartData.diskIO.length > 20) chartData.diskIO.shift();
                if (chartData.latency.length > 20) chartData.latency.shift();
                if (chartData.network.length > 20) chartData.network.shift();
                
                // Redraw charts with real data
                drawChart('cpu-chart', chartData.cpu, '#60a5fa', 'CPU %', 100, false);
                drawChart('memory-chart', chartData.memory, '#22c55e', 'RAM %', 100, false);
                drawChart('disk-chart', chartData.diskIO, '#f59e0b', 'MB/s', Math.max(...chartData.diskIO, 1), false);
                drawChart('latency-chart', chartData.latency, '#8b5cf6', 'ms', Math.max(...chartData.latency, 10), false);
                drawChart('network-chart', chartData.network, '#ef4444', 'MB/s', Math.max(...chartData.network, 1), false);
                
                // Update VM table
                const tbody = document.querySelector('#vm-table tbody');
                tbody.innerHTML = '';
                data.vms.forEach(vm => {
                    const row = tbody.insertRow();
                    row.innerHTML = 
                        '<td><span class="vm-name">' + vm.name + '</span></td>' +
                        '<td style="color: #22c55e;">' + vm.cpu + '%</td>' +
                        '<td style="color: #22c55e;">' + vm.ram + '%</td>' +
                        '<td style="color: #22c55e;">' + vm.disk + '</td>' +
                        '<td style="color: #22c55e;">' + vm.steal_time + '</td>' +
                        '<td style="color: #22c55e;">' + vm.disk_io + '</td>';
                });
                
            } catch (error) {
                console.error('Error fetching data:', error);
            }
        }
        
        // Initial draw with loading message
        drawChart('cpu-chart', [], '#60a5fa', 'CPU %', 100, true);
        drawChart('memory-chart', [], '#22c55e', 'RAM %', 100, true);
        drawChart('disk-chart', [], '#f59e0b', 'MB/s', 1, true);
        drawChart('latency-chart', [], '#8b5cf6', 'ms', 10, true);
        drawChart('network-chart', [], '#ef4444', 'MB/s', 1, true);
        
        // Fetch data immediately and then every 5 seconds
        fetchData();
        setInterval(fetchData, 5000);
    </script>
</body>
</html>
'''

@app.route('/')
def server_dashboard():
    return render_template_string(SERVER_DASHBOARD_TEMPLATE)

@app.route('/api/server-data')
def get_server_data():
    try:
        host_stats = get_host_stats()
        vms = get_vm_metrics()
        pod_count = get_pod_count()
        
        return jsonify({
            'host_stats': host_stats,
            'vms': vms,
            'pod_count': pod_count
        })
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    import logging
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)
    
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
