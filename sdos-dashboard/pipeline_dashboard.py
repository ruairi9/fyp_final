from flask import Flask, render_template_string, jsonify
import subprocess
import json
import os
import signal
import sys
import logging
import urllib.request
from datetime import datetime

app = Flask(__name__)

def signal_handler(sig, frame):
    print('\n\n' + '='*60)
    print('Pipeline Dashboard stopped')
    print('='*60)
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

def get_pipeline_data():
    """Get real pipeline execution data from Jenkins"""
    JENKINS_URL = "http://192.168.121.40:32080"
    pipelines = []
    
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
                    
                    result = build_data.get("result")
                    building = build_data.get("building", False)
                    duration = build_data.get("duration", 0) / 1000
                    timestamp = build_data.get("timestamp", 0) / 1000
                    
                    if building or result is None:
                        status = "RUNNING"
                        stages = {
                            'build': 'complete',
                            'test': 'complete',
                            'staging': 'running',
                            'load': 'pending',
                            'production': 'pending'
                        }
                    elif result == "SUCCESS":
                        status = "COMPLETE"
                        stages = {
                            'build': 'complete',
                            'test': 'complete',
                            'staging': 'complete',
                            'load': 'complete',
                            'production': 'complete'
                        }
                    elif result == "ABORTED":
                        status = "CANCELLED"
                        stages = {
                            'build': 'complete',
                            'test': 'complete',
                            'staging': 'cancelled',
                            'load': 'pending',
                            'production': 'pending'
                        }
                    else:
                        status = "FAILED"
                        stages = {
                            'build': 'complete',
                            'test': 'complete',
                            'staging': 'failed',
                            'load': 'pending',
                            'production': 'pending'
                        }
                    
                    if timestamp > 0:
                        start_dt = datetime.fromtimestamp(timestamp)
                        started = start_dt.strftime('%H:%M')
                    else:
                        started = '00:00'
                    
                    hours = int(duration // 3600)
                    minutes = int((duration % 3600) // 60)
                    seconds = int(duration % 60)
                    execution_time = f'{hours:02d}:{minutes:02d}:{seconds:02d}'
                    
                    pipelines.append({
                        'id': name[:15].upper().replace('-', ' '),
                        'status': status,
                        'started': started,
                        'execution_time': execution_time,
                        'stages': stages,
                        'profile': {
                            'clusters': 1,
                            'pods': 3,
                            'containers': 6,
                            'integration_tests': 45,
                            'load_tests': 8
                        }
                    })
                else:
                    pipelines.append({
                        'id': name[:15].upper().replace('-', ' '),
                        'status': 'NO BUILDS',
                        'started': '00:00',
                        'execution_time': '00:00:00',
                        'stages': {
                            'build': 'pending',
                            'test': 'pending',
                            'staging': 'pending',
                            'load': 'pending',
                            'production': 'pending'
                        },
                        'profile': {
                            'clusters': 0,
                            'pods': 0,
                            'containers': 0,
                            'integration_tests': 0,
                            'load_tests': 0
                        }
                    })
                    
            except Exception as e:
                print(f"Error fetching job {name}: {e}")
                continue

        if not pipelines:
            pipelines = [{
                'id': 'NO JENKINS JOBS',
                'status': 'COMPLETE',
                'started': '00:00',
                'execution_time': '00:00:00',
                'stages': {
                    'build': 'pending',
                    'test': 'pending',
                    'staging': 'pending',
                    'load': 'pending',
                    'production': 'pending'
                },
                'profile': {
                    'clusters': 0,
                    'pods': 0,
                    'containers': 0,
                    'integration_tests': 0,
                    'load_tests': 0
                }
            }]
    
    except Exception as e:
        print(f"Error connecting to Jenkins: {e}")
        pipelines = [{
            'id': 'JENKINS ERROR',
            'status': 'FAILED',
            'started': '00:00',
            'execution_time': '00:00:00',
            'stages': {
                'build': 'failed',
                'test': 'pending',
                'staging': 'pending',
                'load': 'pending',
                'production': 'pending'
            },
            'profile': {
                'clusters': 0,
                'pods': 0,
                'containers': 0,
                'integration_tests': 0,
                'load_tests': 0
            }
        }]
    
    # Sort: RUNNING first, then FAILED, then COMPLETE
    STATUS_ORDER = {'RUNNING': 0, 'COMPLETE': 1, 'CANCELLED': 2, 'FAILED': 3, 'NO BUILDS': 4}
    pipelines.sort(key=lambda p: STATUS_ORDER.get(p['status'], 99))

    return pipelines

PIPELINE_DASHBOARD_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>SDOS Pipeline Dashboard</title>
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
            justify-content: space-between;
            align-items: center;
            box-shadow: 0 8px 32px rgba(59, 130, 246, 0.3);
        }
        
        .header h1 { font-size: 32px; color: white; }
        .header .status-time { font-size: 16px; color: white; }
        .header-left { display: flex; align-items: center; gap: 20px; }
        
        .btn { 
            background: #3b82f6; color: white; border: none; 
            padding: 10px 20px; border-radius: 8px; cursor: pointer; 
            text-decoration: none; display: inline-block; transition: all 0.3s; 
        }
        .btn:hover { background: #2563eb; transform: translateY(-1px); }
        .btn-home { background: #64748b; }
        .btn-home:hover { background: #475569; }
        
        .pipeline-card {
            background: #1e293b;
            border-radius: 12px;
            margin-bottom: 20px;
            padding: 25px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.3);
            border: 1px solid #334155;
            transition: border-color 0.3s;
        }


        
        .pipeline-header {
            display: flex;
            gap: 30px;
            align-items: center;
            margin-bottom: 20px;
            padding-bottom: 15px;
            border-bottom: 2px solid #334155;
        }
        
        .pipeline-id {
            background: #0f172a;
            border: 2px solid #60a5fa;
            padding: 10px 25px;
            font-weight: bold;
            font-size: 15px;
            border-radius: 8px;
            color: #60a5fa;
        }
        
        .pipeline-status { font-weight: bold; font-size: 15px; }
        .status-running    { color: #3b82f6; }
        .status-failed     { color: #ef4444; }
        .status-complete   { color: #22c55e; }
        .status-cancelled  { color: #f59e0b; }
        .status-no-builds  { color: #818cf8; }
        
        .pipeline-time { color: #94a3b8; font-size: 14px; }

        /* RUNNING badge */
        .running-badge {
            background: #3b82f6;
            color: white;
            font-size: 11px;
            font-weight: bold;
            padding: 3px 10px;
            border-radius: 12px;
            animation: pulse-badge 1.5s infinite;
        }
        @keyframes pulse-badge {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.6; }
        }
        
        .stages-section { margin: 20px 0; }
        .stages-label {
            font-weight: bold;
            display: inline-block;
            margin-right: 20px;
            font-size: 15px;
            color: #e2e8f0;
        }
        .stages-container { display: inline-flex; gap: 40px; align-items: center; }
        
        .stage { display: flex; align-items: center; gap: 10px; font-size: 14px; }
        .stage-name { text-transform: uppercase; font-weight: 600; color: #cbd5e1; }
        
        .stage-checkbox {
            width: 22px; height: 22px;
            border: 2px solid #475569;
            border-radius: 4px;
            display: flex; align-items: center; justify-content: center;
            background: #0f172a;
        }
        .stage-checkbox.checked  { background: #22c55e; border-color: #22c55e; }
        .stage-checkbox.checked::after  { content: '✓'; color: white; font-weight: bold; font-size: 16px; }
        .stage-checkbox.running  { background: #3b82f6; border-color: #3b82f6; animation: pulse 2s infinite; }
        .stage-checkbox.running::after  { content: '⊖'; color: white; font-weight: bold; font-size: 18px; }
        .stage-checkbox.failed   { background: #ef4444; border-color: #ef4444; }
        .stage-checkbox.failed::after   { content: '✕'; color: white; font-weight: bold; font-size: 16px; }
        .stage-checkbox.cancelled { background: #f59e0b; border-color: #f59e0b; }
        .stage-checkbox.cancelled::after { content: '⊘'; color: white; font-weight: bold; font-size: 16px; }
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.6; } }
        
        .profile-section {
            margin-top: 15px; padding-top: 15px;
            border-top: 1px solid #334155;
            font-size: 14px; color: #cbd5e1;
        }
        .profile-label { font-weight: bold; display: inline; color: #e2e8f0; }
        .profile-items { display: inline; color: #94a3b8; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="header-left">
                <a href="http://localhost:5000" class="btn btn-home">← Home</a>
                <h1>Pipeline Dashboard</h1>
            </div>
            <div class="status-time" id="current-time">ON dd/mm/yy AT hh:mm</div>
        </div>
        
        <div id="pipelines-container"></div>
    </div>

    <script>
        function updateTime() {
            const now = new Date();
            const d = String(now.getDate()).padStart(2,'0');
            const m = String(now.getMonth()+1).padStart(2,'0');
            const y = String(now.getFullYear()).slice(-2);
            const h = String(now.getHours()).padStart(2,'0');
            const min = String(now.getMinutes()).padStart(2,'0');
            document.getElementById('current-time').textContent = `ON ${d}/${m}/${y} AT ${h}:${min}`;
        }
        
        function renderStage(name, status) {
            const cls = status === 'complete'   ? 'checked'
                      : status === 'running'    ? 'running'
                      : status === 'failed'     ? 'failed'
                      : status === 'cancelled'  ? 'cancelled' : '';
            return `<div class="stage">
                        <span class="stage-name">${name}</span>
                        <div class="stage-checkbox ${cls}"></div>
                    </div>`;
        }
        
        function renderPipeline(pipeline) {
            const statusClass = `status-${pipeline.status.toLowerCase().replace(/ /g, '-')}`;
            const cardClass    = pipeline.status === 'RUNNING' ? 'card-running'
                               : pipeline.status === 'FAILED'  ? 'card-failed' : '';
            const badge = pipeline.status === 'RUNNING'
                ? '<span class="running-badge">● LIVE</span>' : '';

            return `
                <div class="pipeline-card ${cardClass}">
                    <div class="pipeline-header">
                        <div class="pipeline-id">PIPELINE # ${pipeline.id}</div>
                        <div class="pipeline-status ${statusClass}">STATUS [${pipeline.status}]</div>
                        ${badge}
                        <div class="pipeline-time">STARTED @ ${pipeline.started}</div>
                        <div class="pipeline-time">TIME in EXECUTION: ${pipeline.execution_time}</div>
                    </div>
                    <div class="stages-section">
                        <span class="stages-label">STAGES:</span>
                        <div class="stages-container">
                            ${renderStage('BUILD',      pipeline.stages.build)}
                            ${renderStage('TEST',       pipeline.stages.test)}
                            ${renderStage('STAGING',    pipeline.stages.staging)}
                            ${renderStage('LOAD',       pipeline.stages.load)}
                            ${renderStage('PRODUCTION', pipeline.stages.production)}
                        </div>
                    </div>
                    <div class="profile-section">
                        <span class="profile-label">PROFILE:</span>
                        <span class="profile-items">
                            Clusters ${pipeline.profile.clusters}
                            Pods ${pipeline.profile.pods}
                            Containers ${pipeline.profile.containers}
                            Integration Test Case ${pipeline.profile.integration_tests}
                            Load Test Cases ${pipeline.profile.load_tests}
                        </span>
                    </div>
                </div>`;
        }
        
        async function fetchPipelines() {
            try {
                const response = await fetch('/api/pipeline-data');
                const data = await response.json();
                // Data is already sorted server-side: RUNNING → FAILED → COMPLETE
                document.getElementById('pipelines-container').innerHTML =
                    data.pipelines.map(p => renderPipeline(p)).join('');
            } catch (error) {
                console.error('Error fetching pipeline data:', error);
            }
        }
        
        updateTime();
        setInterval(updateTime, 1000);
        fetchPipelines();
        setInterval(fetchPipelines, 5000);
    </script>
</body>
</html>
'''

@app.route('/')
def pipeline_dashboard():
    return render_template_string(PIPELINE_DASHBOARD_TEMPLATE)

@app.route('/api/pipeline-data')
def get_pipeline_api_data():
    try:
        pipelines = get_pipeline_data()
        return jsonify({'pipelines': pipelines})
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)
    
    print("="*60)
    print("SDOS Pipeline Dashboard")
    print("="*60)
    print("Access: http://localhost:7000")
    print("Press Ctrl+C to stop")
    print("="*60)
    
    try:
        app.run(host='0.0.0.0', port=7000, debug=False, threaded=True, use_reloader=False)
    except KeyboardInterrupt:
        print("\n" + "="*60)
        print("Pipeline Dashboard stopped")
        print("="*60)
        sys.exit(0)
