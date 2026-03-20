from flask import Flask, render_template_string, request, jsonify, redirect, url_for
import subprocess
import os
from datetime import datetime

app = Flask(__name__)

# HTML Template
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>Microservice Upload Portal</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        .container {
            max-width: 800px;
            margin: 0 auto;
            background: white;
            border-radius: 15px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            overflow: hidden;
        }
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }
        .header h1 {
            font-size: 2.5em;
            margin-bottom: 10px;
        }
        .header p {
            font-size: 1.1em;
            opacity: 0.9;
        }
        .content {
            padding: 40px;
        }
        .upload-section {
            background: #f8f9fa;
            border: 2px dashed #667eea;
            border-radius: 10px;
            padding: 40px;
            text-align: center;
            margin-bottom: 30px;
            transition: all 0.3s;
        }
        .upload-section:hover {
            border-color: #764ba2;
            background: #f0f0ff;
        }
        .file-input-wrapper {
            position: relative;
            display: inline-block;
        }
        .file-input-wrapper input[type=file] {
            position: absolute;
            opacity: 0;
            width: 100%;
            height: 100%;
            cursor: pointer;
        }
        .file-input-label {
            display: inline-block;
            padding: 15px 40px;
            background: #667eea;
            color: white;
            border-radius: 50px;
            cursor: pointer;
            font-size: 1.1em;
            transition: all 0.3s;
        }
        .file-input-label:hover {
            background: #764ba2;
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(0,0,0,0.2);
        }
        .form-group {
            margin-bottom: 25px;
        }
        .form-group label {
            display: block;
            margin-bottom: 8px;
            font-weight: 600;
            color: #333;
        }
        .form-group input, .form-group select {
            width: 100%;
            padding: 12px 15px;
            border: 2px solid #e0e0e0;
            border-radius: 8px;
            font-size: 1em;
            transition: all 0.3s;
        }
        .form-group input:focus, .form-group select:focus {
            outline: none;
            border-color: #667eea;
        }
        .checkbox-group {
            display: flex;
            align-items: center;
            margin-bottom: 15px;
        }
        .checkbox-group input {
            width: auto;
            margin-right: 10px;
        }
        .submit-btn {
            width: 100%;
            padding: 15px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            border-radius: 50px;
            font-size: 1.2em;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s;
        }
        .submit-btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 25px rgba(102, 126, 234, 0.4);
        }
        .submit-btn:disabled {
            background: #ccc;
            cursor: not-allowed;
        }
        .file-info {
            margin-top: 15px;
            padding: 15px;
            background: #e3f2fd;
            border-radius: 8px;
            display: none;
        }
        .file-info.show {
            display: block;
        }
        .status-message {
            padding: 20px;
            border-radius: 8px;
            margin-top: 20px;
            display: none;
        }
        .status-message.success {
            background: #d4edda;
            color: #155724;
            border: 1px solid #c3e6cb;
            display: block;
        }
        .status-message.error {
            background: #f8d7da;
            color: #721c24;
            border: 1px solid #f5c6cb;
            display: block;
        }
        .info-box {
            background: #fff3cd;
            border: 1px solid #ffeaa7;
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 20px;
        }
        .links {
            margin-top: 30px;
            padding-top: 30px;
            border-top: 2px solid #e0e0e0;
            text-align: center;
        }
        .links a {
            display: inline-block;
            margin: 0 15px;
            padding: 10px 25px;
            background: #667eea;
            color: white;
            text-decoration: none;
            border-radius: 25px;
            transition: all 0.3s;
        }
        .links a:hover {
            background: #764ba2;
            transform: translateY(-2px);
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🚀 Microservice Upload Portal</h1>
            <p>Upload your Python code and deploy to Kubernetes</p>
        </div>
        
        <div class="content">
            {% if message %}
            <div class="status-message {{ message_type }}">
                {{ message }}
            </div>
            {% endif %}
            
            <div class="info-box">
                <strong>ℹ️ Instructions:</strong>
                <ul style="margin-left: 20px; margin-top: 10px;">
                    <li>Upload a Python file (.py)</li>
                    <li>Configure deployment settings</li>
                    <li>Click "Upload & Deploy"</li>
                    <li>Go to Jenkins to run the pipeline</li>
                </ul>
            </div>
            
            <form method="POST" enctype="multipart/form-data" id="uploadForm">
                <div class="upload-section">
                    <h3 style="margin-bottom: 20px;">📁 Select Your Python File</h3>
                    <div class="file-input-wrapper">
                        <input type="file" name="file" id="fileInput" accept=".py" required>
                        <label for="fileInput" class="file-input-label">
                            Choose File
                        </label>
                    </div>
                    <div class="file-info" id="fileInfo">
                        <strong>Selected:</strong> <span id="fileName"></span><br>
                        <strong>Size:</strong> <span id="fileSize"></span>
                    </div>
                </div>
                
                <div class="form-group">
                    <label>Service Name</label>
                    <input type="text" name="service_name" placeholder="my-microservice" required>
                </div>
                
                <div class="form-group">
                    <label>Environment</label>
                    <select name="environment">
                        <option value="both">Development & Production</option>
                        <option value="development">Development Only</option>
                        <option value="production">Production Only</option>
                    </select>
                </div>
                
                <div class="form-group">
                    <label>Development Replicas</label>
                    <input type="number" name="dev_replicas" value="2" min="1" max="5">
                </div>
                
                <div class="form-group">
                    <label>Production Replicas</label>
                    <input type="number" name="prod_replicas" value="3" min="1" max="10">
                </div>
                
                <div class="form-group">
                    <label>Production NodePort</label>
                    <input type="number" name="prod_port" value="31500" min="30000" max="32767">
                </div>
                
                <div class="checkbox-group">
                    <input type="checkbox" name="run_load_test" id="loadTest" checked>
                    <label for="loadTest">Run Load Tests</label>
                </div>
                
                <div class="checkbox-group">
                    <input type="checkbox" name="run_security_scan" id="securityScan" checked>
                    <label for="securityScan">Run Security Scan</label>
                </div>
                
                <button type="submit" class="submit-btn" id="submitBtn">
                    Upload & Deploy 🚀
                </button>
            </form>
            
            <div class="links">
                <a href="http://192.168.121.40:32080" target="_blank">Open Jenkins</a>
                <a href="/history">Upload History</a>
                <a href="/status">Cluster Status</a>
            </div>
        </div>
    </div>
    
    <script>
        const fileInput = document.getElementById('fileInput');
        const fileInfo = document.getElementById('fileInfo');
        const fileName = document.getElementById('fileName');
        const fileSize = document.getElementById('fileSize');
        
        fileInput.addEventListener('change', function(e) {
            if (e.target.files.length > 0) {
                const file = e.target.files[0];
                fileName.textContent = file.name;
                fileSize.textContent = (file.size / 1024).toFixed(2) + ' KB';
                fileInfo.classList.add('show');
            }
        });
        
        document.getElementById('uploadForm').addEventListener('submit', function() {
            document.getElementById('submitBtn').disabled = true;
            document.getElementById('submitBtn').textContent = 'Uploading...';
        });
    </script>
</body>
</html>
'''

HISTORY_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>Upload History</title>
    <style>
        body { font-family: Arial; max-width: 1000px; margin: 50px auto; padding: 20px; }
        table { width: 100%; border-collapse: collapse; margin-top: 20px; }
        th, td { padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }
        th { background: #667eea; color: white; }
        .back-btn { padding: 10px 20px; background: #667eea; color: white; text-decoration: none; border-radius: 5px; }
    </style>
</head>
<body>
    <h1>📜 Upload History</h1>
    <a href="/" class="back-btn">← Back to Upload</a>
    <table>
        <tr>
            <th>Timestamp</th>
            <th>File</th>
            <th>Service Name</th>
            <th>Environment</th>
            <th>Status</th>
        </tr>
        {% for upload in uploads %}
        <tr>
            <td>{{ upload.timestamp }}</td>
            <td>{{ upload.filename }}</td>
            <td>{{ upload.service_name }}</td>
            <td>{{ upload.environment }}</td>
            <td>✅ Uploaded</td>
        </tr>
        {% endfor %}
    </table>
</body>
</html>
'''

# Store upload history
upload_history = []

@app.route('/', methods=['GET', 'POST'])
def index():
    message = None
    message_type = None
    
    if request.method == 'POST':
        try:
            # Get uploaded file
            file = request.files['file']
            service_name = request.form.get('service_name', 'my-service')
            environment = request.form.get('environment', 'both')
            dev_replicas = request.form.get('dev_replicas', '2')
            prod_replicas = request.form.get('prod_replicas', '3')
            prod_port = request.form.get('prod_port', '31500')
            run_load_test = 'run_load_test' in request.form
            run_security_scan = 'run_security_scan' in request.form
            
            if file and file.filename.endswith('.py'):
                # Save file locally
                filename = file.filename
                filepath = f'/tmp/{filename}'
                file.save(filepath)
                
                # Upload to Jenkins using kubectl
                try:
                    result = subprocess.run([
                        'kubectl', 'cp',
                        filepath,
                        f'cicd/jenkins-b74dbbb-l7tbd:/tmp/{filename}'
                    ], env={'KUBECONFIG': './k3s.yaml'}, capture_output=True, text=True)
                    
                    if result.returncode == 0:
                        # Save to history
                        upload_history.append({
                            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                            'filename': filename,
                            'service_name': service_name,
                            'environment': environment
                        })
                        
                        message = f'''
                        ✅ SUCCESS! File uploaded to Jenkins<br><br>
                        <strong>Next Steps:</strong><br>
                        1. Go to <a href="http://192.168.121.40:32080" target="_blank">Jenkins</a><br>
                        2. Click "universal-microservice-pipeline"<br>
                        3. Click "Build with Parameters"<br>
                        4. Set:<br>
                           - SERVICE_NAME: {service_name}<br>
                           - CODE_FILE: {filename}<br>
                           - ENVIRONMENT: {environment}<br>
                           - PROD_PORT: {prod_port}<br>
                        5. Click "Build"
                        '''
                        message_type = 'success'
                    else:
                        message = f'❌ Upload failed: {result.stderr}'
                        message_type = 'error'
                except Exception as e:
                    message = f'❌ Error uploading to Jenkins: {str(e)}'
                    message_type = 'error'
            else:
                message = '❌ Please upload a Python (.py) file'
                message_type = 'error'
                
        except Exception as e:
            message = f'❌ Error: {str(e)}'
            message_type = 'error'
    
    return render_template_string(HTML_TEMPLATE, message=message, message_type=message_type)

@app.route('/history')
def history():
    return render_template_string(HISTORY_TEMPLATE, uploads=upload_history)

@app.route('/status')
def status():
    try:
        result = subprocess.run([
            'kubectl', 'get', 'pods', '--all-namespaces', '-o', 'wide'
        ], env={'KUBECONFIG': './k3s.yaml'}, capture_output=True, text=True)
        
        return f'<pre>{result.stdout}</pre><br><a href="/">Back</a>'
    except Exception as e:
        return f'Error: {str(e)}<br><a href="/">Back</a>'

if __name__ == '__main__':
    print("🌐 Starting Microservice Upload Portal...")
    print("📡 Access at: http://localhost:8000")
    print("🚀 Ready to receive uploads!")
    app.run(host='0.0.0.0', port=8000, debug=True)
