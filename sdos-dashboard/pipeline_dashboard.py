from flask import Flask, render_template_string, jsonify, redirect
import subprocess
import json
import os
import signal
import sys
import logging
import urllib.request
from datetime import datetime

app = Flask(__name__)

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
    print('Pipeline Dashboard stopped')
    print('='*60)
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

def get_pipeline_data():
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
                        stages = {'build': 'complete', 'test': 'complete', 'staging': 'running', 'load': 'pending', 'production': 'pending'}
                    elif result == "SUCCESS":
                        status = "COMPLETE"
                        stages = {'build': 'complete', 'test': 'complete', 'staging': 'complete', 'load': 'complete', 'production': 'complete'}
                    elif result == "ABORTED":
                        status = "CANCELLED"
                        stages = {'build': 'complete', 'test': 'complete', 'staging': 'cancelled', 'load': 'pending', 'production': 'pending'}
                    else:
                        status = "FAILED"
                        stages = {'build': 'complete', 'test': 'complete', 'staging': 'failed', 'load': 'pending', 'production': 'pending'}
                    
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
                        'id': name.upper().replace('-', ' '),
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
                        'id': name.upper().replace('-', ' '),
                        'status': 'NO BUILDS',
                        'started': '--:--',
                        'execution_time': '--:--:--',
                        'stages': {'build': 'pending', 'test': 'pending', 'staging': 'pending', 'load': 'pending', 'production': 'pending'},
                        'profile': {'clusters': 0, 'pods': 0, 'containers': 0, 'integration_tests': 0, 'load_tests': 0}
                    })
                    
            except Exception as e:
                print(f"Error fetching job {name}: {e}")
                continue

        if not pipelines:
            pipelines = [{'id': 'NO JENKINS JOBS', 'status': 'COMPLETE', 'started': '--:--', 'execution_time': '--:--:--',
                'stages': {'build': 'pending', 'test': 'pending', 'staging': 'pending', 'load': 'pending', 'production': 'pending'},
                'profile': {'clusters': 0, 'pods': 0, 'containers': 0, 'integration_tests': 0, 'load_tests': 0}}]
    
    except Exception as e:
        print(f"Error connecting to Jenkins: {e}")
        pipelines = [{'id': 'JENKINS ERROR', 'status': 'FAILED', 'started': '--:--', 'execution_time': '--:--:--',
            'stages': {'build': 'failed', 'test': 'pending', 'staging': 'pending', 'load': 'pending', 'production': 'pending'},
            'profile': {'clusters': 0, 'pods': 0, 'containers': 0, 'integration_tests': 0, 'load_tests': 0}}]
    
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
        body { font-family: 'Segoe UI', Arial, sans-serif; background: #1a1a1a; color: #e0e0e0; padding: 20px; }
        .container { max-width: 1600px; margin: 0 auto; }
        .header {
            background: #2d2d2d;
            padding: 20px 30px; border-radius: 15px; margin-bottom: 25px;
            display: flex; justify-content: space-between; align-items: center;
            box-shadow: none; border-bottom: 4px solid #cc0000;
        }
        .header h1 { font-size: 32px; color: white; }
        .header-left { display: flex; align-items: center; gap: 20px; }
        .header-time { font-size: 15px; color: rgba(255,255,255,0.85); }
        .btn { background: #555555; color: white; border: none; padding: 10px 20px; border-radius: 8px; cursor: pointer; text-decoration: none; display: inline-block; transition: all 0.3s; }
        .btn:hover { background: #666666; transform: translateY(-1px); }
        .btn-home { background: #64748b; }
        .btn-home:hover { background: #555555; }

        .pipeline-card {
            background: #383838; border-radius: 12px; margin-bottom: 20px;
            padding: 25px; box-shadow: 0 4px 20px rgba(0,0,0,0.3);
            border: 1px solid #555; transition: border-color 0.3s;
        }
        .pipeline-header {
            display: flex; gap: 20px; align-items: center;
            margin-bottom: 20px; padding-bottom: 15px;
            border-bottom: 2px solid #4a6fa5; flex-wrap: wrap;
        }
        .pipeline-id {
            background: #2d2d2d; border: 2px solid #60a5fa;
            padding: 6px 16px; font-weight: bold; font-size: 13px;
            border-radius: 20px; color: #cccccc; letter-spacing: 0.5px;
        }

        /* Status badge */
        .status-badge {
            padding: 6px 16px; border-radius: 20px;
            font-weight: bold; font-size: 13px; letter-spacing: 0.5px;
        }
        .status-badge.complete   { background: #052e16; color: #22c55e; border: 1px solid #22c55e; }
        .status-badge.running    { background: #3a3a3a; color: #cccccc; border: 1px solid #3b82f6; animation: pulse-badge 1.5s infinite; }
        .status-badge.failed     { background: #3b0000; color: #ef4444; border: 1px solid #ef4444; }
        .status-badge.cancelled  { background: #451a03; color: #f59e0b; border: 1px solid #f59e0b; }
        .status-badge.no-builds  { background: #1a1a3e; color: #818cf8; border: 1px solid #818cf8; }
        @keyframes pulse-badge { 0%, 100% { opacity: 1; } 50% { opacity: 0.6; } }

        .pipeline-meta { display: flex; gap: 25px; align-items: center; }
        .meta-item { display: flex; flex-direction: column; gap: 2px; }
        .meta-label { font-size: 10px; color: #ffffff; text-transform: uppercase; letter-spacing: 0.5px; }
        .meta-value { font-size: 14px; color: #ffffff; font-weight: 500; }

        .running-badge {
            background: #555555; color: white; font-size: 11px;
            font-weight: bold; padding: 3px 10px; border-radius: 12px;
            animation: pulse-badge 1.5s infinite;
        }

        .stages-section { margin: 20px 0; }
        .stages-label { font-weight: bold; display: inline-block; margin-right: 20px; font-size: 15px; color: #e0e0e0; }
        .stages-container { display: inline-flex; gap: 40px; align-items: center; }
        .stage { display: flex; align-items: center; gap: 10px; font-size: 14px; }
        .stage-name { text-transform: uppercase; font-weight: 600; color: #cccccc; }
        .stage-checkbox { width: 22px; height: 22px; border: 2px solid #475569; border-radius: 4px; display: flex; align-items: center; justify-content: center; background: #2d2d2d; }
        .stage-checkbox.checked  { background: #22c55e; border-color: #22c55e; }
        .stage-checkbox.checked::after  { content: '✓'; color: white; font-weight: bold; font-size: 16px; }
        .stage-checkbox.running  { background: #555555; border-color: #cccccc; animation: pulse 2s infinite; }
        .stage-checkbox.running::after  { content: '⊖'; color: white; font-weight: bold; font-size: 18px; }
        .stage-checkbox.failed   { background: #ef4444; border-color: #ef4444; }
        .stage-checkbox.failed::after   { content: '✕'; color: white; font-weight: bold; font-size: 16px; }
        .stage-checkbox.cancelled { background: #f59e0b; border-color: #f59e0b; }
        .stage-checkbox.cancelled::after { content: '⊘'; color: white; font-weight: bold; font-size: 16px; }
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.6; } }

        .profile-section {
            margin-top: 15px; padding-top: 15px;
            border-top: 1px solid #4a6fa5;
            display: flex; gap: 0; flex-wrap: nowrap; align-items: center;
        }
        .profile-label { font-weight: bold; font-size: 13px; color: #ffffff; margin-right: 12px; }
        .profile-chip {
            font-size: 13px; color: #ffffff;
            padding: 0 12px; border-right: 1px solid #4a6fa5;
        }
        .profile-chip:last-child { border-right: none; }
        .profile-chip span { color: #ffffff; font-weight: bold; margin-left: 4px; }
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
                <h1 style="color:white;">Pipeline Dashboard</h1>
            </div>
            <div class="header-time" id="current-time"></div>
        </div>

        <div id="pipelines-container"></div>
    </div>

    <script>
        function updateTime() {
            const now = new Date();
            const d = String(now.getDate()).padStart(2,\'0\');
            const m = String(now.getMonth()+1).padStart(2,\'0\');
            const y = String(now.getFullYear()).slice(-2);
            const h = String(now.getHours()).padStart(2,\'0\');
            const min = String(now.getMinutes()).padStart(2,\'0\');
            document.getElementById(\'current-time\').textContent = `${d}/${m}/${y}  ${h}:${min}`;
        }

        function renderStage(name, status) {
            const cls = status === \'complete\'  ? \'checked\'
                      : status === \'running\'   ? \'running\'
                      : status === \'failed\'    ? \'failed\'
                      : status === \'cancelled\' ? \'cancelled\' : \'\';
            return `<div class="stage">
                        <span class="stage-name">${name}</span>
                        <div class="stage-checkbox ${cls}"></div>
                    </div>`;
        }

        function renderPipeline(p) {
            const statusKey = p.status.toLowerCase().replace(/ /g,\'-\');
            const badge = p.status === \'RUNNING\' ? \'<span class="running-badge">● LIVE</span>\' : \'\';

            const profileChips = p.status === \'NO BUILDS\' ? \'<span style="color:#475569;font-size:12px;">No build data</span>\' : `
                <div class="profile-chip">Clusters<span>${p.profile.clusters}</span></div>
                <div class="profile-chip">Pods<span>${p.profile.pods}</span></div>
                <div class="profile-chip">Containers<span>${p.profile.containers}</span></div>
                <div class="profile-chip">Integration Tests<span>${p.profile.integration_tests}</span></div>
                <div class="profile-chip">Load Tests<span>${p.profile.load_tests}</span></div>
            `;

            return `
                <div class="pipeline-card">
                    <div class="pipeline-header">
                        <div class="pipeline-id">PIPELINE  ${p.id}</div>
                        <div class="status-badge ${statusKey}">${p.status}</div>
                        ${badge}
                        <div class="pipeline-meta">
                            <div class="meta-item">
                                <span class="meta-label">Started</span>
                                <span class="meta-value">${p.started}</span>
                            </div>
                            <div class="meta-item">
                                <span class="meta-label">Run Time</span>
                                <span class="meta-value">${p.execution_time}</span>
                            </div>
                        </div>
                    </div>
                    <div class="stages-section">
                        <span class="stages-label">STAGES:</span>
                        <div class="stages-container">
                            ${renderStage(\'BUILD\',      p.stages.build)}
                            ${renderStage(\'TEST\',       p.stages.test)}
                            ${renderStage(\'STAGING\',    p.stages.staging)}
                            ${renderStage(\'LOAD\',       p.stages.load)}
                            ${renderStage(\'PRODUCTION\', p.stages.production)}
                        </div>
                    </div>
                    <div class="profile-section">
                        <span class="profile-label">PROFILE</span>
                        ${profileChips}
                    </div>
                </div>`;
        }

        async function fetchPipelines() {
            try {
                const response = await fetch(\'/api/pipeline-data\');
                const data = await response.json();
                document.getElementById(\'pipelines-container\').innerHTML =
                    data.pipelines.map(p => renderPipeline(p)).join(\'\');
            } catch (error) {
                console.error(\'Error fetching pipeline data:\', error);
            }
        }

        updateTime();
        setInterval(updateTime, 1000);

        async function logout() {
            await fetch(\'http://localhost:5000/api/logout\', { method: \'POST\' });
            window.location.href = \'http://localhost:5000\';
        }

        fetchPipelines();
        setInterval(async function() {
            try {
                const res = await fetch(\'http://localhost:5000/api/check-session\');
                const data = await res.json();
                if (!data.logged_in) window.location.href = \'http://localhost:5000\';
            } catch(e) {}
        }, 30000);
        setInterval(fetchPipelines, 3000);
    </script>
</div></div>
</body>
</html>
'''

@app.route('/')
def pipeline_dashboard():
    if not _get_session().get("logged_in"):
        return redirect("http://localhost:5000")
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
