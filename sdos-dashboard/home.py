from flask import Flask, render_template_string
import logging
import os

app = Flask(__name__)

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
    </style>
</head>
<body>
    <div class="container">
        <div class="hero">
            <h1>Software Defined Operating System</h1>
            <p>Kubernetes Cluster Management &amp; Monitoring Platform</p>
        </div>
        
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
</body>
</html>
'''

@app.route('/')
def home():
    return render_template_string(HOME_TEMPLATE)

@app.route('/health')
def health():
    return {'status': 'ok', 'service': 'home'}, 200

if __name__ == '__main__':
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)

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

    # use_reloader=False is critical when running as background process
    app.run(
        host='0.0.0.0',
        port=5000,
        debug=False,
        threaded=True,
        use_reloader=False
    )
