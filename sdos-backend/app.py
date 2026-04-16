from flask import Flask, jsonify
import os

app = Flask(__name__)

@app.route('/api/health')
def health():
    return jsonify({
        'status': 'ok',
        'env': os.environ.get('APP_ENV', 'unknown'),
        'replicas': os.environ.get('REPLICA_COUNT', '1')
    })

@app.route('/api/info')
def info():
    return jsonify({
        'service': 'sdos-backend',
        'version': '1.0.0',
        'env': os.environ.get('APP_ENV', 'unknown')
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
