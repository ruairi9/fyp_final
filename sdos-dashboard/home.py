from flask import Flask, render_template_string, request, jsonify
import json as _json
import logging
import os
import subprocess

app = Flask(__name__)

SESSION_FILE = os.path.expanduser('~/fyp-cluster/sdos-dashboard/.sdos_session')

def get_session():
    try:
        if os.path.exists(SESSION_FILE):
            with open(SESSION_FILE) as f:
                return _json.load(f)
    except Exception:
        pass
    return {}

def set_session(data):
    try:
        with open(SESSION_FILE, 'w') as f:
            _json.dump(data, f)
    except Exception:
        pass

def clear_session():
    try:
        if os.path.exists(SESSION_FILE):
            os.remove(SESSION_FILE)
    except Exception:
        pass

HOME_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>SDOS - Home</title>
    <meta http-equiv="Cache-Control" content="no-cache">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Arial, sans-serif;
            background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
            color: #e2e8f0;
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }
        .container { max-width: 1400px; width: 100%; text-align: center; }
        .hero {
            background: linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%);
            padding: 60px 40px;
            border-radius: 20px;
            margin-bottom: 40px;
            box-shadow: 0 20px 60px rgba(59, 130, 246, 0.4);
        }
        .hero h1 { font-size: 48px; margin-bottom: 15px; }
        .hero p { font-size: 20px; opacity: 0.9; }
        .cards {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 25px;
        }
        .card {
            background: #1e293b;
            padding: 35px 25px;
            border-radius: 15px;
            border: 2px solid #334155;
            transition: all 0.3s;
            cursor: pointer;
            text-decoration: none;
            color: inherit;
            display: block;
        }
        .card:hover {
            transform: translateY(-10px);
            border-color: #3b82f6;
            box-shadow: 0 20px 40px rgba(59, 130, 246, 0.3);
        }
        .card-icon { font-size: 48px; margin-bottom: 20px; }
        .card h2 { color: #60a5fa; margin-bottom: 15px; font-size: 22px; }
        .card p { color: #94a3b8; font-size: 14px; line-height: 1.6; }
        .status-badge {
            display: inline-block;
            background: #22c55e;
            color: white;
            padding: 5px 15px;
            border-radius: 20px;
            font-size: 12px;
            margin-top: 15px;
        }

        /* ── Login wall ─────────────────────────────── */
        #login-wall {
            max-width: 440px;
            margin: 0 auto;
            background: #1e293b;
            border: 2px solid #334155;
            border-radius: 20px;
            padding: 40px;
            text-align: left;
        }
        #login-wall h2 {
            color: #60a5fa;
            font-size: 22px;
            margin-bottom: 8px;
            text-align: center;
        }
        #login-wall p {
            color: #94a3b8;
            font-size: 13px;
            text-align: center;
            margin-bottom: 28px;
        }
        .lw-label {
            display: block;
            color: #94a3b8;
            font-size: 13px;
            margin-bottom: 6px;
        }
        .lw-input {
            width: 100%;
            background: #0f172a;
            border: 1px solid #475569;
            border-radius: 8px;
            padding: 12px;
            color: #e2e8f0;
            font-size: 14px;
            margin-bottom: 18px;
        }
        .lw-input:focus { outline: none; border-color: #60a5fa; }
        .lw-btn {
            width: 100%;
            background: #3b82f6;
            color: white;
            border: none;
            padding: 13px;
            border-radius: 8px;
            font-size: 15px;
            font-weight: 600;
            cursor: pointer;
            transition: background 0.2s;
        }
        .lw-btn:hover { background: #2563eb; }
        #lw-error {
            color: #ef4444;
            font-size: 13px;
            margin-top: 14px;
            text-align: center;
            min-height: 18px;
        }
        #lw-spinner {
            display: none;
            text-align: center;
            color: #60a5fa;
            font-size: 13px;
            margin-top: 12px;
        }

        /* ── Logout bar (shown when logged in) ─────── */
        #user-bar {
            display: none;
            justify-content: flex-end;
            align-items: center;
            gap: 14px;
            margin-bottom: 24px;
        }
        #user-bar span { color: #94a3b8; font-size: 14px; }
        #logout-btn {
            background: #ef4444;
            color: white;
            border: none;
            padding: 9px 20px;
            border-radius: 8px;
            cursor: pointer;
            font-size: 13px;
            font-weight: 600;
            transition: all 0.3s;
        }
        #logout-btn:hover { background: #dc2626; transform: translateY(-2px); box-shadow: 0 4px 15px rgba(239,68,68,0.5); }
    </style>
</head>
<body>
    <div class="container">

        <!-- ── User bar (only visible when logged in) ── -->
        <div id="user-bar">
            <span id="user-greeting"></span>
            <button id="logout-btn" onclick="doLogout()">Logout</button>
        </div>

        <div class="hero">
            <h1>Software SDOS Operating System</h1>
            <p>Kubernetes Cluster Management &amp; Monitoring Platform</p>
        </div>

        <!-- ── Login wall (shown when NOT logged in) ── -->
        <div id="login-wall">
            <h2>🔐 Login to Website</h2>
            <p>Enter your credentials to access the SDOS dashboards</p>

            <label class="lw-label">Username</label>
            <input class="lw-input" type="text" id="lw-username" value="admin" autocomplete="username">

            <label class="lw-label">Password</label>
            <input class="lw-input" type="password" id="lw-password" placeholder="Enter password"
                   autocomplete="current-password"
                   onkeydown="if(event.key===\'Enter\') doLogin()">

            <button class="lw-btn" onclick="doLogin()">Login</button>
            <div id="lw-error"></div>
            <div id="lw-spinner">Logging in all nodes — this may take ~30 seconds...</div>
        </div>

        <!-- ── Dashboard cards (shown when logged in) ── -->
        <div id="dashboard-cards" style="display:none;">
            <div class="cards">
                <a href="http://localhost:8080" class="card">
                    <div class="card-icon">📊</div>
                    <h2>Cluster Dashboard</h2>
                    <p>Real-time cluster metrics, server status, Jenkins pipelines, and resource usage graphs</p>
                    <span class="status-badge">Active</span>
                </a>
                <a href="http://localhost:9000" class="card">
                    <div class="card-icon">🖥️</div>
                    <h2>Server Dashboard</h2>
                    <p>Individual server monitoring with VM statistics, resource utilization, and performance metrics</p>
                    <span class="status-badge">Active</span>
                </a>
                <a href="http://localhost:7000" class="card">
                    <div class="card-icon">🚀</div>
                    <h2>Pipeline Dashboard</h2>
                    <p>Jenkins CI/CD pipeline monitoring with build status, execution times, and stage tracking</p>
                    <span class="status-badge">Active</span>
                </a>
                <a href="http://localhost:6001" class="card">
                    <div class="card-icon">💻</div>
                    <h2>Developer Workspace</h2>
                    <p>Code editor with Monaco (VS Code) for editing microservices, pipelines, and configurations</p>
                    <span class="status-badge">Active</span>
                </a>
            </div>
        </div>

    </div>

    <script>
        (async function init() {
            try {
                const res  = await fetch('/api/check-session');
                const data = await res.json();
                if (data.logged_in) {
                    showDashboard(data.username);
                } else {
                    showLoginWall();
                }
            } catch(e) {
                showLoginWall();
            }
        })();

        function showLoginWall() {
            document.getElementById('login-wall').style.display      = 'block';
            document.getElementById('dashboard-cards').style.display = 'none';
            document.getElementById('user-bar').style.display        = 'none';
        }

        function showDashboard(username) {
            document.getElementById('login-wall').style.display      = 'none';
            document.getElementById('dashboard-cards').style.display = 'block';
            document.getElementById('user-bar').style.display        = 'flex';
            if (username) {
                document.getElementById('user-greeting').textContent = 'Logged in as ' + username;
            }
        }

        async function doLogin() {
            const username = document.getElementById('lw-username').value.trim();
            const password = document.getElementById('lw-password').value.trim();
            const errEl    = document.getElementById('lw-error');
            const spinner  = document.getElementById('lw-spinner');

            errEl.textContent = '';

            if (!username || !password) {
                errEl.textContent = 'Please enter username and password.';
                return;
            }

            spinner.style.display = 'block';
            document.querySelector('.lw-btn').disabled = true;

            try {
                const res  = await fetch('/api/registry-login', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ username, password })
                });
                const data = await res.json();

                const allOk = data.results && data.results.every(r => r.success);
                if (allOk) {
                    showDashboard(username);
                } else {
                    errEl.textContent = 'Incorrect password — please try again.';
                }
            } catch(e) {
                errEl.textContent = 'Error: ' + e.message;
            }

            spinner.style.display = 'none';
            document.querySelector('.lw-btn').disabled = false;
        }

        async function doLogout() {
            await fetch('/api/logout', { method: 'POST' });
            window.location.href = 'http://localhost:5000';
        }
    </script>
</body>
</html>
'''

@app.route('/')
def home():
    return render_template_string(HOME_TEMPLATE)

@app.route('/api/registry-status')
def registry_status():
    import urllib.request, urllib.error
    REGISTRY_URL = "http://192.168.121.50:30500"
    result = {'online': False, 'auth_enabled': False}
    try:
        req = urllib.request.Request(f"{REGISTRY_URL}/v2/")
        with urllib.request.urlopen(req, timeout=3) as r:
            result['online'] = True
            result['auth_enabled'] = False
    except urllib.error.HTTPError as e:
        if e.code == 401:
            result['online'] = True
            result['auth_enabled'] = True
    except Exception:
        pass
    return jsonify(result)

@app.route('/api/registry-login', methods=['POST'])
def registry_login():
    data = request.json
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()
    if not username or not password:
        return jsonify({'success': False, 'error': 'Missing credentials'})

    REGISTRY   = "192.168.121.50:30500"
    VAGRANT_DIR = os.path.expanduser('~/fyp-cluster')

    nodes = [
        ('worker-dev-integration', 'worker-dev'),
        ('worker-production',      'worker-prod'),
        ('worker-cicd',            'worker-cicd'),
        ('control-plane',          'control-plane'),
    ]

    import base64, json as _json
    auth_b64 = base64.b64encode(f'{username}:{password}'.encode()).decode()
    config   = _json.dumps({"auths": {REGISTRY: {"auth": auth_b64}}})

    results = []
    for k8s_name, vagrant_name in nodes:
        try:
            if vagrant_name == 'worker-cicd':
                cmd = f"sudo docker login {REGISTRY} -u {username} -p {password}"
            else:
                cmd = f"sudo mkdir -p /root/.docker && echo '{config}' | sudo tee /root/.docker/config.json > /dev/null && echo OK"

            result = subprocess.run(
                ['vagrant', 'ssh', vagrant_name, '-c', cmd],
                capture_output=True, text=True, timeout=20,
                cwd=VAGRANT_DIR
            )
            success = result.returncode == 0 or 'Login Succeeded' in result.stdout or 'OK' in result.stdout
            results.append({'node': k8s_name, 'success': success, 'message': result.stdout.strip()})
        except Exception as e:
            results.append({'node': k8s_name, 'success': False, 'message': str(e)})

    all_ok = all(r['success'] for r in results)
    if all_ok:
        set_session({'logged_in': True, 'username': username})
    return jsonify({'results': results, 'all_ok': all_ok})

@app.route('/api/check-session')
def check_session():
    s = get_session()
    return jsonify({'logged_in': s.get('logged_in', False), 'username': s.get('username', '')})

@app.route('/api/logout', methods=['POST'])
def logout():
    clear_session()
    return jsonify({'success': True})

@app.route('/health')
def health():
    return {'status': 'ok', 'service': 'home'}, 200

if __name__ == '__main__':
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)

    clear_session()
    print("Session cleared — all users must log in again.")

    print("=" * 60)
    print("SDOS Home Page")
    print("=" * 60)
    print("Access:              http://localhost:5000")
    print("Cluster Dashboard:   http://localhost:8080")
    print("Server Dashboard:    http://localhost:9000")
    print("Pipeline Dashboard:  http://localhost:7000")
    print("Developer Workspace: http://localhost:6001")
    print("Press Ctrl+C to stop")
    print("=" * 60)

    app.run(
        host='0.0.0.0',
        port=5000,
        debug=False,
        threaded=True,
        use_reloader=False
    )
