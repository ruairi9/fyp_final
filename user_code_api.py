from flask import Flask, jsonify, request
import os

app = Flask(__name__)

@app.route('/')
def home():
    return jsonify({
        "service": "User Code API",
        "version": "1.0",
        "pod": os.getenv("HOSTNAME", "unknown"),
        "endpoints": {
            "/hello": "Returns Hello, World!",
            "/goodbye": "Returns Goodbye, World!",
            "/choice": "POST with choice parameter"
        }
    })

@app.route('/hello')
def hello():
    return jsonify({
        "message": "Hello, World!",
        "pod": os.getenv("HOSTNAME", "unknown")
    })

@app.route('/goodbye')
def goodbye():
    return jsonify({
        "message": "Goodbye, World!",
        "pod": os.getenv("HOSTNAME", "unknown")
    })

@app.route('/choice', methods=['POST'])
def choice():
    data = request.get_json()
    user_choice = data.get('choice', '').strip()
    
    pod = os.getenv("HOSTNAME", "unknown")
    
    if user_choice == "1":
        return jsonify({"result": "Hello, World!", "choice": "1", "pod": pod})
    elif user_choice == "2":
        return jsonify({"result": "Goodbye, World!", "choice": "2", "pod": pod})
    else:
        return jsonify({"result": "Invalid choice", "choice": user_choice, "pod": pod}), 400

@app.route('/health')
def health():
    return jsonify({"status": "healthy"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
