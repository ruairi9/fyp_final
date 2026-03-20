from flask import Flask, jsonify, request
import os

app = Flask(__name__)

# In-memory task storage
tasks = []

@app.route('/')
def home():
    return jsonify({
        "service": "To-Do List API",
        "version": "1.0.0",
        "pod": os.getenv("HOSTNAME", "unknown"),
        "endpoints": {
            "tasks": "/tasks",
            "add": "/tasks (POST)",
            "remove": "/tasks/:id (DELETE)"
        }
    })

@app.route('/tasks', methods=['GET'])
def get_tasks():
    return jsonify({
        "tasks": tasks,
        "count": len(tasks),
        "pod": os.getenv("HOSTNAME", "unknown")
    })

@app.route('/tasks', methods=['POST'])
def add_task():
    data = request.get_json()
    if data and 'task' in data:
        tasks.append(data['task'])
        return jsonify({"message": "Task added", "task": data['task']}), 201
    return jsonify({"error": "No task provided"}), 400

@app.route('/tasks/<int:task_id>', methods=['DELETE'])
def remove_task(task_id):
    if 0 <= task_id < len(tasks):
        removed = tasks.pop(task_id)
        return jsonify({"message": "Task removed", "task": removed})
    return jsonify({"error": "Invalid task ID"}), 404

@app.route('/health')
def health():
    return jsonify({"status": "healthy"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
