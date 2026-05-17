from flask import Flask, render_template_string, jsonify, request, session, redirect
import signal
import sys
import logging
import os
import subprocess
import json
import base64
import secrets
from collections import defaultdict
import re

SESSION_FILE = os.path.expanduser('~/fyp-cluster/sdos-dashboard/.sdos_session')

def _get_session():
    """read login state from shared session file (used across all dashboards)"""
    try:
        if os.path.exists(SESSION_FILE):
            with open(SESSION_FILE) as f:
                return json.load(f)
    except Exception:
        pass
    return {}

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)


REPOS_FILE   = os.path.expanduser('~/fyp-cluster/sdos-dashboard/github_repos.json')
EDITS_FILE   = os.path.expanduser('~/fyp-cluster/sdos-dashboard/github_edits.json')
DELETES_FILE = os.path.expanduser('~/fyp-cluster/sdos-dashboard/github_pending_deletes.json')
CLONES_DIR   = os.path.expanduser('~/fyp-cluster/sdos-dashboard/github-clones')

def load_pending_deletes():
    if os.path.exists(DELETES_FILE):
        try:
            with open(DELETES_FILE, 'r') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_pending_deletes(deletes):
    try:
        with open(DELETES_FILE, 'w') as f:
            json.dump(deletes, f, indent=2)
    except Exception as e:
        print(f"Error saving pending deletes: {e}")

def signal_handler(sig, frame):
    print('\n\n' + '='*60)
    print('Developer Workspace stopped')
    print('='*60)
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

CODE_BASE_PATH = os.path.expanduser('~/fyp-cluster')

def load_repos_from_file():
    if os.path.exists(REPOS_FILE):
        try:
            with open(REPOS_FILE, 'r') as f:
                return json.load(f)
        except:
            return []
    return []

def save_repos_to_file(repos):
    try:
        with open(REPOS_FILE, 'w') as f:
            json.dump(repos, f, indent=2)
    except Exception as e:
        print(f"Error saving repos: {e}")

def load_edits_from_file():
    if os.path.exists(EDITS_FILE):
        try:
            with open(EDITS_FILE, 'r') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_edits_to_file(edits):
    try:
        with open(EDITS_FILE, 'w') as f:
            json.dump(edits, f, indent=2)
    except Exception as e:
        print(f"Error saving edits: {e}")

def clone_or_update_repo(token, owner, repo):
    os.makedirs(CLONES_DIR, exist_ok=True)
    repo_dir = os.path.join(CLONES_DIR, f"{owner}_{repo}")
    try:
        if os.path.exists(repo_dir):
            subprocess.run(['git', 'pull'], cwd=repo_dir, check=True, capture_output=True)
        else:
            clone_url = f'https://{token}@github.com/{owner}/{repo}.git'
            subprocess.run(['git', 'clone', clone_url, repo_dir], check=True, capture_output=True)
            subprocess.run(['git', 'config', 'user.email', 'sdos@example.com'], cwd=repo_dir, check=True)
            subprocess.run(['git', 'config', 'user.name', owner], cwd=repo_dir, check=True)
        return {'success': True, 'path': repo_dir}
    except Exception as e:
        return {'success': False, 'error': str(e)}

def get_github_files_recursive(token, owner, repo, path=''):
    import urllib.request
    import urllib.error
    files = []
    try:
        if path:
            url = f'https://api.github.com/repos/{owner}/{repo}/contents/{path}'
        else:
            url = f'https://api.github.com/repos/{owner}/{repo}/contents'
        req = urllib.request.Request(url)
        req.add_header('Authorization', f'token {token}')
        req.add_header('Accept', 'application/vnd.github.v3+json')
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode())
            for item in data:
                if item['type'] == 'file':
                    files.append({
                        'name': item['name'],
                        'path': item['path'],
                        'repo': f'{owner}/{repo}',
                        'sha': item['sha'],
                        'type': 'file'
                    })
                elif item['type'] == 'dir':
                    files.append({
                        'name': item['name'],
                        'path': item['path'],
                        'repo': f'{owner}/{repo}',
                        'type': 'dir'
                    })
                    subfiles = get_github_files_recursive(token, owner, repo, item['path'])
                    files.extend(subfiles)
        return files
    except Exception as e:
        print(f"Error fetching files from {path}: {e}")
        return []

def get_github_files(token, owner, repo):
    try:
        files = get_github_files_recursive(token, owner, repo)
        return {'files': files, 'source': 'github'}
    except Exception as e:
        return {'error': str(e), 'files': []}

def load_github_file(token, owner, repo, path):
    import urllib.request
    try:
        url = f'https://api.github.com/repos/{owner}/{repo}/contents/{path}'
        req = urllib.request.Request(url)
        req.add_header('Authorization', f'token {token}')
        req.add_header('Accept', 'application/vnd.github.v3+json')
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode())
            content = base64.b64decode(data['content']).decode('utf-8')
            return {'content': content, 'sha': data['sha'], 'source': 'github'}
    except Exception as e:
        return {'error': str(e)}

def save_github_file(token, owner, repo, path, content, sha):
    import urllib.request
    try:
        url = f'https://api.github.com/repos/{owner}/{repo}/contents/{path}'
        content_b64 = base64.b64encode(content.encode('utf-8')).decode('utf-8')
        if not content.endswith('\n'):
            content = content + '\n'
        content_b64 = base64.b64encode(content.encode('utf-8')).decode('utf-8')
        payload = {
            'message': f'Update {path} via SDOS Workspace',
            'content': content_b64,
            'sha': sha,
            'branch': 'main'
        }
        req = urllib.request.Request(url, method='PUT')
        req.add_header('Authorization', f'token {token}')
        req.add_header('Accept', 'application/vnd.github.v3+json')
        req.add_header('Content-Type', 'application/json')
        with urllib.request.urlopen(req, data=json.dumps(payload).encode(), timeout=10) as response:
            result = json.loads(response.read().decode())
            return {'success': True, 'sha': result['content']['sha']}
    except Exception as e:
        return {'success': False, 'error': str(e)}

def create_github_file(token, owner, repo, path, content):
    import urllib.request
    try:
        url = f'https://api.github.com/repos/{owner}/{repo}/contents/{path}'
        content_b64 = base64.b64encode(content.encode('utf-8')).decode('utf-8')
        payload = {
            'message': f'chore: create empty {path} [via SDOS Workspace]',
            'content': content_b64,
            'branch': 'main'
        }
        req = urllib.request.Request(url, method='PUT')
        req.add_header('Authorization', f'token {token}')
        req.add_header('Accept', 'application/vnd.github.v3+json')
        req.add_header('Content-Type', 'application/json')
        with urllib.request.urlopen(req, data=json.dumps(payload).encode(), timeout=10) as response:
            result = json.loads(response.read().decode())
            return {'success': True, 'sha': result['content']['sha']}
    except Exception as e:
        return {'success': False, 'error': str(e)}

def delete_github_file(token, owner, repo, path, sha):
    import urllib.request
    try:
        url = f'https://api.github.com/repos/{owner}/{repo}/contents/{path}'
        payload = {
            'message': f'chore: delete {path} [via SDOS Workspace]',
            'sha': sha,
            'branch': 'main'
        }
        req = urllib.request.Request(url, method='DELETE')
        req.add_header('Authorization', f'token {token}')
        req.add_header('Accept', 'application/vnd.github.v3+json')
        req.add_header('Content-Type', 'application/json')
        urllib.request.urlopen(req, data=json.dumps(payload).encode(), timeout=10)
        return {'success': True}
    except Exception as e:
        return {'success': False, 'error': str(e)}

def get_folder_files_with_sha(token, owner, repo, folder_path):
    import urllib.request
    files = []
    try:
        url = f'https://api.github.com/repos/{owner}/{repo}/contents/{folder_path}'
        req = urllib.request.Request(url)
        req.add_header('Authorization', f'token {token}')
        req.add_header('Accept', 'application/vnd.github.v3+json')
        with urllib.request.urlopen(req, timeout=10) as response:
            items = json.loads(response.read().decode())
            for item in items:
                if item['type'] == 'file':
                    files.append({'path': item['path'], 'sha': item['sha']})
                elif item['type'] == 'dir':
                    files.extend(get_folder_files_with_sha(token, owner, repo, item['path']))
    except Exception as e:
        print(f"Error listing folder {folder_path}: {e}")
    return files

WORKSPACE_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>SDOS - Developer Workspace</title>
    <meta http-equiv="Cache-Control" content="no-cache">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/0.44.0/min/vs/editor/editor.main.min.css">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: 'Segoe UI', Arial, sans-serif; 
            background: #1a1a1a; 
            color: #e0e0e0; 
        }
        
        .header {
            background: #3a3a3a;
            padding: 20px 30px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 4px solid #cc0000;
        }
        
        .header h1 { font-size: 32px; color: white; }
        .header-left { display: flex; align-items: center; gap: 20px; }
        
        .btn { 
            background: #555555; color: white; border: none; 
            padding: 10px 20px; border-radius: 8px; cursor: pointer; 
            text-decoration: none; display: inline-block; transition: all 0.3s; 
        }
        .btn:hover { background: #666666; transform: translateY(-1px); }
        .btn-home { background: #64748b; }
        .btn-home:hover { background: #555555; }
        .btn-success { background: #22c55e; }
        .btn-success:hover { background: #16a34a; }
        .btn-danger { background: #ef4444; }
        .btn-danger:hover { background: #dc2626; }
        .btn-warning { background: #f59e0b; }
        .btn-warning:hover { background: #d97706; }
        .btn-small { padding: 6px 12px; font-size: 12px; }
        .btn-secondary { background: #555555; }
        .btn-secondary:hover { background: #4a4a4a; }
        
        .modal {
            display: none;
            position: fixed;
            top: 0; left: 0; right: 0; bottom: 0;
            background: rgba(0,0,0,0.8);
            z-index: 1000;
            align-items: center;
            justify-content: center;
        }
        
        .modal.active { display: flex; }
        
        .modal-content {
            background: #383838;
            border: 1px solid #555;
            border-radius: 12px;
            padding: 30px;
            max-width: 520px;
            width: 90%;
            box-shadow: 0 20px 60px rgba(0,0,0,0.5);
        }
        
        .modal-header {
            font-size: 24px;
            color: #cccccc;
            margin-bottom: 20px;
        }
        
        .form-group {
            margin-bottom: 20px;
        }
        
        .form-group label {
            display: block;
            color: #cccccc;
            margin-bottom: 8px;
            font-size: 14px;
        }
        
        .form-group input {
            width: 100%;
            padding: 12px;
            background: #2d2d2d;
            border: 1px solid #666;
            border-radius: 8px;
            color: #e0e0e0;
            font-size: 14px;
        }
        
        .form-group input:focus {
            outline: none;
            border-color: #cccccc;
        }
        
        .form-actions {
            display: flex;
            gap: 12px;
            margin-top: 25px;
        }

        .folder-mode-tabs {
            display: flex;
            gap: 8px;
            margin-bottom: 20px;
        }
        .folder-mode-tab {
            flex: 1;
            padding: 10px;
            background: #2d2d2d;
            border: 2px solid #555;
            border-radius: 8px;
            color: #999999;
            cursor: pointer;
            font-size: 13px;
            text-align: center;
            transition: all 0.2s;
        }
        .folder-mode-tab.active {
            border-color: #cccccc;
            color: #cccccc;
            background: #3a3a3a;
        }
        .folder-with-file-section {
            display: none;
        }
        .folder-with-file-section.active {
            display: block;
        }
        
        .main-container {
            display: grid;
            grid-template-columns: var(--left-width, 350px) 8px 1fr;
            grid-template-rows: 1fr;
            height: calc(100vh - 80px);
            padding: 20px;
            gap: 0;
        }

        .left-panel {
            grid-column: 1;
            grid-row: 1 / 3;
            background: #383838;
            border: 1px solid #555;
            border-radius: 12px;
            padding: 20px;
            display: flex;
            flex-direction: column;
            gap: 15px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.3);
            overflow-y: auto;
            min-width: 220px;
            max-width: 600px;
        }

        .row-resizer {
            flex: 0 0 14px;
            cursor: row-resize;
            display: flex;
            align-items: center;
            justify-content: center;
            background: #2d2d2d;
            border-bottom: 1px solid #334155;
            border-radius: 12px 12px 0 0;
            margin: -15px -15px 10px -15px;
            transition: background 0.2s;
        }
        .row-resizer::after {
            content: '';
            display: block;
            width: 60px;
            height: 4px;
            background: #4a4a4a;
            border-radius: 2px;
            transition: background 0.2s;
        }
        .row-resizer:hover, .row-resizer.dragging { background: rgba(59,130,246,0.2); }
        .row-resizer:hover::after, .row-resizer.dragging::after { background: #555555; }

        .panel-resizer {
            grid-column: 2;
            grid-row: 1 / 3;
            cursor: col-resize;
            background: transparent;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: background 0.2s;
            z-index: 10;
        }
        .panel-resizer:hover, .panel-resizer.dragging {
            background: rgba(59,130,246,0.3);
            border-radius: 4px;
        }
        .panel-resizer::after {
            content: '';
            width: 3px;
            height: 50px;
            background: #4a4a4a;
            border-radius: 3px;
        }
        .panel-resizer:hover::after, .panel-resizer.dragging::after {
            background: #60a5fa;
        }

        .right-col {
            grid-column: 3;
            grid-row: 1;
            display: flex;
            flex-direction: column;
            gap: 0;
            min-width: 0;
            overflow: hidden;
        }

        .editor-window {
            flex: 1 1 0;
            background: #383838;
            border: 1px solid #555;
            border-radius: 12px;
            padding: 20px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.3);
            display: flex;
            flex-direction: column;
            min-height: 150px;
            overflow: hidden;
        }

        .command-line {
            flex: 0 0 var(--terminal-height, 180px);
            background: #383838;
            border: 1px solid #555;
            border-radius: 12px;
            padding: 15px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.3);
            min-height: 80px;
            overflow: hidden;
            display: flex;
            flex-direction: column;
        }
        
        .info-section {
            background: #2d2d2d;
            border: 1px solid #555;
            border-radius: 8px 8px 0 0;
            padding: 12px;
            font-size: 12px;
            overflow-y: auto;
            min-height: 50px;
        }
        
        .info-section strong {
            color: #cccccc;
            display: block;
            margin-bottom: 8px;
        }
        
        .github-repos { margin-top: 8px; }
        
        .repo-item {
            background: #383838;
            padding: 8px 10px;
            border-radius: 6px;
            margin: 5px 0;
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-size: 11px;
        }
        
        .repo-name { color: #22c55e; }
        
        .info-section p {
            color: #999999;
            margin: 3px 0;
        }
        
        .file-tree {
            background: #2d2d2d;
            border: 1px solid #555;
            border-radius: 8px 8px 0 0;
            padding: 15px;
            padding-right: 6px;
            min-height: 60px;
            overflow-y: auto;
            scrollbar-gutter: stable;
        }

        .box-resizer {
            height: 8px;
            cursor: row-resize;
            background: #252525;
            border: 1px solid #555;
            border-top: none;
            border-radius: 0 0 8px 8px;
            display: flex;
            align-items: center;
            justify-content: center;
            flex-shrink: 0;
            transition: background 0.2s;
            margin-bottom: 10px;
        }
        .box-resizer:hover, .box-resizer.dragging {
            background: rgba(59,130,246,0.25);
        }
        .box-resizer::after {
            content: '';
            width: 36px;
            height: 3px;
            background: #2d3f55;
            border-radius: 3px;
        }
        .box-resizer:hover::after, .box-resizer.dragging::after {
            background: #60a5fa;
        }
        
        .file-tree-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 10px;
            gap: 6px;
        }

        .file-tree-title {
            color: #cccccc;
            font-weight: bold;
            font-size: 14px;
            flex: 1;
        }

        .tree-header-btn {
            padding: 3px 8px;
            border-radius: 5px;
            border: none;
            font-size: 10px;
            cursor: pointer;
            font-weight: 600;
            transition: all 0.2s;
            white-space: nowrap;
        }
        .tree-save-btn {
            background: #22c55e;
            color: white;
        }
        .tree-save-btn:hover { background: #16a34a; }
        .tree-commit-btn {
            background: #f59e0b;
            color: white;
        }
        .tree-commit-btn:hover { background: #d97706; }

        .file-item.pending-create .file-label {
            color: #fbbf24;
            font-style: italic;
        }
        .subfolder-header.pending-create .subfolder-name {
            color: #fbbf24;
            font-style: italic;
        }

        .subfolder-header.pending-delete .subfolder-name {
            text-decoration: line-through;
            color: #ef4444;
            opacity: 0.8;
        }
        .subfolder-header.pending-delete .repo-action-btn {
            display: none;
        }

        .file-item.pending-delete .file-label {
            text-decoration: line-through;
            color: #ef4444;
            opacity: 0.7;
        }
        .subfolder-header.pending-delete .subfolder-name {
            text-decoration: line-through;
            color: #ef4444;
            opacity: 0.7;
        }

        .delete-btn {
            background: transparent;
            border: none;
            color: #2d3f55;
            cursor: pointer;
            font-size: 11px;
            padding: 1px 5px;
            border-radius: 3px;
            flex-shrink: 0;
            line-height: 1;
            transition: color 0.15s, background 0.15s;
            margin-left: auto;
            opacity: 0.4;
        }
        .file-item:hover .delete-btn,
        .subfolder-header:hover .delete-btn {
            opacity: 1;
            color: #999999;
        }
        .delete-btn:hover {
            color: #ef4444 !important;
            background: #3b0000;
            opacity: 1 !important;
        }
        
        .repo-folder { margin-bottom: 15px; }
        
        .repo-folder-header {
            color: #22c55e;
            font-weight: bold;
            font-size: 13px;
            padding: 6px 10px;
            background: #383838;
            border-radius: 6px;
            margin-bottom: 5px;
            cursor: pointer;
            user-select: none;
            transition: all 0.2s;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .repo-folder-header:hover { background: #4a4a4a; }
        
        .repo-folder-header::before {
            content: '▼ ';
            display: inline-block;
            transition: transform 0.2s;
        }
        
        .repo-folder.collapsed .repo-folder-header::before {
            transform: rotate(-90deg);
        }
        
        .subfolder {
            margin-left: 20px;
            margin-top: 5px;
        }
        
        .subfolder-header {
            color: #f59e0b;
            font-weight: bold;
            font-size: 12px;
            padding: 4px 8px;
            background: #2d2d2d;
            border-radius: 4px;
            margin-bottom: 3px;
            user-select: none;
            transition: all 0.2s;
            display: flex;
            align-items: center;
            gap: 4px;
        }
        
        .subfolder-header:hover { background: #383838; }

        .subfolder-arrow {
            color: #f59e0b;
            font-size: 10px;
            flex-shrink: 0;
            transition: transform 0.2s;
            cursor: pointer;
            padding: 0 2px;
        }
        .subfolder.collapsed .subfolder-arrow {
            transform: rotate(-90deg);
        }
        
        .repo-actions {
            display: flex;
            gap: 5px;
        }
        
        .repo-action-btn {
            background: #3a3a3a;
            color: #cccccc;
            border: 1px solid #2d5a8f;
            padding: 2px 6px;
            border-radius: 4px;
            font-size: 9px;
            cursor: pointer;
            transition: all 0.15s;
            white-space: nowrap;
            flex-shrink: 0;
            opacity: 0;
        }
        .repo-folder-header:hover .repo-action-btn,
        .subfolder-header:hover .repo-action-btn {
            opacity: 1;
        }
        .repo-action-btn:hover {
            background: #4a4a4a;
            color: white;
            border-color: #cccccc;
        }
        
        .repo-action-btn:hover { background: #555555; }
        
        .repo-folder-files {
            display: block;
        }
        
        .repo-folder.collapsed .repo-folder-files { display: none; }
        
        .subfolder-files {
            display: block;
        }
        
        .subfolder.collapsed .subfolder-files { display: none; }
        
        .file-item {
            padding: 6px 8px;
            padding-left: 8px;
            cursor: pointer;
            border-radius: 6px;
            margin: 2px 0;
            font-size: 12px;
            color: #cccccc;
            transition: all 0.2s;
            display: flex;
            align-items: center;
            gap: 6px;
        }
        
        .file-item:hover { background: #383838; color: #cccccc; }
        .file-item.active { background: #555555; color: white; }
        
        .file-item.subfolder-file { padding-left: 20px; }

        .drag-handle {
            cursor: grab;
            color: #334155;
            font-size: 14px;
            line-height: 1;
            user-select: none;
            flex-shrink: 0;
            padding: 2px 3px;
            border-radius: 3px;
            transition: color 0.15s, background 0.15s;
        }
        .drag-handle:hover {
            color: #cccccc;
            background: #3a3a3a;
        }
        .drag-handle:active { cursor: grabbing; }

        .file-label {
            flex: 1;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }

        .file-item.dragging {
            opacity: 0.4;
            background: #383838;
        }
        .file-item.drag-over-top {
            border-top: 2px solid #60a5fa;
        }
        .file-item.drag-over-bottom {
            border-bottom: 2px solid #60a5fa;
        }

        .subfolder-drag {
            cursor: grab;
            color: #334155;
            font-size: 13px;
            user-select: none;
            flex-shrink: 0;
            transition: color 0.15s;
        }
        .subfolder-drag:hover { color: #f59e0b; }
        .subfolder-drag:active { cursor: grabbing; }
        
        .tool-section {
            display: flex;
            flex-direction: column;
            gap: 10px;
        }
        
        .tool-button {
            background: #2d2d2d;
            border: 2px solid #60a5fa;
            border-radius: 8px;
            padding: 12px 20px;
            font-size: 15px;
            color: #cccccc;
            cursor: pointer;
            transition: all 0.3s;
            font-weight: 600;
        }
        
        .tool-button:hover {
            background: #383838;
            border-color: #aaaaaa;
        }
        
        .tool-description {
            font-size: 12px;
            color: #999999;
            margin-left: 10px;
            line-height: 1.5;
        }
        
        .bottom-buttons {
            display: flex;
            gap: 12px;
            margin-top: auto;
        }
        
        .nav-button {
            flex: 1;
            background: #4a4a4a;
            border: 1px solid #666;
            border-radius: 8px;
            padding: 10px 20px;
            font-size: 13px;
            color: #e0e0e0;
            cursor: pointer;
            transition: all 0.3s;
        }
        
        .nav-button:hover {
            background: #555555;
            border-color: #cccccc;
        }
        
        .window-header {
            background: #2d2d2d;
            border: 1px solid #555;
            padding: 12px 20px;
            font-size: 14px;
            font-weight: bold;
            margin-bottom: 15px;
            border-radius: 8px;
            color: #cccccc;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .editor-actions { display: flex; gap: 10px; }
        
        .current-file {
            font-size: 13px;
            color: #999999;
            font-weight: normal;
        }
        
        #monaco-editor {
            flex: 1;
            border: 1px solid #555;
            border-radius: 8px;
            overflow: hidden;
        }
        
        .command-header {
            background: #2d2d2d;
            border: 1px solid #555;
            padding: 10px 20px;
            font-size: 13px;
            font-weight: bold;
            margin-bottom: 10px;
            border-radius: 8px;
            color: #cccccc;
        }
        
        .command-content {
            background: #000;
            color: #0f0;
            border: 1px solid #555;
            padding: 15px;
            font-family: 'Courier New', monospace;
            font-size: 12px;
            flex: 1;
            max-height: none;
            overflow-y: auto;
            border-radius: 8px;
            overflow-y: auto;
        }
    </style>
</head>
<body>
    <div class="modal" id="github-modal">
        <div class="modal-content">
            <div class="modal-header">Add GitHub Repository</div>
            <div class="form-group">
                <label>GitHub Personal Access Token</label>
                <input type="password" id="github-token" placeholder="ghp_xxxxxxxxxxxx">
                <p style="font-size: 11px; color: #999999; margin-top: 5px;">
                    Create token at: <a href="https://github.com/settings/tokens" target="_blank" style="color: #cccccc;">github.com/settings/tokens</a><br>
                    Required scope: <code>repo</code>
                </p>
            </div>
            <div class="form-group">
                <label>Repository Owner (Username)</label>
                <input type="text" id="github-owner" placeholder="your-username">
            </div>
            <div class="form-group">
                <label>Repository Name</label>
                <input type="text" id="github-repo" placeholder="microservices-repo">
            </div>
            <div class="form-actions">
                <button class="btn btn-success" style="flex: 1;" onclick="connectGithub()">Add Repository</button>
                <button class="btn btn-danger" onclick="closeModal()">Cancel</button>
            </div>
        </div>
    </div>

    <div class="modal" id="new-file-modal">
        <div class="modal-content">
            <div class="modal-header">Create New File</div>
            <div class="form-group">
                <label>File Path</label>
                <input type="text" id="new-file-path" placeholder="filename.py or folder/filename.py">
                <p style="font-size: 11px; color: #999999; margin-top: 5px;">
                    Examples: <code>test.py</code> or <code>utils/helper.py</code>
                </p>
            </div>
            <div class="form-group">
                <label>Repository</label>
                <div id="new-file-repo-name" style="color: #22c55e; font-weight: bold;"></div>
            </div>
            <div class="form-actions">
                <button class="btn btn-success" style="flex: 1;" onclick="createNewFile()">Create File</button>
                <button class="btn btn-danger" onclick="closeNewFileModal()">Cancel</button>
            </div>
        </div>
    </div>

    <div class="modal" id="new-folder-modal">
        <div class="modal-content">
            <div class="modal-header">Create New Folder</div>

            <div class="folder-mode-tabs">
                <div class="folder-mode-tab active" id="tab-empty" onclick="setFolderMode('empty')">
                    Empty Folder
                </div>
                <div class="folder-mode-tab" id="tab-with-file" onclick="setFolderMode('with-file')">
                    Folder + File
                </div>
            </div>

            <div class="form-group">
                <label>Repository</label>
                <div id="new-folder-repo-name" style="color: #22c55e; font-weight: bold; margin-bottom: 4px;"></div>
                <div style="font-size: 11px; color: #64748b;">
                    Creating inside: <span id="new-folder-parent-display" style="color: #999999;">/ (root)</span>
                </div>
            </div>

            <div class="form-group">
                <label>New Folder Name</label>
                <input type="text" id="new-folder-name" placeholder="my-folder">
            </div>

            <div class="folder-with-file-section" id="folder-file-section">
                <div class="form-group">
                    <label>File Name inside new folder</label>
                    <input type="text" id="new-folder-filename" placeholder="main.py">
                    <p style="font-size: 11px; color: #999999; margin-top: 5px;">
                        Creates an empty file inside the new folder
                    </p>
                </div>
            </div>

            <div class="form-actions">
                <button class="btn btn-success" style="flex: 1;" onclick="createNewFolder()">Create Folder</button>
                <button class="btn btn-danger" onclick="closeNewFolderModal()">Cancel</button>
            </div>
        </div>
    </div>

    <div class="header">
        <div class="header-left">
            <a href="http://localhost:5000" class="btn btn-home">← Home</a>
            <button onclick="logout()" style="background:#ef4444;color:white;border:none;padding:8px 18px;border-radius:8px;cursor:pointer;font-size:13px;font-weight:600;transition:all 0.3s;" onmouseover="this.style.background='#dc2626';this.style.transform='translateY(-2px)'" onmouseout="this.style.background='#ef4444';this.style.transform='translateY(0)'">Logout</button>
            <h1 style="color:white;">Developer Workspace</h1>
        </div>
    </div>
    
    <div class="main-container">
        <div class="left-panel">
            <div class="info-section" id="repos-box">
                <strong>GitHub Repositories</strong>
                <div id="github-repos-list">
                    <p style="color: #64748b;">Loading...</p>
                </div>
                <button class="btn btn-success btn-small" style="margin-top: 10px; width: 100%;" onclick="showGithubModal()">+ Add Repository</button>
            </div>
            <div class="box-resizer" data-target="repos-box" title="Drag to resize"></div>
            
            <div class="info-section" id="vscode-box">
                <strong>Visual Studio Code</strong>
                <p style="font-size: 11px; color: #999999; margin-bottom: 8px;">Opens with full Git integration</p>
                <div id="vscode-files" style="margin-top: 10px; overflow-y: auto;">
                    <p style="color: #64748b; font-size: 11px;">Load a file first</p>
                </div>
            </div>
            <div class="box-resizer" data-target="vscode-box" title="Drag to resize"></div>
            
            <div class="file-tree" id="file-tree-box">
                <div class="file-tree-header">
                    <div class="file-tree-title">Microservice Files</div>
                    <button class="tree-header-btn tree-save-btn" onclick="saveAllEdits()" title="Save all unsaved edits locally"> Save All</button>
                    <button class="tree-header-btn tree-commit-btn" onclick="commitAllEdits()" title="Push all saved edits to GitHub"> Commit All</button>
                </div>
                <div id="file-list">Loading...</div>
            </div>
            <div class="box-resizer" data-target="file-tree-box" title="Drag to resize file tree"></div>
            
            <div class="tool-section">
                <button class="tool-button" onclick="refreshFiles()">Refresh Files</button>
                <div class="tool-description">Reload all files from GitHub</div>
            </div>
            
            <div class="bottom-buttons">
                <button class="nav-button" onclick="goToDashboard()">Main Dashboard</button>
                <button class="nav-button" onclick="checkPipelines()">Pipelines</button>
            </div>
        </div>
        
        <div class="panel-resizer" id="panel-resizer" title="Drag to resize"></div>

        <div class="right-col">
        <div class="editor-window">
            <div class="window-header">
                <div>
                    <span>CODE EDITOR</span>
                    <div class="current-file" id="current-file">No file selected</div>
                </div>
                <div class="editor-actions">
                    <button class="btn btn-success" onclick="saveFile()">Save</button>
                    <button class="btn btn-warning" onclick="commitToGithub()" id="commit-btn" style="display:none;">Push to GitHub</button>
                    <button class="btn btn-danger" onclick="reloadFile()">Reload</button>
                </div>
            </div>
            <div id="monaco-editor"></div>
        </div>
        
        <div class="row-resizer" id="row-resizer" title="Drag to resize"></div>
        <div class="command-line">
            <div class="command-header">COMMAND LINE</div>
            <div class="command-content" id="terminal">$ SDOS Developer Workspace
$ </div>
        </div>
    </div>

    <script src="https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/0.44.0/min/vs/loader.min.js"></script>
    <script>
        let editor;
        let currentFile = '';
        let currentFilePath = '';
        let currentSource = 'github';
        let currentRepo = '';
        let currentSha = '';
        let githubRepos = [];
        let selectedRepoForNewFile = '';
        let selectedRepoForNewFolder = '';
        let selectedFolderParentPath = '';
        let folderCreateMode = 'empty';
        let pendingDeletes = {};
        let pendingStagedFolders = {};
        let pendingCreates = [];
        let pendingCreateFolders = {};
        let lastSavedPath = '';
        let _pendingPushContent = null;
        
        require.config({ paths: { vs: 'https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/0.44.0/min/vs' }});
        
        require(['vs/editor/editor.main'], function() {
            editor = monaco.editor.create(document.getElementById('monaco-editor'), {
                value: '',
                language: 'python',
                theme: 'vs-dark',
                automaticLayout: true,
                fontSize: 14,
                minimap: { enabled: true },
                scrollBeyondLastLine: false,
                wordWrap: 'on'
            });
            
            addTerminalLine('Monaco Editor initialized');

            setInterval(async function() {
                try {
                    const res = await fetch('http://localhost:5000/api/check-session');
                    const data = await res.json();
                    if (!data.logged_in) {
                        window.location.href = 'http://localhost:5000';
                    }
                } catch(e) {}
            }, 30000);

            loadGithubRepos();
            loadPendingDeletes().then(() => loadFileList());
        });

        async function logout() {
            await fetch('http://localhost:5000/api/logout', { method: 'POST' });
            window.location.href = 'http://localhost:5000';
        }

        function setFolderMode(mode) {
            folderCreateMode = mode;
            document.getElementById('tab-empty').classList.toggle('active', mode === 'empty');
            document.getElementById('tab-with-file').classList.toggle('active', mode === 'with-file');
            document.getElementById('folder-file-section').classList.toggle('active', mode === 'with-file');
        }
        
        function showGithubModal() {
            document.getElementById('github-modal').classList.add('active');
        }
        function closeModal() {
            document.getElementById('github-modal').classList.remove('active');
        }
        function showNewFileModal(repoName) {
            selectedRepoForNewFile = repoName;
            document.getElementById('new-file-repo-name').textContent = repoName;
            document.getElementById('new-file-path').value = '';
            document.getElementById('new-file-modal').classList.add('active');
        }
        function closeNewFileModal() {
            document.getElementById('new-file-modal').classList.remove('active');
        }
        function showNewFolderModal(repoName, parentPath) {
            selectedRepoForNewFolder = repoName;
            selectedFolderParentPath = parentPath || '';
            document.getElementById('new-folder-repo-name').textContent = repoName;
            document.getElementById('new-folder-parent-display').textContent =
                parentPath ? '/' + parentPath : '/ (root)';
            document.getElementById('new-folder-name').value = '';
            document.getElementById('new-folder-filename').value = '';
            setFolderMode('empty');
            document.getElementById('new-folder-modal').classList.add('active');
        }
        function closeNewFolderModal() {
            document.getElementById('new-folder-modal').classList.remove('active');
        }
        
        async function createNewFile() {
            const filePath = document.getElementById('new-file-path').value.trim();
            if (!filePath) { addTerminalLine(' Please enter a file path'); return; }
            if (!selectedRepoForNewFile) { addTerminalLine(' No repository selected'); return; }

            pendingCreates.push({ repo: selectedRepoForNewFile, path: filePath });
            closeNewFileModal();
            await loadFileList();
            addTerminalLine(` Staged new file ${filePath} hit Save All then Commit All to push`);

            const fileName = filePath.split('/').pop();
            editor.setValue('');
            currentFile = fileName;
            currentFilePath = filePath;
            currentSource = 'github';
            currentRepo = selectedRepoForNewFile;
            currentSha = '';
            document.getElementById('current-file').textContent = filePath + ' [' + selectedRepoForNewFile + '] (new - not yet committed)';
            document.getElementById('commit-btn').style.display = 'inline-block';
            const ext = fileName.split('.').pop();
            const langMap = { 'py': 'python', 'js': 'javascript', 'html': 'html', 'css': 'css',
                'json': 'json', 'yaml': 'yaml', 'yml': 'yaml', 'sh': 'shell', 'md': 'markdown' };
            monaco.editor.setModelLanguage(editor.getModel(), langMap[ext] || 'plaintext');
            editor.focus();
        }
        
        async function createNewFolder() {
            const folderName = document.getElementById('new-folder-name').value.trim();
            if (!folderName) { addTerminalLine(' Please enter a folder name'); return; }
            if (!selectedRepoForNewFolder) { addTerminalLine(' No repository selected'); return; }

            const folderPath = selectedFolderParentPath
                ? selectedFolderParentPath + '/' + folderName
                : folderName;

            let targetPath;
            if (folderCreateMode === 'with-file') {
                const fileName = document.getElementById('new-folder-filename').value.trim();
                if (!fileName) { addTerminalLine(' Please enter a file name'); return; }
                targetPath = folderPath + '/' + fileName;
            } else {
                targetPath = folderPath + '/.gitkeep';
            }

            pendingCreates.push({ repo: selectedRepoForNewFolder, path: targetPath, folderPath });
            closeNewFolderModal();

            pendingCreateFolders[selectedRepoForNewFolder] = pendingCreateFolders[selectedRepoForNewFolder] || new Set();
            pendingCreateFolders[selectedRepoForNewFolder].add(folderPath);

            await loadFileList();
            if (folderCreateMode === 'with-file') {
                addTerminalLine(` Staged new folder ${folderPath} hit Save All then Commit All to push`);
            } else {
                addTerminalLine(` Staged empty folder ${folderPath} hit Save All then Commit All to push`);
            }
        }
        
        async function loadGithubRepos() {
            const response = await fetch('/api/list-github-repos');
            const data = await response.json();
            githubRepos = data.repos || [];
            updateReposList();
            if (githubRepos.length > 0) addTerminalLine(`Loaded ${githubRepos.length} repositories`);
        }
        
        function updateReposList() {
            const container = document.getElementById('github-repos-list');
            if (githubRepos.length === 0) {
                container.innerHTML = '<p style="color: #64748b;">No repositories connected</p>';
            } else {
                container.innerHTML = '';
                githubRepos.forEach((repo, idx) => {
                    const div = document.createElement('div');
                    div.className = 'repo-item';
                    div.innerHTML = `<span class="repo-name">${repo}</span>
                        <button class="btn btn-danger btn-small" onclick="removeRepo(${idx})">Remove</button>`;
                    container.appendChild(div);
                });
            }
        }
        
        async function removeRepo(index) {
            const response = await fetch('/api/remove-github-repo', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ index: index })
            });
            const data = await response.json();
            if (data.success) {
                await loadGithubRepos();
                await loadFileList();
                addTerminalLine('Removed repository');
            }
        }
        
        async function connectGithub() {
            const token = document.getElementById('github-token').value.trim();
            const owner = document.getElementById('github-owner').value.trim();
            const repo  = document.getElementById('github-repo').value.trim();
            if (!token || !owner || !repo) { addTerminalLine(' Please fill in all fields'); return; }
            
            const response = await fetch('/api/add-github-repo', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ token, owner, repo })
            });
            const data = await response.json();
            if (data.success) {
                closeModal();
                document.getElementById('github-token').value = '';
                document.getElementById('github-owner').value = '';
                document.getElementById('github-repo').value = '';
                await loadGithubRepos();
                await loadFileList();
                addTerminalLine(` Added repository: ${owner}/${repo}`);
            } else {
                addTerminalLine(` Failed: ${data.error}`);
            }
        }
        
        function toggleFolder(repoName) {
            const folder = document.getElementById('folder-' + repoName.replace(/\//g, '-'));
            if (folder) folder.classList.toggle('collapsed');
        }
        function toggleSubfolder(folderId) {
            const folder = document.getElementById(folderId);
            if (folder) folder.classList.toggle('collapsed');
        }
        
        let dragSrc = null;

        function addDragEvents(el) {
            el.addEventListener('dragstart', e => {
                dragSrc = el;
                el.classList.add('dragging');
                e.dataTransfer.effectAllowed = 'move';
            });
            el.addEventListener('dragend', () => {
                dragSrc = null;
                el.classList.remove('dragging');
                document.querySelectorAll('.drag-over-top, .drag-over-bottom')
                    .forEach(d => { d.classList.remove('drag-over-top'); d.classList.remove('drag-over-bottom'); });
            });
            el.addEventListener('dragover', e => {
                e.preventDefault();
                if (!dragSrc || dragSrc === el) return;
                document.querySelectorAll('.drag-over-top, .drag-over-bottom')
                    .forEach(d => { d.classList.remove('drag-over-top'); d.classList.remove('drag-over-bottom'); });
                const rect = el.getBoundingClientRect();
                const mid = rect.top + rect.height / 2;
                if (e.clientY < mid) {
                    el.classList.add('drag-over-top');
                } else {
                    el.classList.add('drag-over-bottom');
                }
            });
            el.addEventListener('dragleave', () => {
                el.classList.remove('drag-over-top');
                el.classList.remove('drag-over-bottom');
            });
            el.addEventListener('drop', e => {
                e.preventDefault();
                if (!dragSrc || dragSrc === el) return;
                const rect = el.getBoundingClientRect();
                const mid = rect.top + rect.height / 2;
                if (e.clientY < mid) {
                    el.parentNode.insertBefore(dragSrc, el);
                } else {
                    el.parentNode.insertBefore(dragSrc, el.nextSibling);
                }
                el.classList.remove('drag-over-top');
                el.classList.remove('drag-over-bottom');
            });
        }

        function makeDragHandle() {
            const h = document.createElement('span');
            h.className = 'drag-handle';
            h.textContent = '⠿';
            h.title = 'Drag to reorder';
            h.addEventListener('mousedown', e => e.stopPropagation());
            return h;
        }
        
        function buildFolderTree(files, repoName) {
            const tree = {};
            const rootFiles = [];

            files.forEach(file => {
                if (file.type === 'dir') {
                    const folderName = file.path.split('/')[0];
                    if (!tree[folderName]) tree[folderName] = [];
                } else if (file.type === 'file') {
                    if (file.name === '.gitkeep' || file.name === '.keep') return;
                    const parts = file.path.split('/');
                    if (parts.length === 1) {
                        rootFiles.push(file);
                    } else {
                        const folderName = parts[0];
                        if (!tree[folderName]) tree[folderName] = [];
                        tree[folderName].push(file);
                    }
                }
            });

            return { tree, rootFiles };
        }
        
        async function loadFileList() {
            try {
                const response = await fetch('/api/list-all-files');
                const data = await response.json();
                
                const fileList = document.getElementById('file-list');
                fileList.innerHTML = '';
                
                if (data.error) {
                    fileList.innerHTML = `<div style="color: #ef4444;">${data.error}</div>`;
                    updateVSCodeFileList([]);
                    return;
                }
                
                if (data.files && data.files.length > 0 || Object.keys(pendingCreateFolders).length > 0 || pendingCreates.length > 0) {
                    const grouped = {};
                    (data.files || []).forEach(file => {
                        if (!grouped[file.repo]) grouped[file.repo] = [];
                        grouped[file.repo].push(file);
                    });
                    for (const [repo, folders] of Object.entries(pendingCreateFolders)) {
                        if (!grouped[repo]) grouped[repo] = [];
                        for (const fp of folders) {
                            grouped[repo].push({ name: fp.split('/').pop(), path: fp, repo, type: 'dir', pending: true });
                        }
                    }
                    for (const pc of pendingCreates) {
                        if (!grouped[pc.repo]) grouped[pc.repo] = [];
                        const name = pc.path.split('/').pop();
                        if (name !== '.gitkeep') {
                            grouped[pc.repo].push({ name, path: pc.path, repo: pc.repo, type: 'file', sha: '', pending: true });
                        }
                    }
                    
                    Object.keys(grouped).sort().forEach(repoName => {
                        const repoDiv = document.createElement('div');
                        repoDiv.className = 'repo-folder';
                        repoDiv.id = 'folder-' + repoName.replace(/\//g, '-');
                        
                        const headerDiv = document.createElement('div');
                        headerDiv.className = 'repo-folder-header';
                        
                        const nameSpan = document.createElement('span');
                        nameSpan.textContent = `[${repoName}]`;
                        nameSpan.onclick = () => toggleFolder(repoName);
                        nameSpan.style.flex = '1';
                        
                        const actionsDiv = document.createElement('div');
                        actionsDiv.className = 'repo-actions';
                        
                        const newFileBtn = document.createElement('button');
                        newFileBtn.className = 'repo-action-btn';
                        newFileBtn.textContent = '+ File';
                        newFileBtn.onclick = e => { e.stopPropagation(); showNewFileModal(repoName); };
                        
                        const newFolderBtn = document.createElement('button');
                        newFolderBtn.className = 'repo-action-btn';
                        newFolderBtn.textContent = '+ Folder';
                        newFolderBtn.onclick = e => { e.stopPropagation(); showNewFolderModal(repoName, ''); };
                        
                        actionsDiv.appendChild(newFileBtn);
                        actionsDiv.appendChild(newFolderBtn);
                        headerDiv.appendChild(nameSpan);
                        headerDiv.appendChild(actionsDiv);
                        repoDiv.appendChild(headerDiv);
                        
                        const filesContainer = document.createElement('div');
                        filesContainer.className = 'repo-folder-files';
                        
                        const { tree, rootFiles } = buildFolderTree(grouped[repoName], repoName);
                        
                        Object.keys(tree).sort().forEach(folderName => {
                            const folderId = 'subfolder-' + repoName.replace(/\//g, '-') + '-' + folderName.replace(/\//g, '-');
                            
                            const subfolderDiv = document.createElement('div');
                            subfolderDiv.className = 'subfolder';
                            subfolderDiv.id = folderId;
                            
                            const subfolderHeader = document.createElement('div');
                            const folderIsPendingCreate = pendingCreateFolders[repoName] && pendingCreateFolders[repoName].has(folderName);
                            const folderIsPendingDel = isFolderPendingDelete(repoName, folderName);
                            subfolderHeader.className = 'subfolder-header' + (folderIsPendingCreate ? ' pending-create' : '') + (folderIsPendingDel ? ' pending-delete' : '');

                            const sfHandle = document.createElement('span');
                            sfHandle.className = 'subfolder-drag';
                            sfHandle.textContent = '⠿';
                            sfHandle.title = 'Drag to reorder';
                            subfolderHeader.appendChild(sfHandle);

                            const sfArrow = document.createElement('span');
                            sfArrow.className = 'subfolder-arrow';
                            sfArrow.textContent = '▼';
                            sfArrow.onclick = () => toggleSubfolder(folderId);
                            subfolderHeader.appendChild(sfArrow);

                            const sfLabel = document.createElement('span');
                            sfLabel.className = 'subfolder-name';
                            sfLabel.textContent = folderName;
                            sfLabel.style.flex = '1';
                            sfLabel.style.cursor = 'pointer';
                            sfLabel.onclick = () => toggleSubfolder(folderId);
                            subfolderHeader.appendChild(sfLabel);

                            const sfFolderBtn = document.createElement('button');
                            sfFolderBtn.className = 'repo-action-btn';
                            sfFolderBtn.textContent = '+ Folder';
                            sfFolderBtn.title = `Create folder inside ${folderName}`;
                            sfFolderBtn.onclick = e => {
                                e.stopPropagation();
                                showNewFolderModal(repoName, folderName);
                            };
                            subfolderHeader.appendChild(sfFolderBtn);

                            const sfFileBtn = document.createElement('button');
                            sfFileBtn.className = 'repo-action-btn';
                            sfFileBtn.textContent = '+ File';
                            sfFileBtn.title = `Create file inside ${folderName}`;
                            sfFileBtn.onclick = e => {
                                e.stopPropagation();
                                selectedRepoForNewFile = repoName;
                                document.getElementById('new-file-repo-name').textContent = repoName;
                                document.getElementById('new-file-path').value = folderName + '/';
                                document.getElementById('new-file-modal').classList.add('active');
                            };
                            subfolderHeader.appendChild(sfFileBtn);

                            const sfDelBtn = document.createElement('button');
                            sfDelBtn.className = 'delete-btn';
                            if (folderIsPendingDel) {
                                sfDelBtn.textContent = '';
                                sfDelBtn.style.color = '#f97316';
                                sfDelBtn.title = `Undo staged deletion of folder ${folderName}`;
                                sfDelBtn.onclick = e => { e.stopPropagation(); unstageFolderDelete(folderName, repoName); };
                            } else {
                                sfDelBtn.textContent = '✕';
                                sfDelBtn.title = `Delete folder ${folderName} and all its files`;
                                sfDelBtn.onclick = e => { e.stopPropagation(); confirmDeleteFolder(folderName, repoName); };
                            }
                            subfolderHeader.appendChild(sfDelBtn);
                            
                            subfolderDiv.appendChild(subfolderHeader);
                            
                            const subfolderFiles = document.createElement('div');
                            subfolderFiles.className = 'subfolder-files';
                            
                            tree[folderName].forEach(file => {
                                const fileDiv = document.createElement('div');
                                const isPendingDel = isFilePendingDelete(file.repo, file.path);
                                const isPendingCreate = !!file.pending;
                                fileDiv.className = 'file-item subfolder-file' + (isPendingDel ? ' pending-delete' : '') + (isPendingCreate ? ' pending-create' : '');
                                fileDiv.draggable = true;

                                const handle = makeDragHandle();
                                const label = document.createElement('span');
                                label.className = 'file-label';
                                label.textContent = file.name;
                                if (!isPendingDel) {
                                    label.onclick = () => loadFile(file.path, file.name, 'github', file.repo, file.sha || '');
                                } else {
                                    label.title = 'Staged for deletion Commit All to apply';
                                }

                                const delBtn = document.createElement('button');
                                delBtn.className = 'delete-btn';
                                delBtn.textContent = isPendingDel ? '' : '✕';
                                delBtn.title = isPendingDel ? `Undo staged delete for ${file.name}` : `Delete ${file.name}`;
                                if (isPendingDel) {
                                    delBtn.style.color = '#f97316';
                                    delBtn.onclick = e => { e.stopPropagation(); unstageDelete(file.path, file.repo); };
                                } else {
                                    delBtn.onclick = e => { e.stopPropagation(); confirmDeleteFile(file.path, file.sha, file.repo); };
                                }

                                fileDiv.appendChild(handle);
                                fileDiv.appendChild(label);
                                fileDiv.appendChild(delBtn);
                                addDragEvents(fileDiv);
                                subfolderFiles.appendChild(fileDiv);
                            });
                            
                            subfolderDiv.appendChild(subfolderFiles);
                            filesContainer.appendChild(subfolderDiv);
                        });
                        
                        rootFiles.forEach(file => {
                            const fileDiv = document.createElement('div');
                            const isPendingDel = isFilePendingDelete(file.repo, file.path);
                            const isPendingCreate = !!file.pending;
                            fileDiv.className = 'file-item' + (isPendingDel ? ' pending-delete' : '') + (isPendingCreate ? ' pending-create' : '');
                            fileDiv.draggable = true;

                            const handle = makeDragHandle();
                            const label = document.createElement('span');
                            label.className = 'file-label';
                            label.textContent = file.name;
                            if (!isPendingDel) {
                                label.onclick = () => loadFile(file.path, file.name, 'github', file.repo, file.sha || '');
                            } else {
                                label.title = 'Staged for deletion Commit All to apply';
                            }

                            const delBtn = document.createElement('button');
                            delBtn.className = 'delete-btn';
                            delBtn.textContent = isPendingDel ? '' : '✕';
                            delBtn.title = isPendingDel ? `Undo staged delete for ${file.name}` : `Delete ${file.name}`;
                            if (isPendingDel) {
                                delBtn.style.color = '#f97316';
                                delBtn.onclick = e => { e.stopPropagation(); unstageDelete(file.path, file.repo); };
                            } else {
                                delBtn.onclick = e => { e.stopPropagation(); confirmDeleteFile(file.path, file.sha, file.repo); };
                            }

                            fileDiv.appendChild(handle);
                            fileDiv.appendChild(label);
                            fileDiv.appendChild(delBtn);
                            addDragEvents(fileDiv);
                            filesContainer.appendChild(fileDiv);
                        });
                        
                        repoDiv.appendChild(filesContainer);
                        fileList.appendChild(repoDiv);
                    });
                    
                    addTerminalLine(`Found ${data.files.length} files`);
                    updateVSCodeFileList(data.files);
                } else {
                    fileList.innerHTML = '<div style="color: #999999;">No files found</div>';
                    updateVSCodeFileList([]);
                }
            } catch (error) {
                addTerminalLine(`Error: ${error.message}`);
                updateVSCodeFileList([]);
            }
        }
        
        function updateVSCodeFileList(allFiles) {
            const container = document.getElementById('vscode-files');
            if (!currentFile) {
                container.innerHTML = '<p style="color: #64748b; font-size: 11px;">Load a file first</p>';
            } else {
                container.innerHTML = '<button class="btn btn-success btn-small" style="width: 100%;" onclick="openCurrentInVSCode()">Open in VS Code</button>';
            }
        }
        
        async function openCurrentInVSCode() {
            if (!currentFile) { addTerminalLine(' Load a file first'); return; }
            try {
                const response = await fetch('/api/open-in-vscode-git', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ filename: currentFile, filepath: currentFilePath, repo: currentRepo })
                });
                const data = await response.json();
                if (data.success) {
                    addTerminalLine(` Opened in VS Code: ${data.repo_path}`);
                    addTerminalLine('You can now commit/push from VS Code');
                } else {
                    addTerminalLine(` Error: ${data.error}`);
                }
            } catch (error) {
                addTerminalLine(` Error: ${error.message}`);
            }
        }
        
        async function loadFile(filepath, filename, source, repo, sha = '') {
            try {
                const response = await fetch('/api/load-file', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ filepath, source: 'github', repo, reload: true })
                });
                const data = await response.json();
                
                if (data.content !== undefined) {
                    editor.setValue(data.content);
                    currentFile = filename;
                    currentFilePath = filepath;
                    currentSource = 'github';
                    currentRepo = repo;
                    currentSha = data.sha || sha;
                    document.getElementById('current-file').textContent = `${filepath} [${repo}]`;
                    document.getElementById('commit-btn').style.display = 'inline-block';
                    
                    const ext = filename.split('.').pop();
                    const langMap = {
                        'py': 'python', 'js': 'javascript', 'html': 'html', 'css': 'css',
                        'json': 'json', 'yaml': 'yaml', 'yml': 'yaml', 'sh': 'shell', 'md': 'markdown'
                    };
                    monaco.editor.setModelLanguage(editor.getModel(), langMap[ext] || 'plaintext');
                    updateVSCodeFileList([]);
                    addTerminalLine(`Loaded ${filepath} from GitHub (${data.content.split('\\n').length} lines)`);
                    editor.focus();
                } else {
                    addTerminalLine(`Error: ${data.error}`);
                }
            } catch (error) {
                addTerminalLine(`Error: ${error.message}`);
            }
        }
        
        async function saveFile() {
            if (!currentFilePath) { addTerminalLine('No file selected'); return; }
            const content = editor.getValue();
            try {
                const response = await fetch('/api/save-file', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ filepath: currentFilePath, content, source: 'github', repo: currentRepo, sha: currentSha, commit: false })
                });
                const data = await response.json();
                if (data.success) {
                    addTerminalLine(` Saved ${currentFile} locally`);
                } else {
                    addTerminalLine(` Error: ${data.error}`);
                }
            } catch (error) {
                addTerminalLine(` Error: ${error.message}`);
            }
        }
        
        async function doPush(content) {
            try {
                const response = await fetch('/api/save-file', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ filepath: currentFilePath, content, source: 'github', repo: currentRepo, sha: currentSha, commit: true })
                });
                const data = await response.json();
                if (data.success) {
                    if (data.sha) currentSha = data.sha;
                    addTerminalLine(`Pushed ${currentFile} to GitHub successfully.`);
                } else {
                    addTerminalLine(`Push failed: ${data.error}`);
                }
            } catch(e) {
                addTerminalLine(`Push error: ${e.message}`);
            }
        }

        async function commitToGithub() {
            if (!currentFilePath) { addTerminalLine('Not a GitHub file'); return; }
            const content = editor.getValue();

            if (currentFile.endsWith('.py')) {
                addTerminalLine('Running lint check before push...');
                try {
                    const lr = await fetch('/api/pre-push-lint', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ content, filename: currentFile })
                    });
                    const ld = await lr.json();
                    if (!ld.passed) {
                        addTerminalLine(`LINT FAILED push blocked. ${currentFile} has issues:`);
                        ld.issues.forEach(i => addTerminalLine('  ' + i));
                        addTerminalLine(`Fix the issues in ${currentFile} above then try pushing again.`);
                        return;
                    }
                    addTerminalLine('Lint passed pipeline must run before push.');
                } catch(e) {
                    addTerminalLine('Could not run lint check.');
                    return;
                }
            }

            showPipelineModal(currentRepo, content);
            return;

            try {
                const response = await fetch('/api/save-file', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ filepath: currentFilePath, content, source: 'github', repo: currentRepo, sha: currentSha, commit: true })
                });
                const data = await response.json();
                if (data.success) {
                    if (data.sha) currentSha = data.sha;
                    addTerminalLine(` Pushed to ${currentRepo}`);
                    fetch('/api/trigger-lint', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ repo: currentRepo })
                    }).then(r => r.json()).then(d => {
                        if (d.success) {
                            addTerminalLine(`Lint triggered for ${currentRepo} polling result...`);
                            let polls = 0;
                            const pollLint = setInterval(async () => {
                                polls++;
                                if (polls > 24) { clearInterval(pollLint); addTerminalLine(' Lint check timed out check Jenkins manually'); return; }
                                try {
                                    const lr = await fetch('/api/check-lint-result', {method:'POST', headers:{'Content-Type':'application/json'}, body:'{}'});
                                    const ld = await lr.json();
                                    if (!ld.building && ld.result) {
                                        clearInterval(pollLint);
                                        if (ld.result === 'SUCCESS') addTerminalLine(`Jenkins lint PASSED all repo files are clean, safe to merge`);
                                        else addTerminalLine(`Jenkins lint found issues in other repo files check Jenkins for details`);
                                    }
                                } catch(e) {}
                            }, 5000);
                        } else addTerminalLine(` Could not trigger lint: ${d.error}`);
                    }).catch(() => {});
                    showPipelineModal(currentRepo, content);
                } else {
                    addTerminalLine(`Error: ${data.error}`);
                }
            } catch (error) {
                addTerminalLine(`Error: ${error.message}`);
            }
        }
        
        async function reloadFile() {
            if (!currentFilePath) { addTerminalLine('No file loaded'); return; }
            try {
                const response = await fetch('/api/reload-file', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ filepath: currentFilePath, source: 'github', repo: currentRepo })
                });
                const data = await response.json();
                if (data.content !== undefined) {
                    editor.setValue(data.content);
                    currentSha = data.sha || currentSha;
                    addTerminalLine(` Reloaded from GitHub (cleared local save)`);
                    editor.focus();
                } else {
                    addTerminalLine(`Error: ${data.error}`);
                }
            } catch (error) {
                addTerminalLine(`Error: ${error.message}`);
            }
        }
        
        async function loadPendingDeletes() {
            try {
                const r = await fetch('/api/pending-deletes');
                const data = await r.json();
                pendingDeletes = {};
                pendingStagedFolders = {};
                for (const [repo, items] of Object.entries(data)) {
                    pendingDeletes[repo] = new Set(items.map(i => i.path));
                    pendingStagedFolders[repo] = new Set(
                        items.filter(i => i.folder_delete).map(i => i.path.split('/')[0])
                    );
                }
            } catch(e) {}
        }

        function isFilePendingDelete(repo, filepath) {
            return pendingDeletes[repo] && pendingDeletes[repo].has(filepath);
        }

        function isFolderPendingDelete(repo, folderName) {
            return pendingStagedFolders[repo] && pendingStagedFolders[repo].has(folderName);
        }

        async function unstageDelete(filepath, repo) {
            try {
                const r = await fetch('/api/unstage-delete', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ filepath, repo })
                });
                const d = await r.json();
                if (d.success) {
                    addTerminalLine(` Unstaged delete for ${filepath.split('/').pop()}`);
                    await loadPendingDeletes();
                    await loadFileList();
                } else {
                    addTerminalLine(` Undo failed: ${d.error}`);
                }
            } catch(e) { addTerminalLine(` Error: ${e.message}`); }
        }

        async function unstageFolderDelete(folderName, repo) {
            try {
                const r = await fetch('/api/unstage-folder-delete', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ folder: folderName, repo })
                });
                const d = await r.json();
                if (d.success) {
                    addTerminalLine(` Unstaged deletion of folder ${folderName} (${d.restored} file(s) restored)`);
                    await loadPendingDeletes();
                    await loadFileList();
                } else {
                    addTerminalLine(` Undo failed: ${d.error}`);
                }
            } catch(e) { addTerminalLine(` Error: ${e.message}`); }
        }

        async function confirmDeleteFile(filepath, sha, repo) {
            const name = filepath.split('/').pop();
            if (!confirm(`Mark "${name}" for deletion?\n\nNothing changes on GitHub yet.\nHit Save All -> then Commit All to apply.`)) return;
            try {
                const response = await fetch('/api/delete-file', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ filepath, sha, repo })
                });
                const data = await response.json();
                if (data.success) {
                    addTerminalLine(` Staged delete: ${filepath} hit Commit All to push to GitHub`);
                    if (currentFilePath === filepath) {
                        currentFile = ''; currentFilePath = ''; currentRepo = ''; currentSha = '';
                        editor.setValue('');
                        document.getElementById('current-file').textContent = 'No file selected';
                        document.getElementById('commit-btn').style.display = 'none';
                    }
                    await loadPendingDeletes();
                    await loadFileList();
                } else {
                    addTerminalLine(` Stage delete failed: ${data.error}`);
                }
            } catch (e) { addTerminalLine(` Error: ${e.message}`); }
        }

        async function confirmDeleteFolder(folderName, repo) {
            if (!confirm(`Mark folder "${folderName}" and ALL its files for deletion?\n\nNothing changes on GitHub yet.\nHit Save All -> then Commit All to apply.`)) return;
            addTerminalLine(`Staging folder ${folderName} for deletion...`);
            try {
                const response = await fetch('/api/delete-folder', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ folder: folderName, repo })
                });
                const data = await response.json();
                if (data.success) {
                    addTerminalLine(` Staged ${data.staged} files for deletion hit Commit All to push to GitHub`);
                    if (currentFilePath.startsWith(folderName + '/')) {
                        currentFile = ''; currentFilePath = ''; currentRepo = ''; currentSha = '';
                        editor.setValue('');
                        document.getElementById('current-file').textContent = 'No file selected';
                        document.getElementById('commit-btn').style.display = 'none';
                    }
                    await loadPendingDeletes();
                    await loadFileList();
                } else {
                    addTerminalLine(` Stage delete failed: ${data.error}`);
                }
            } catch (e) { addTerminalLine(` Error: ${e.message}`); }
        }

        async function saveAllEdits() {
            let savedAnything = false;

            if (currentFilePath) {
                const content = editor.getValue();
                try {
                    const response = await fetch('/api/save-file', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ filepath: currentFilePath, content, source: 'github', repo: currentRepo, sha: currentSha, commit: false })
                    });
                    const data = await response.json();
                    if (data.success) {
                        lastSavedPath = currentFilePath;
                        addTerminalLine(` Saved ${currentFile} locally`);
                        savedAnything = true;
                    } else {
                        addTerminalLine(` Save failed: ${data.error}`);
                    }
                } catch (e) { addTerminalLine(` Error: ${e.message}`); }
            }

            if (pendingCreates.length > 0) {
                const toCreate = [...pendingCreates];
                pendingCreates = [];
                for (const pc of toCreate) {
                    try {
                        const r = await fetch('/api/create-file', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ repo: pc.repo, path: pc.path })
                        });
                        const d = await r.json();
                        if (d.success) {
                            addTerminalLine(` Created ${pc.path} on GitHub`);
                            if (pc.folderPath && pendingCreateFolders[pc.repo]) {
                                pendingCreateFolders[pc.repo].delete(pc.folderPath);
                            }
                            savedAnything = true;
                        } else {
                            addTerminalLine(` Failed to create ${pc.path}: ${d.error}`);
                            pendingCreates.push(pc);
                        }
                    } catch(e) { addTerminalLine(` Error creating ${pc.path}: ${e.message}`); pendingCreates.push(pc); }
                }
                await loadFileList();
            }

            const pending = await (await fetch('/api/pending-deletes')).json();
            let stagedCount = 0;
            for (const items of Object.values(pending)) stagedCount += items.length;
            if (stagedCount > 0) {
                addTerminalLine(` ${stagedCount} deletion(s) staged hit Commit All to push to GitHub`);
                savedAnything = true;
            }

            if (!savedAnything) { addTerminalLine('Nothing to save'); }
        }

        async function commitAllEdits() {
            let didSomething = false;
            let fileContentWasPushed = false;

            if (currentFilePath && lastSavedPath === currentFilePath) {
                const content = editor.getValue();
                try {
                    const response = await fetch('/api/save-file', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ filepath: currentFilePath, content, source: 'github', repo: currentRepo, sha: currentSha, commit: true })
                    });
                    const data = await response.json();
                    if (data.success) {
                        if (data.sha) currentSha = data.sha;
                        lastSavedPath = '';
                        addTerminalLine(` Committed & pushed ${currentFile} to GitHub`);
                        didSomething = true;
                        fileContentWasPushed = true;
                        fetch('/api/trigger-lint', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ repo: currentRepo })
                        }).then(r => r.json()).then(d => {
                            if (d.success) addTerminalLine(` Lint triggered for ${currentRepo} check Jenkins`);
                            else addTerminalLine(` Could not trigger lint: ${d.error}`);
                        }).catch(() => {});
                    } else {
                        addTerminalLine(` Commit failed: ${data.error}`);
                    }
                } catch (e) { addTerminalLine(` Error: ${e.message}`); }
            } else if (currentFilePath && lastSavedPath !== currentFilePath) {
                addTerminalLine(` ${currentFile} has unsaved changes hit Save All first`);
            }

            const pending = await (await fetch('/api/pending-deletes')).json();
            for (const repo of Object.keys(pending)) {
                if (!pending[repo] || pending[repo].length === 0) continue;
                try {
                    const r = await fetch('/api/commit-deletes', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ repo })
                    });
                    const d = await r.json();
                    if (d.success) {
                        addTerminalLine(` Committed ${d.deleted} deletion(s) to ${repo}`);
                        didSomething = true;
                    } else {
                        addTerminalLine(` Delete commit failed: ${d.error}`);
                    }
                } catch(e) { addTerminalLine(` Error: ${e.message}`); }
            }

            if (!didSomething) { addTerminalLine('Nothing to commit'); }
            await loadPendingDeletes();
            await loadFileList();
            if (fileContentWasPushed) { showPipelineModal(currentRepo); }
        }

        (function() {
            const resizer = document.getElementById('panel-resizer');
            const container = resizer ? resizer.closest('.main-container') : null;
            if (!resizer || !container) return;
            let startX, startWidth;
            resizer.addEventListener('mousedown', e => {
                startX = e.clientX;
                const leftPanel = container.querySelector('.left-panel');
                startWidth = leftPanel.getBoundingClientRect().width;
                resizer.classList.add('dragging');
                document.body.style.cursor = 'col-resize';
                document.body.style.userSelect = 'none';
                function onMove(e) {
                    const delta = e.clientX - startX;
                    const maxW = Math.min(600, window.innerWidth - 400);
                    const newWidth = Math.max(220, Math.min(maxW, startWidth + delta));
                    container.style.setProperty('--left-width', newWidth + 'px');
                }
                function onUp() {
                    resizer.classList.remove('dragging');
                    document.body.style.cursor = '';
                    document.body.style.userSelect = '';
                    document.removeEventListener('mousemove', onMove);
                    document.removeEventListener('mouseup', onUp);
                }
                document.addEventListener('mousemove', onMove);
                document.addEventListener('mouseup', onUp);
                e.preventDefault();
            });
        })();

        (function() {
            const rowResizer = document.getElementById('row-resizer');
            const rightCol   = rowResizer ? rowResizer.closest('.right-col') : null;
            if (!rowResizer || !rightCol) return;
            let startY, startH;
            rowResizer.addEventListener('mousedown', e => {
                startY = e.clientY;
                const terminal = rightCol.querySelector('.command-line');
                startH = terminal.getBoundingClientRect().height;
                rowResizer.classList.add('dragging');
                document.body.style.cursor = 'row-resize';
                document.body.style.userSelect = 'none';
                function onMove(e) {
                    const delta  = startY - e.clientY;
                    const totalH = rightCol.getBoundingClientRect().height;
                    const newH   = Math.max(80, Math.min(totalH - 150, startH + delta));
                    rightCol.style.setProperty('--terminal-height', newH + 'px');
                }
                function onUp() {
                    rowResizer.classList.remove('dragging');
                    document.body.style.cursor = '';
                    document.body.style.userSelect = '';
                    document.removeEventListener('mousemove', onMove);
                    document.removeEventListener('mouseup', onUp);
                }
                document.addEventListener('mousemove', onMove);
                document.addEventListener('mouseup', onUp);
                e.preventDefault();
            });
        })();

        document.querySelectorAll('.box-resizer').forEach(resizer => {
            const targetId = resizer.getAttribute('data-target');
            const box = targetId ? document.getElementById(targetId) : null;
            if (!box) return;
            let startY, startHeight;
            resizer.addEventListener('mousedown', e => {
                startY = e.clientY;
                startHeight = box.getBoundingClientRect().height;
                resizer.classList.add('dragging');
                document.body.style.cursor = 'row-resize';
                document.body.style.userSelect = 'none';
                function onMove(e) {
                    const delta = e.clientY - startY;
                    const leftPanel = document.querySelector('.left-panel');
                    const panelH = leftPanel ? leftPanel.getBoundingClientRect().height : 800;
                    const maxH = Math.max(100, panelH - 100);
                    const newHeight = Math.max(50, Math.min(maxH, startHeight + delta));
                    box.style.flex = 'none';
                    box.style.height = newHeight + 'px';
                }
                function onUp() {
                    resizer.classList.remove('dragging');
                    document.body.style.cursor = '';
                    document.body.style.userSelect = '';
                    document.removeEventListener('mousemove', onMove);
                    document.removeEventListener('mouseup', onUp);
                }
                document.addEventListener('mousemove', onMove);
                document.addEventListener('mouseup', onUp);
                e.preventDefault();
            });
        });

        function refreshFiles() { loadFileList(); }
        function goToDashboard() { window.location.href = 'http://localhost:8080'; }
        function checkPipelines() { window.location.href = 'http://localhost:7000'; }
        
        let _pipelineRepo = null;

        async function showPipelineModal(repo, pendingContent) {
            _pendingPushContent = pendingContent || null;
            _pipelineRepo = repo;
            const status = document.getElementById('pipeline-modal-status');
            status.textContent = '';
            document.getElementById('pipeline-name-input').value = '';
            document.getElementById('pipeline-existing-select').value = '';
            const changeLabel = document.getElementById('pipeline-change-label');
            if (changeLabel) changeLabel.style.display = 'none';

            const res  = await fetch('/api/get-pipeline-for-repo', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ repo })
            });
            const data = await res.json();

            const linkedSection   = document.getElementById('pipeline-linked-section');
            const unlinkedSection = document.getElementById('pipeline-unlinked-section');
            const msg             = document.getElementById('pipeline-modal-msg');
            const linkBtn         = document.getElementById('pipeline-modal-link');

            if (data.pipeline) {
                msg.textContent = `Repo "${repo}" is already linked to a Jenkins pipeline:`;
                document.getElementById('pipeline-linked-name').textContent = ' ' + data.pipeline;
                linkedSection.style.display   = 'block';
                unlinkedSection.style.display = 'none';
                linkBtn.textContent = 'Update Link';
                linkBtn.style.background = '#f59e0b';
                document.getElementById('run-pipeline-btn').style.display = 'inline-block';
                document.getElementById('run-pipeline-btn').onclick = () => runLinkedPipeline(data.pipeline);
                linkBtn.onclick = () => {
                    const sec = document.getElementById('pipeline-unlinked-section');
                    const changeLabel = document.getElementById('pipeline-change-label');
                    if (sec.style.display === 'none') {
                        sec.style.display = 'block';
                        if (changeLabel) changeLabel.style.display = 'block';
                        linkBtn.textContent = 'Confirm Update';
                        linkBtn.style.background = '#3b82f6';
                        loadJenkinsJobs();
                    } else {
                        linkPipeline();
                    }
                };
            } else {
                msg.textContent = `Repo "${repo}" is not linked to a Jenkins pipeline yet. Pick an existing job or create a new empty one:`;
                linkedSection.style.display   = 'none';
                unlinkedSection.style.display = 'block';
                linkBtn.textContent = 'Link Pipeline';
                linkBtn.style.background = '#3b82f6';
                document.getElementById('run-pipeline-btn').style.display = 'none';
                loadJenkinsJobs();
                setTimeout(() => document.getElementById('pipeline-name-input').focus(), 100);
            }

            document.getElementById('pipeline-modal').style.display = 'flex';
        }

        async function loadJenkinsJobs() {
            const select = document.getElementById('pipeline-existing-select');
            select.innerHTML = '<option value="">Loading...</option>';
            try {
                const res  = await fetch('/api/list-jenkins-jobs');
                const data = await res.json();
                select.innerHTML = '<option value=""> select existing job </option>';
                (data.jobs || []).forEach(j => {
                    const opt = document.createElement('option');
                    opt.value = j;
                    opt.textContent = j;
                    select.appendChild(opt);
                });
            } catch(e) {
                select.innerHTML = '<option value="">Could not load jobs</option>';
            }
        }

        function onExistingSelect() {
            const val = document.getElementById('pipeline-existing-select').value;
            if (val) document.getElementById('pipeline-name-input').value = '';
        }

        function onNameInput() {
            const val = document.getElementById('pipeline-name-input').value.trim();
            if (val) document.getElementById('pipeline-existing-select').value = '';
        }

        async function runLinkedPipeline(pipelineName) {
            const status = document.getElementById('pipeline-modal-status');
            status.style.color = '#94a3b8';
            addTerminalLine('Getting current build number before triggering...');

            let buildNumBefore = 0;
            try {
                const preR = await fetch('/api/check-pipeline-result', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ pipeline: pipelineName })
                });
                const preD = await preR.json();
                buildNumBefore = preD.number || 0;
                addTerminalLine('Build number before trigger: ' + buildNumBefore);
            } catch(e) {
                addTerminalLine('Could not get pre-trigger build number: ' + e.message);
            }

            status.textContent = 'Triggering ' + pipelineName + '...';
            addTerminalLine('Triggering pipeline: ' + pipelineName);
            try {
                const res = await fetch('/api/run-pipeline', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ pipeline: pipelineName })
                });
                const data = await res.json();
                if (!data.success) {
                    status.style.color = '#ef4444';
                    status.textContent = 'Failed to trigger: ' + data.error;
                    addTerminalLine('Failed to trigger pipeline: ' + data.error);
                    return;
                }
                addTerminalLine('Pipeline triggered waiting 8 seconds for Jenkins to register build...');
                status.textContent = 'Pipeline queued waiting for Jenkins...';
                await new Promise(r => setTimeout(r, 8000));

                let polls = 0;
                const pollPipeline = setInterval(async () => {
                    polls++;
                    if (polls > 40) {
                        clearInterval(pollPipeline);
                        status.style.color = '#ef4444';
                        status.textContent = 'Pipeline timed out push cancelled.';
                        addTerminalLine('Pipeline timed out push cancelled.');
                        return;
                    }
                    try {
                        const pr = await fetch('/api/check-pipeline-result', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ pipeline: pipelineName })
                        });
                        const pd = await pr.json();
                        const isNewBuild = (pd.number || 0) > buildNumBefore;
                        const isComplete = pd.building === false && pd.result !== null && pd.result !== undefined && pd.result !== '';
                        addTerminalLine('Poll ' + polls + ': build#=' + pd.number + ' building=' + pd.building + ' result=' + pd.result + ' isNew=' + isNewBuild);
                        if (isNewBuild && isComplete) {
                            clearInterval(pollPipeline);
                            if (pd.result === 'SUCCESS') {
                                status.style.color = '#22c55e';
                                status.textContent = 'Pipeline passed pushing to GitHub...';
                                addTerminalLine('Pipeline passed pushing to GitHub...');
                                closePipelineModal();
                                if (_pendingPushContent !== null) {
                                    await doPush(_pendingPushContent);
                                    _pendingPushContent = null;
                                } else {
                                    addTerminalLine('Warning: no pending content to push.');
                                }
                            } else {
                                status.style.color = '#ef4444';
                                status.textContent = 'Pipeline FAILED push blocked. Fix issues then retry.';
                                addTerminalLine('Pipeline FAILED push blocked. Fix issues then retry.');
                            }
                        } else if (!isNewBuild) {
                            addTerminalLine('Waiting for new build to start...');
                        } else {
                            addTerminalLine('Build running waiting for completion...');
                        }
                    } catch(e) {
                        addTerminalLine('Poll error: ' + e.message);
                    }
                }, 5000);
            } catch(e) {
                status.style.color = '#ef4444';
                status.textContent = 'Error: ' + e.message;
                addTerminalLine('Error: ' + e.message);
            }
        }

        function cancelPush() {
            closePipelineModal();
            addTerminalLine('Push cancelled run the pipeline first before pushing to GitHub.');
        }

        function closePipelineModal() {
            document.getElementById('pipeline-modal').style.display = 'none';
            document.getElementById('pipeline-modal-status').textContent = '';
        }

        async function linkPipeline() {
            const status   = document.getElementById('pipeline-modal-status');
            const existing = document.getElementById('pipeline-existing-select').value.trim();
            const newName  = document.getElementById('pipeline-name-input').value.trim();
            const choice   = existing || newName;

            if (!choice) {
                status.style.color = '#ef4444';
                status.textContent = 'Pick an existing pipeline or enter a new name.';
                return;
            }

            status.style.color = '#94a3b8';
            status.textContent = existing ? 'Linking to existing pipeline...' : 'Creating empty pipeline and linking...';
            document.getElementById('pipeline-modal-link').disabled = true;

            try {
                const res  = await fetch('/api/link-pipeline', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ repo: _pipelineRepo, pipeline_name: choice, create_new: !existing })
                });
                const text = await res.text();
                let data;
                try { data = JSON.parse(text); }
                catch(e) {
                    status.style.color = '#ef4444';
                    status.textContent = ' Server error: ' + text.substring(0, 120);
                    document.getElementById('pipeline-modal-link').disabled = false;
                    return;
                }
                if (data.success) {
                    status.style.color = '#22c55e';
                    status.textContent = data.message;
                    addTerminalLine(' ' + data.message);
                    setTimeout(closePipelineModal, 2000);
                } else {
                    status.style.color = '#ef4444';
                    status.textContent = ' ' + data.error;
                }
            } catch(e) {
                status.style.color = '#ef4444';
                status.textContent = ' ' + e.message;
            }

            document.getElementById('pipeline-modal-link').disabled = false;
        }

        function addTerminalLine(text) {
            const terminal = document.getElementById('terminal');
            terminal.innerHTML += '$ ' + text + '<br>';
            terminal.scrollTop = terminal.scrollHeight;
        }
    </script>

        <div id="pipeline-modal" style="display:none;position:fixed;inset:0;background:rgba(0,0,0,0.7);z-index:9999;align-items:center;justify-content:center;">
            <div style="background:#383838;border:1px solid #3b82f6;border-radius:12px;padding:30px;width:460px;box-shadow:0 20px 60px rgba(0,0,0,0.5);">
                <h3 style="color:#60a5fa;margin-bottom:6px;font-size:18px;">Link Jenkins Pipeline</h3>
                <p id="pipeline-modal-msg" style="color:#94a3b8;font-size:13px;margin-bottom:20px;line-height:1.5;"></p>

                <div id="pipeline-linked-section" style="display:none;margin-bottom:18px;">
                    <div style="background:#2a2a2a;border:1px solid #22c55e;border-radius:6px;padding:10px 14px;color:#22c55e;font-size:13px;font-weight:600;" id="pipeline-linked-name"></div>
                </div>

                <p id="pipeline-change-label" style="display:none;color:#f59e0b;font-size:12px;margin-bottom:10px;">
                     Pick a different pipeline or enter a new name to update the link:
                </p>
                <div id="pipeline-unlinked-section" style="display:none;margin-bottom:18px;">
                    <label style="color:#cbd5e1;font-size:13px;display:block;margin-bottom:6px;">Pick an existing Jenkins pipeline:</label>
                    <select id="pipeline-existing-select"
                        style="width:100%;background:#2a2a2a;border:1px solid #334155;border-radius:6px;
                               padding:8px 12px;color:#e2e8f0;font-size:14px;margin-bottom:14px;"
                        onchange="onExistingSelect()">
                        <option value=""> select existing job</option>
                    </select>

                    <div style="text-align:center;color:#475569;font-size:12px;margin-bottom:12px;"> or create a new one </div>

                    <label style="color:#cbd5e1;font-size:13px;display:block;margin-bottom:6px;">New pipeline name:</label>
                    <input id="pipeline-name-input" type="text" placeholder="e.g. my-pipeline"
                        style="width:100%;background:#2a2a2a;border:1px solid #334155;border-radius:6px;
                               padding:8px 12px;color:#e2e8f0;font-size:14px;outline:none;"
                        oninput="onNameInput()" />
                </div>

                <div style="display:flex;gap:10px;justify-content:flex-end;">
                    <button style="background:#334155;color:#94a3b8;border:none;padding:9px 18px;border-radius:6px;cursor:pointer;font-size:13px;"
                        onclick="cancelPush()">Cancel
                    </button>
                    <button id="run-pipeline-btn"
                        style="display:none;background:#22c55e;color:white;border:none;padding:9px 18px;border-radius:6px;cursor:pointer;font-size:13px;font-weight:600;">
                         Run Pipeline
                    </button>
                    <button id="pipeline-modal-link"
                        style="background:#3b82f6;color:white;border:none;padding:9px 18px;border-radius:6px;cursor:pointer;font-size:13px;font-weight:600;"
                        onclick="linkPipeline()">Link Pipeline
                    </button>
                </div>
                <p id="pipeline-modal-status" style="color:#22c55e;font-size:12px;margin-top:12px;min-height:16px;"></p>
            </div>
        </div>
</body>
</html>
'''

@app.route('/')
def workspace():
    if not _get_session().get("logged_in"):
        return redirect("http://localhost:5000")
    return render_template_string(WORKSPACE_TEMPLATE)

@app.route('/api/create-file', methods=['POST'])
def create_file():
    data = request.json
    repo = data.get('repo', '')
    path = data.get('path', '')
    if not repo or not path:
        return jsonify({'success': False, 'error': 'Missing repo or path'})
    content = ''
    try:
        repos = load_repos_from_file()
        for repo_config in repos:
            repo_name = f"{repo_config['owner']}/{repo_config['repo']}"
            if repo_name == repo:
                result = create_github_file(
                    repo_config['token'], repo_config['owner'], repo_config['repo'], path, content
                )
                return jsonify(result)
        return jsonify({'success': False, 'error': 'Repository not found'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/open-in-vscode-git', methods=['POST'])
def open_in_vscode_git():
    data = request.json
    filepath = data.get('filepath', '')
    repo     = data.get('repo', '')
    if not repo:
        return jsonify({'success': False, 'error': 'Not a GitHub file'})
    try:
        repos = load_repos_from_file()
        for repo_config in repos:
            repo_name = f"{repo_config['owner']}/{repo_config['repo']}"
            if repo_name == repo:
                result = clone_or_update_repo(repo_config['token'], repo_config['owner'], repo_config['repo'])
                if not result['success']:
                    return jsonify(result)
                file_path = os.path.join(result['path'], filepath)
                subprocess.Popen(['code', file_path])
                return jsonify({'success': True, 'repo_path': result['path']})
        return jsonify({'success': False, 'error': 'Repository not found'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/reload-file', methods=['POST'])
def reload_file():
    data = request.json
    filepath = data.get('filepath', '')
    repo     = data.get('repo', '')
    edits = load_edits_from_file()
    file_key = f"{repo}:{filepath}"
    if file_key in edits:
        del edits[file_key]
        save_edits_to_file(edits)
    repos = load_repos_from_file()
    for repo_config in repos:
        repo_name = f"{repo_config['owner']}/{repo_config['repo']}"
        if repo_name == repo:
            return jsonify(load_github_file(repo_config['token'], repo_config['owner'], repo_config['repo'], filepath))
    return jsonify({'error': 'Repository not found'})

@app.route('/api/list-github-repos')
def list_github_repos():
    repos = load_repos_from_file()
    return jsonify({'repos': [f"{r['owner']}/{r['repo']}" for r in repos]})


def setup_branch_protection(token, owner, repo):
    import urllib.request
    try:
        url = f'https://api.github.com/repos/{owner}/{repo}/branches/main/protection'
        payload = {
            "required_status_checks": None,
            "enforce_admins": False,
            "required_pull_request_reviews": None,
            "restrictions": None
        }
        req = urllib.request.Request(url, method='PUT')
        req.add_header('Authorization', f'token {token}')
        req.add_header('Accept', 'application/vnd.github.v3+json')
        req.add_header('Content-Type', 'application/json')
        urllib.request.urlopen(req, data=__import__('json').dumps(payload).encode(), timeout=10)
        return True
    except Exception as e:
        print(f"Branch protection setup failed: {e}")
        return False

@app.route('/api/add-github-repo', methods=['POST'])
def add_github_repo():
    data  = request.json
    token = data.get('token', '').strip()
    owner = data.get('owner', '').strip()
    repo  = data.get('repo',  '').strip()
    result = get_github_files(token, owner, repo)
    if result.get('error'):
        return jsonify({'success': False, 'error': result['error']})
    repos = load_repos_from_file()
    for existing in repos:
        if existing['owner'] == owner and existing['repo'] == repo:
            return jsonify({'success': False, 'error': 'Repository already added'})
    repos.append({'token': token, 'owner': owner, 'repo': repo})
    save_repos_to_file(repos)
    setup_branch_protection(token, owner, repo)
    return jsonify({'success': True})

@app.route('/api/remove-github-repo', methods=['POST'])
def remove_github_repo():
    data  = request.json
    index = data.get('index', -1)
    repos = load_repos_from_file()
    if 0 <= index < len(repos):
        repos.pop(index)
        save_repos_to_file(repos)
        return jsonify({'success': True})
    return jsonify({'success': False})

@app.route('/api/delete-file', methods=['POST'])
def api_delete_file():
    data = request.json
    filepath = data.get('filepath', '')
    sha      = data.get('sha', '')
    repo     = data.get('repo', '')
    if not filepath or not sha or not repo:
        return jsonify({'success': False, 'error': 'Missing fields'})
    edits = load_edits_from_file()
    file_key = f"{repo}:{filepath}"
    if file_key in edits:
        del edits[file_key]
        save_edits_to_file(edits)
    pending = load_pending_deletes()
    if repo not in pending:
        pending[repo] = []
    pending[repo] = [d for d in pending[repo] if d['path'] != filepath]
    pending[repo].append({'path': filepath, 'sha': sha, 'folder_delete': False})
    save_pending_deletes(pending)
    return jsonify({'success': True, 'staged': True})

@app.route('/api/delete-folder', methods=['POST'])
def api_delete_folder():
    data   = request.json
    folder = data.get('folder', '')
    repo   = data.get('repo', '')
    if not folder or not repo:
        return jsonify({'success': False, 'error': 'Missing fields'})
    repos = load_repos_from_file()
    for repo_config in repos:
        repo_name = f"{repo_config['owner']}/{repo_config['repo']}"
        if repo_name == repo:
            token = repo_config['token']
            owner = repo_config['owner']
            repo_name_only = repo_config['repo']
            files = get_folder_files_with_sha(token, owner, repo_name_only, folder)
            if not files:
                return jsonify({'success': False, 'error': 'Folder not found or already empty'})
            pending = load_pending_deletes()
            if repo not in pending:
                pending[repo] = []
            for f in files:
                edits = load_edits_from_file()
                file_key = f"{repo}:{f['path']}"
                if file_key in edits:
                    del edits[file_key]
                    save_edits_to_file(edits)
                pending[repo] = [d for d in pending[repo] if d['path'] != f['path']]
                pending[repo].append({'path': f['path'], 'sha': f['sha'], 'folder_delete': True})
            save_pending_deletes(pending)
            return jsonify({'success': True, 'staged': len(files), 'deleted': len(files)})
    return jsonify({'success': False, 'error': 'Repository not found'})

@app.route('/api/pending-deletes', methods=['GET'])
def api_get_pending_deletes():
    return jsonify(load_pending_deletes())

@app.route('/api/unstage-delete', methods=['POST'])
def api_unstage_delete():
    data = request.json
    filepath = data.get('filepath', '')
    repo     = data.get('repo', '')
    if not filepath or not repo:
        return jsonify({'success': False, 'error': 'Missing fields'})
    pending = load_pending_deletes()
    if repo in pending:
        before = len(pending[repo])
        pending[repo] = [d for d in pending[repo] if d['path'] != filepath]
        if not pending[repo]:
            del pending[repo]
        save_pending_deletes(pending)
        return jsonify({'success': True, 'removed': before - len(pending.get(repo, []))})
    return jsonify({'success': True, 'removed': 0})

@app.route('/api/unstage-folder-delete', methods=['POST'])
def api_unstage_folder_delete():
    data   = request.json
    folder = data.get('folder', '')
    repo   = data.get('repo', '')
    if not folder or not repo:
        return jsonify({'success': False, 'error': 'Missing fields'})
    pending = load_pending_deletes()
    if repo in pending:
        before = len(pending[repo])
        pending[repo] = [d for d in pending[repo] if not d['path'].startswith(folder + '/') and d['path'] != folder]
        restored = before - len(pending[repo])
        if not pending[repo]:
            del pending[repo]
        save_pending_deletes(pending)
        return jsonify({'success': True, 'restored': restored})
    return jsonify({'success': True, 'restored': 0})

@app.route('/api/commit-deletes', methods=['POST'])
def api_commit_deletes():
    data = request.json
    repo = data.get('repo', '')
    pending = load_pending_deletes()
    items = pending.get(repo, [])
    if not items:
        return jsonify({'success': True, 'deleted': 0, 'message': 'Nothing to delete'})
    repos = load_repos_from_file()
    for repo_config in repos:
        repo_name = f"{repo_config['owner']}/{repo_config['repo']}"
        if repo_name == repo:
            token = repo_config['token']
            owner = repo_config['owner']
            repo_name_only = repo_config['repo']
            deleted = 0
            errors = []
            affected_folders = set()
            for item in items:
                result = delete_github_file(token, owner, repo_name_only, item['path'], item['sha'])
                if result['success']:
                    deleted += 1
                    parts = item['path'].split('/')
                    if len(parts) > 1 and not item.get('folder_delete'):
                        affected_folders.add(parts[0])
                else:
                    errors.append(item['path'])
            for folder in affected_folders:
                remaining = get_folder_files_with_sha(token, owner, repo_name_only, folder)
                if not remaining:
                    create_github_file(token, owner, repo_name_only, f'{folder}/.gitkeep', '')
            pending[repo] = [i for i in items if i['path'] in errors]
            if not pending[repo]:
                del pending[repo]
            save_pending_deletes(pending)
            if errors:
                return jsonify({'success': False, 'error': f"Failed: {', '.join(errors)}", 'deleted': deleted})
            return jsonify({'success': True, 'deleted': deleted})
    return jsonify({'success': False, 'error': 'Repository not found'})

@app.route('/api/list-all-files')
def list_all_files():
    all_files = []
    repos = load_repos_from_file()
    for repo_config in repos:
        github_result = get_github_files(repo_config['token'], repo_config['owner'], repo_config['repo'])
        all_files.extend(github_result.get('files', []))
    return jsonify({'files': all_files})

@app.route('/api/load-file', methods=['POST'])
def load_file():
    data     = request.json
    filepath = data.get('filepath', '')
    repo     = data.get('repo', '')
    repos = load_repos_from_file()
    for repo_config in repos:
        repo_name = f"{repo_config['owner']}/{repo_config['repo']}"
        if repo_name == repo:
            return jsonify(load_github_file(repo_config['token'], repo_config['owner'], repo_config['repo'], filepath))
    return jsonify({'error': 'Repository not found'})

@app.route('/api/save-file', methods=['POST'])
def save_file():
    data     = request.json
    filepath = data.get('filepath', '')
    content  = data.get('content', '')
    repo     = data.get('repo', '')
    sha      = data.get('sha', '')
    commit   = data.get('commit', False)
    
    if commit:
        repos = load_repos_from_file()
        for repo_config in repos:
            repo_name = f"{repo_config['owner']}/{repo_config['repo']}"
            if repo_name == repo:
                result = save_github_file(
                    repo_config['token'], repo_config['owner'], repo_config['repo'], filepath, content, sha
                )
                if result['success']:
                    edits = load_edits_from_file()
                    file_key = f"{repo}:{filepath}"
                    if file_key in edits:
                        del edits[file_key]
                        save_edits_to_file(edits)
                return jsonify(result)
        return jsonify({'success': False, 'error': 'Repository not found'})
    else:
        edits = load_edits_from_file()
        file_key = f"{repo}:{filepath}"
        edits[file_key] = {'content': content, 'sha': sha, 'repo': repo, 'filepath': filepath}
        save_edits_to_file(edits)
        return jsonify({'success': True})

JENKINS_URL   = "http://192.168.121.40:32080"
JENKINS_USER  = "admin"
JENKINS_TOKEN = "119841289d2010c9d2b89611641fd17bef"
PIPELINE_MAPPINGS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'pipeline_mappings.json')

def load_pipeline_mappings():
    if os.path.exists(PIPELINE_MAPPINGS_FILE):
        with open(PIPELINE_MAPPINGS_FILE) as f:
            return json.load(f)
    return {}

def save_pipeline_mappings(mappings):
    with open(PIPELINE_MAPPINGS_FILE, 'w') as f:
        json.dump(mappings, f, indent=2)

def jenkins_request(path, method='GET', data=None):
    import urllib.request, urllib.error, base64
    creds = base64.b64encode(f'{JENKINS_USER}:{JENKINS_TOKEN}'.encode()).decode()
    headers = {'Authorization': f'Basic {creds}', 'Content-Type': 'application/x-www-form-urlencoded'}
    try:
        crumb_req = urllib.request.Request(
            f'{JENKINS_URL}/crumbIssuer/api/json',
            headers={'Authorization': f'Basic {creds}'}
        )
        with urllib.request.urlopen(crumb_req, timeout=5) as r:
            crumb_data = json.loads(r.read().decode())
            headers[crumb_data['crumbRequestField']] = crumb_data['crumb']
    except Exception:
        pass
    url = f'{JENKINS_URL}{path}'
    body = data.encode() if data else b''
    req  = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return True, r.read().decode()
    except urllib.error.HTTPError as e:
        return False, f'HTTP {e.code}: {e.reason}'
    except Exception as e:
        return False, str(e)

@app.route('/api/get-pipeline-for-repo', methods=['POST'])
def get_pipeline_for_repo():
    try:
        import urllib.request, base64, json as _json, urllib.parse
        data     = request.get_json(force=True)
        repo     = data.get('repo', '')
        mappings = load_pipeline_mappings()
        pipeline = mappings.get(repo)
        if pipeline:
            try:
                creds = base64.b64encode(f'{JENKINS_USER}:{JENKINS_TOKEN}'.encode()).decode()
                req = urllib.request.Request(
                    f'{JENKINS_URL}/job/{urllib.parse.quote(pipeline)}/api/json',
                    headers={'Authorization': f'Basic {creds}'}
                )
                with urllib.request.urlopen(req, timeout=5) as r:
                    pass
            except Exception:
                del mappings[repo]
                save_pipeline_mappings(mappings)
                pipeline = None
        return jsonify({'pipeline': pipeline, 'repo': repo})
    except Exception as e:
        return jsonify({'pipeline': None, 'repo': '', 'error': str(e)})

@app.route('/api/run-pipeline', methods=['POST'])
def run_pipeline():
    try:
        import urllib.request, urllib.error, urllib.parse, base64, json as _json
        data          = request.get_json(force=True)
        pipeline_name = data.get('pipeline', '').strip()
        if not pipeline_name:
            return jsonify({'success': False, 'error': 'No pipeline name provided'})
        creds   = base64.b64encode(f'{JENKINS_USER}:{JENKINS_TOKEN}'.encode()).decode()
        headers = {'Authorization': f'Basic {creds}', 'Content-Type': 'application/x-www-form-urlencoded'}
        try:
            crumb_req = urllib.request.Request(
                f'{JENKINS_URL}/crumbIssuer/api/json',
                headers={'Authorization': f'Basic {creds}'}
            )
            with urllib.request.urlopen(crumb_req, timeout=5) as r:
                crumb_data = _json.loads(r.read().decode())
                headers[crumb_data['crumbRequestField']] = crumb_data['crumb']
        except Exception:
            pass
        url = f'{JENKINS_URL}/job/{urllib.parse.quote(pipeline_name)}/build'
        req = urllib.request.Request(url, data=b'', headers=headers, method='POST')
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                return jsonify({'success': True})
        except urllib.error.HTTPError as e:
            return jsonify({'success': False, 'error': f'HTTP {e.code}: {e.reason}'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/trigger-lint', methods=['POST'])
def trigger_lint():
    try:
        import urllib.request, urllib.error, urllib.parse, base64, json as _json
        data = request.get_json(force=True)
        repo = data.get('repo', '').strip()
        if not repo:
            return jsonify({'success': False, 'error': 'No repo provided'})
        creds   = base64.b64encode(f'{JENKINS_USER}:{JENKINS_TOKEN}'.encode()).decode()
        headers = {'Authorization': f'Basic {creds}', 'Content-Type': 'application/x-www-form-urlencoded'}
        try:
            crumb_req = urllib.request.Request(
                f'{JENKINS_URL}/crumbIssuer/api/json',
                headers={'Authorization': f'Basic {creds}'}
            )
            with urllib.request.urlopen(crumb_req, timeout=5) as r:
                crumb_data = _json.loads(r.read().decode())
                headers[crumb_data['crumbRequestField']] = crumb_data['crumb']
        except Exception:
            pass
        token = ''
        repos = load_repos_from_file()
        for r in repos:
            if f"{r['owner']}/{r['repo']}" == repo:
                token = r['token']
                break
        params = urllib.parse.urlencode({'REPO': repo, 'TOKEN': token}).encode()
        url = f'{JENKINS_URL}/job/lint/buildWithParameters'
        req = urllib.request.Request(url, data=params, headers=headers, method='POST')
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                return jsonify({'success': True})
        except urllib.error.HTTPError as e:
            return jsonify({'success': False, 'error': f'HTTP {e.code}: {e.reason}'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})



@app.route('/api/pre-push-lint', methods=['POST'])
def pre_push_lint():
    import subprocess, tempfile, os
    data = request.get_json(force=True)
    content = data.get('content', '')
    filename = data.get('filename', 'file.py')
    if not filename.endswith('.py'):
        return jsonify({'passed': True, 'issues': []})
    try:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(content)
            tmp_path = f.name
        result = subprocess.run(
            ['python3', '-m', 'flake8', tmp_path,
             '--max-line-length=120', '--ignore=E501,W503'],
            capture_output=True, text=True
        )
        os.unlink(tmp_path)
        issues = [line.replace(tmp_path, filename)
                  for line in result.stdout.strip().split('\n') if line]
        return jsonify({'passed': len(issues) == 0, 'issues': issues})
    except Exception as e:
        return jsonify({'passed': True, 'issues': [], 'error': str(e)})

@app.route('/api/check-pipeline-result', methods=['POST'])
def check_pipeline_result():
    try:
        import urllib.request, base64, json as _json, urllib.parse
        data = request.get_json(force=True)
        pipeline_name = data.get('pipeline', '').strip()
        creds = base64.b64encode(f'{JENKINS_USER}:{JENKINS_TOKEN}'.encode()).decode()
        req = urllib.request.Request(
            f'{JENKINS_URL}/job/{urllib.parse.quote(pipeline_name)}/lastBuild/api/json',
            headers={'Authorization': f'Basic {creds}'}
        )
        with urllib.request.urlopen(req, timeout=5) as r:
            d = _json.loads(r.read().decode())
            return jsonify({'result': d.get('result'), 'building': d.get('building'), 'number': d.get('number')})
    except Exception as e:
        return jsonify({'result': None, 'error': str(e)})

@app.route('/api/check-lint-result', methods=['POST'])
def check_lint_result():
    try:
        import urllib.request, base64, json as _json
        creds = base64.b64encode(f'{JENKINS_USER}:{JENKINS_TOKEN}'.encode()).decode()
        req = urllib.request.Request(
            f'{JENKINS_URL}/job/lint/lastBuild/api/json',
            headers={'Authorization': f'Basic {creds}'}
        )
        with urllib.request.urlopen(req, timeout=5) as r:
            data = _json.loads(r.read().decode())
            return jsonify({
                'result': data.get('result'),
                'building': data.get('building'),
                'number': data.get('number')
            })
    except Exception as e:
        return jsonify({'result': None, 'error': str(e)})

@app.route('/api/list-jenkins-jobs')
def list_jenkins_jobs():
    try:
        import urllib.request, base64, json as _json
        creds = base64.b64encode(f'{JENKINS_USER}:{JENKINS_TOKEN}'.encode()).decode()
        req = urllib.request.Request(
            f'{JENKINS_URL}/api/json',
            headers={'Authorization': f'Basic {creds}'}
        )
        with urllib.request.urlopen(req, timeout=5) as r:
            data = _json.loads(r.read().decode())
        jobs = [j['name'] for j in data.get('jobs', [])]
        return jsonify({'jobs': jobs})
    except Exception as e:
        return jsonify({'jobs': [], 'error': str(e)})

@app.route('/api/link-pipeline', methods=['POST'])
def link_pipeline():
    try:
        import urllib.request, urllib.error, urllib.parse, base64, json as _json
        data          = request.get_json(force=True)
        repo          = data.get('repo', '')
        pipeline_name = data.get('pipeline_name', '').strip()
        create_new    = data.get('create_new', False)
        if not pipeline_name:
            return jsonify({'success': False, 'error': 'No pipeline name provided'})
        job_name = re.sub(r'[^a-zA-Z0-9_-]', '-', pipeline_name).strip('-')
        if create_new:
            empty_xml = (
                "<?xml version='1.1' encoding='UTF-8'?>\n"
                '<flow-definition plugin="workflow-job">\n'
                '  <description></description>\n'
                '  <keepDependencies>false</keepDependencies>\n'
                '  <definition class="org.jenkinsci.plugins.workflow.cps.CpsFlowDefinition" plugin="workflow-cps">\n'
                '    <script></script>\n'
                '    <sandbox>true</sandbox>\n'
                '  </definition>\n'
                '</flow-definition>'
            )
            creds = base64.b64encode(f'{JENKINS_USER}:{JENKINS_TOKEN}'.encode()).decode()
            headers = {'Authorization': f'Basic {creds}', 'Content-Type': 'application/xml'}
            try:
                crumb_req = urllib.request.Request(
                    f'{JENKINS_URL}/crumbIssuer/api/json',
                    headers={'Authorization': f'Basic {creds}'}
                )
                with urllib.request.urlopen(crumb_req, timeout=5) as r:
                    crumb_data = _json.loads(r.read().decode())
                    headers[crumb_data['crumbRequestField']] = crumb_data['crumb']
            except Exception:
                pass
            url = f'{JENKINS_URL}/createItem?name={urllib.parse.quote(job_name)}'
            req = urllib.request.Request(url, data=empty_xml.encode('utf-8'), headers=headers, method='POST')
            try:
                with urllib.request.urlopen(req, timeout=10) as r:
                    pass
            except urllib.error.HTTPError as e:
                if e.code != 400:
                    body = e.read().decode()[:200]
                    return jsonify({'success': False, 'error': f'Could not create Jenkins job: HTTP {e.code}: {body}'})
        mappings = load_pipeline_mappings()
        mappings[repo] = job_name
        save_pipeline_mappings(mappings)
        action = 'Created and linked' if create_new else 'Linked'
        return jsonify({'success': True, 'message': f'{action} pipeline "{job_name}" to {repo}. You can now edit the script in Jenkins.'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

if __name__ == '__main__':
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)
    
    print("="*60)
    print("SDOS Developer Workspace")
    print("="*60)
    print("Access: http://localhost:6001")
    print(f"Repos:  {REPOS_FILE}")
    print(f"Clones: {CLONES_DIR}")
    print("")
    print("Press Ctrl+C to stop")
    print("="*60)
    
    repos = load_repos_from_file()
    if repos:
        print(f"Loaded {len(repos)} saved repositories")
    
    try:
        app.run(host='0.0.0.0', port=6001, debug=False, threaded=True, use_reloader=False)
    except KeyboardInterrupt:
        print("\n" + "="*60)
        print("Developer Workspace stopped")
        print("="*60)
        sys.exit(0)
