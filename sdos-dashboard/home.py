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
            background: #f0f0f0;
            color: #222;
            min-height: 100vh;
            display: flex;
            flex-direction: column;
        }

        /* Header */
        .header {
            background: #3a3a3a;
            color: white;
            padding: 12px 40px;
            border-bottom: 4px solid #cc0000;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }
        .header h1 {
            font-size: 42px;
            font-weight: 700;
            margin-bottom: 8px;
        }
        .header p {
            font-size: 16px;
            color: #aaa;
            font-style: italic;
        }
        .header-top { display: flex; align-items: center; }

        /* Main content */
        .main {
            flex: 1;
            padding: 40px;
            max-width: 1200px;
            margin: 0 auto;
            width: 100%;
        }

        /* Dashboard grid */
        .cards {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 20px;
            margin-top: 10px;
        }

        .card {
            background: #4a4a4a;
            color: #ffffff;
            border: none;
            border-radius: 6px;
            padding: 45px 30px;
            font-size: 18px;
            font-weight: 500;
            text-align: center;
            cursor: pointer;
            text-decoration: none;
            display: block;
            transition: background 0.2s, transform 0.1s;
            letter-spacing: 0.5px;
        }
        .card:hover {
            background: #4a4a4a;
            transform: translateY(-2px);
        }
        .card p {
            font-size: 12px;
            color: #cccccc;
            margin-top: 8px;
            font-weight: 400;
        }

        /* Login wall */
        #login-wall {
            max-width: 440px;
            margin: 40px auto;
            background: #383838;
            border: 1px solid #555;
            border-radius: 8px;
            padding: 40px;
        }
        #login-wall h2 {
            color: #ffffff;
            font-size: 22px;
            margin-bottom: 8px;
            text-align: center;
        }
        #login-wall p {
            color: #aaaaaa;
            font-size: 13px;
            text-align: center;
            margin-bottom: 28px;
        }
        .lw-label {
            display: block;
            color: #cccccc;
            font-size: 13px;
            margin-bottom: 6px;
        }
        .lw-input {
            width: 100%;
            background: #2d2d2d;
            border: 1px solid #666;
            border-radius: 6px;
            padding: 12px;
            color: #e0e0e0;
            font-size: 14px;
            margin-bottom: 18px;
        }
        .lw-input:focus { outline: none; border-color: #888; }
        .lw-btn {
            width: 100%;
            background: #4a4a4a;
            color: white;
            border: none;
            padding: 13px;
            border-radius: 6px;
            font-size: 15px;
            font-weight: 600;
            cursor: pointer;
            transition: background 0.2s;
        }
        .lw-btn:hover { background: #4a4a4a; }
        #lw-error {
            color: #cc0000;
            font-size: 13px;
            margin-top: 14px;
            text-align: center;
            min-height: 18px;
        }
        #lw-spinner {
            display: none;
            text-align: center;
            color: #888;
            font-size: 13px;
            margin-top: 12px;
        }

        /* Logout button */
        #logout-btn {
            background: #cc0000;
            color: white;
            border: none;
            padding: 9px 20px;
            border-radius: 6px;
            cursor: pointer;
            font-size: 13px;
            font-weight: 600;
            transition: background 0.2s;
        }
        #logout-btn:hover { background: #aa0000; }

        /* Footer */
        .footer {
            background: #3a3a3a;
            color: #aaa;
            text-align: center;
            padding: 20px;
            font-size: 13px;
        }
    </style>
</head>
<body>
<div style="background:#1a1a1a;min-height:100vh;padding:30px 0;">
<div style="background:#2d2d2d;max-width:1200px;margin:0 auto;padding:30px;border-radius:8px;box-shadow:0 2px 10px rgba(0,0,0,0.4);">

    <div class="header">
        <div style="width:100px;"></div>
        <div style="flex:1;text-align:center;">
            <h1 style="margin:0;">SDOS Home Page</h1>
            <p style="margin:4px 0 0 0;font-size:14px;color:#cccccc;font-style:italic;">Kubernetes Cluster Management and Monitoring Platform</p>
        </div>
        <div style="width:100px;display:flex;justify-content:flex-end;">
            <button id="logout-btn" onclick="doLogout()" style="display:none;">Logout</button>
        </div>
    </div>

    <div class="main">

        <!-- Login wall -->
        <div id="login-wall">
            <h2>Login to SDOS</h2>
            <p>Enter your credentials to access the SDOS dashboards</p>

            <label class="lw-label">Username</label>
            <input class="lw-input" type="text" id="lw-username" value="" autocomplete="username">

            <label class="lw-label">Password</label>
            <input class="lw-input" type="password" id="lw-password" placeholder="Enter password"
                   autocomplete="current-password"
                   onkeydown="if(event.key===\'Enter\') doLogin()">

            <label class="lw-label">Role</label>
            <select class="lw-input" id="lw-role" style="cursor:pointer;">
                <option value="" disabled selected>Select Role</option>
                <option value="Administrator">Administrator</option>
                <option value="Developer">Developer</option>
                <option value="Tester">Tester</option>
            </select>

            <button class="lw-btn" onclick="doLogin()">Login</button>
            <div id="lw-error"></div>
            <div id="lw-spinner">Logging in — this may take up to 30 seconds...</div>
        </div>

        <!-- Dashboard cards -->
        <div id="dashboard-cards" style="display:none;">
            <div class="cards">
                <a href="http://localhost:8080" class="card">
                    Cluster Dashboard
                    <p>Real-time cluster metrics, server status and resource usage</p>
                </a>
                <a href="http://localhost:9000" class="card">
                    Server Dashboard
                    <p>VM statistics, resource utilization and performance metrics</p>
                </a>
                <a href="http://localhost:7000" class="card">
                    Pipeline Dashboard
                    <p>Jenkins CI/CD pipeline monitoring and build status</p>
                </a>
                <a href="http://localhost:6001" class="card">
                    Developer Workspace
                    <p>Code editor for microservices, pipelines and configurations</p>
                </a>
            </div>
        </div>

    </div>

    <div class="footer">
        SDOS Operating System — Kubernetes Cluster Management Platform
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
            document.getElementById('logout-btn').style.display      = 'none';
        }

        function showDashboard(username) {
            document.getElementById('login-wall').style.display      = 'none';
            document.getElementById('dashboard-cards').style.display = 'block';
            document.getElementById('logout-btn').style.display      = 'inline-block';
        }

        async function doLogin() {
            const username = document.getElementById('lw-username').value.trim();
            const password = document.getElementById('lw-password').value.trim();
            const role     = document.getElementById('lw-role').value.trim();
            const errEl    = document.getElementById('lw-error');
            const spinner  = document.getElementById('lw-spinner');

            errEl.textContent = '';

            if (!username || !password || !role) {
                errEl.textContent = 'All fields are required.';
                return;
            }

            spinner.style.display = 'block';
            document.querySelector('.lw-btn').disabled = true;

            try {
                const res  = await fetch('/api/registry-login', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ username, password, role })
                });
                const data = await res.json();

                if (data.all_ok) {
                    showDashboard(username);
                } else {
                    errEl.textContent = data.error || 'Login failed — please try again.';
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
</div></div>
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

# Role mapping
USER_ROLES = {
    'admin':     'Administrator',
    'ruairi':    'Administrator',
    'developer': 'Developer',
    'tester':    'Tester',
}

@app.route('/api/registry-login', methods=['POST'])
def registry_login():
    data = request.json
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()
    role     = data.get('role', '').strip()

    if not username or not password or not role:
        return jsonify({'results': [], 'all_ok': False, 'error': 'All fields are required'})

    if username not in USER_ROLES:
        return jsonify({'results': [], 'all_ok': False, 'error': 'Invalid username'})

    if USER_ROLES[username] != role:
        return jsonify({'results': [], 'all_ok': False, 'error': f'You are not authorised for the {role} role'})

    REGISTRY    = "192.168.121.50:30500"
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
        set_session({'logged_in': True, 'username': username, 'role': role})
    return jsonify({'results': results, 'all_ok': all_ok, 'role': role})

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
