from flask import Flask, render_template_string, jsonify, request, session
import signal
import sys
import logging
import os
import subprocess
import json
import base64
import secrets
import shutil
from collections import defaultdict
import re

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)

# Persistent storage files
REPOS_FILE   = os.path.expanduser('~/fyp-cluster/sdos-dashboard/github_repos.json')
EDITS_FILE   = os.path.expanduser('~/fyp-cluster/sdos-dashboard/github_edits.json')
DELETES_FILE = os.path.expanduser('~/fyp-cluster/sdos-dashboard/github_pending_deletes.json')
CLONES_DIR   = os.path.expanduser('~/fyp-cluster/sdos-dashboard/github-clones')

def load_pending_deletes():
    """Load staged (not yet committed) deletes: {repo: [{path, sha, type, folder_delete}]}"""
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
    """Delete a single file from GitHub"""
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
    """Get all files (with sha) inside a folder recursively"""
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
            background: #0f172a; 
            color: #e2e8f0; 
        }
        
        .header {
            background: linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%);
            padding: 20px 30px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            box-shadow: 0 8px 32px rgba(59, 130, 246, 0.3);
        }
        
        .header h1 { font-size: 32px; color: white; }
        .header-left { display: flex; align-items: center; gap: 20px; }
        
        .btn { 
            background: #3b82f6; color: white; border: none; 
            padding: 10px 20px; border-radius: 8px; cursor: pointer; 
            text-decoration: none; display: inline-block; transition: all 0.3s; 
        }
        .btn:hover { background: #2563eb; transform: translateY(-1px); }
        .btn-home { background: #64748b; }
        .btn-home:hover { background: #475569; }
        .btn-success { background: #22c55e; }
        .btn-success:hover { background: #16a34a; }
        .btn-danger { background: #ef4444; }
        .btn-danger:hover { background: #dc2626; }
        .btn-warning { background: #f59e0b; }
        .btn-warning:hover { background: #d97706; }
        .btn-small { padding: 6px 12px; font-size: 12px; }
        .btn-secondary { background: #475569; }
        .btn-secondary:hover { background: #334155; }
        
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
            background: #1e293b;
            border: 1px solid #334155;
            border-radius: 12px;
            padding: 30px;
            max-width: 520px;
            width: 90%;
            box-shadow: 0 20px 60px rgba(0,0,0,0.5);
        }
        
        .modal-header {
            font-size: 24px;
            color: #60a5fa;
            margin-bottom: 20px;
        }
        
        .form-group {
            margin-bottom: 20px;
        }
        
        .form-group label {
            display: block;
            color: #cbd5e1;
            margin-bottom: 8px;
            font-size: 14px;
        }
        
        .form-group input {
            width: 100%;
            padding: 12px;
            background: #0f172a;
            border: 1px solid #475569;
            border-radius: 8px;
            color: #e2e8f0;
            font-size: 14px;
        }
        
        .form-group input:focus {
            outline: none;
            border-color: #60a5fa;
        }
        
        .form-actions {
            display: flex;
            gap: 12px;
            margin-top: 25px;
        }

        /* Folder creation mode toggle */
        .folder-mode-tabs {
            display: flex;
            gap: 8px;
            margin-bottom: 20px;
        }
        .folder-mode-tab {
            flex: 1;
            padding: 10px;
            background: #0f172a;
            border: 2px solid #334155;
            border-radius: 8px;
            color: #94a3b8;
            cursor: pointer;
            font-size: 13px;
            text-align: center;
            transition: all 0.2s;
        }
        .folder-mode-tab.active {
            border-color: #60a5fa;
            color: #60a5fa;
            background: #1e3a5f;
        }
        .folder-with-file-section {
            display: none;
        }
        .folder-with-file-section.active {
            display: block;
        }
        
        /* ── Main layout: left panel | 8px drag handle | editor+terminal ── */
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
            grid-row: 1 / 3;       /* spans both rows */
            background: #1e293b;
            border: 1px solid #334155;
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

        /* Drag handle — spans both rows, sits between col 1 and col 3 */
        /* ── Horizontal resizer between editor and terminal ── */
        .row-resizer {
            flex: 0 0 10px;
            cursor: row-resize;
            display: flex;
            align-items: center;
            justify-content: center;
            background: transparent;
        }
        .row-resizer::after {
            content: '';
            display: block;
            width: 60px;
            height: 4px;
            background: #334155;
            border-radius: 2px;
            transition: background 0.2s;
        }
        .row-resizer:hover::after, .row-resizer.dragging::after { background: #3b82f6; }

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
            background: #334155;
            border-radius: 3px;
        }
        .panel-resizer:hover::after, .panel-resizer.dragging::after {
            background: #60a5fa;
        }

        /* Right column wrapper — flex column */
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
            background: #1e293b;
            border: 1px solid #334155;
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
            background: #1e293b;
            border: 1px solid #334155;
            border-radius: 12px;
            padding: 15px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.3);
            min-height: 80px;
            overflow: hidden;
        }
        
        /* All 3 resizable boxes in the left panel share this pattern */
        .info-section {
            background: #0f172a;
            border: 1px solid #334155;
            border-radius: 8px 8px 0 0;
            padding: 12px;
            font-size: 12px;
            overflow-y: auto;
            min-height: 50px;
        }
        
        .info-section strong {
            color: #60a5fa;
            display: block;
            margin-bottom: 8px;
        }
        
        .github-repos { margin-top: 8px; }
        
        .repo-item {
            background: #1e293b;
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
            color: #94a3b8;
            margin: 3px 0;
        }
        
        .file-tree {
            background: #0f172a;
            border: 1px solid #334155;
            border-radius: 8px 8px 0 0;
            padding: 15px;
            padding-right: 6px;
            min-height: 60px;
            overflow-y: auto;
            scrollbar-gutter: stable;
        }

        /* Shared drag handle for all 3 resizable left-panel boxes */
        .box-resizer {
            height: 8px;
            cursor: row-resize;
            background: #0a1120;
            border: 1px solid #334155;
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
            color: #60a5fa;
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

        /* Staged-for-creation files shown in yellow italic */
        .file-item.pending-create .file-label {
            color: #fbbf24;
            font-style: italic;
        }
        .subfolder-header.pending-create .subfolder-name {
            color: #fbbf24;
            font-style: italic;
        }

        /* Staged-for-deletion: folder headers get red strikethrough on their name */
        .subfolder-header.pending-delete .subfolder-name {
            text-decoration: line-through;
            color: #ef4444;
            opacity: 0.8;
        }
        /* Also dim the action buttons on pending-delete folders */
        .subfolder-header.pending-delete .repo-action-btn {
            display: none;
        }

        /* Staged-for-deletion files shown with strikethrough */
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

        /* Delete button on file/folder rows — always visible, right-aligned */
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
            color: #94a3b8;
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
            background: #1e293b;
            border-radius: 6px;
            margin-bottom: 5px;
            cursor: pointer;
            user-select: none;
            transition: all 0.2s;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .repo-folder-header:hover { background: #334155; }
        
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
            background: #0f172a;
            border-radius: 4px;
            margin-bottom: 3px;
            user-select: none;
            transition: all 0.2s;
            display: flex;
            align-items: center;
            gap: 4px;
        }
        
        .subfolder-header:hover { background: #1e293b; }

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
            background: #1e3a5f;
            color: #60a5fa;
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
            background: #2d5a8f;
            color: white;
            border-color: #60a5fa;
        }
        
        .repo-action-btn:hover { background: #3b82f6; }
        
        .repo-folder-files {
            display: block;
        }
        
        .repo-folder.collapsed .repo-folder-files { display: none; }
        
        .subfolder-files {
            display: block;
        }
        
        .subfolder.collapsed .subfolder-files { display: none; }
        
        /* File items with drag handles */
        .file-item {
            padding: 6px 8px;
            padding-left: 8px;
            cursor: pointer;
            border-radius: 6px;
            margin: 2px 0;
            font-size: 12px;
            color: #cbd5e1;
            transition: all 0.2s;
            display: flex;
            align-items: center;
            gap: 6px;
        }
        
        .file-item:hover { background: #1e293b; color: #60a5fa; }
        .file-item.active { background: #3b82f6; color: white; }
        
        .file-item.subfolder-file { padding-left: 20px; }

        /* Drag handle */
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
            color: #60a5fa;
            background: #1e3a5f;
        }
        .drag-handle:active { cursor: grabbing; }

        .file-label {
            flex: 1;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }

        /* Drag-and-drop visual feedback */
        .file-item.dragging {
            opacity: 0.4;
            background: #1e293b;
        }
        .file-item.drag-over-top {
            border-top: 2px solid #60a5fa;
        }
        .file-item.drag-over-bottom {
            border-bottom: 2px solid #60a5fa;
        }

        /* Subfolder drag handle */
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
            background: #0f172a;
            border: 2px solid #60a5fa;
            border-radius: 8px;
            padding: 12px 20px;
            font-size: 15px;
            color: #60a5fa;
            cursor: pointer;
            transition: all 0.3s;
            font-weight: 600;
        }
        
        .tool-button:hover {
            background: #1e293b;
            border-color: #3b82f6;
        }
        
        .tool-description {
            font-size: 12px;
            color: #94a3b8;
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
            background: #334155;
            border: 1px solid #475569;
            border-radius: 8px;
            padding: 10px 20px;
            font-size: 13px;
            color: #e2e8f0;
            cursor: pointer;
            transition: all 0.3s;
        }
        
        .nav-button:hover {
            background: #475569;
            border-color: #60a5fa;
        }
        

        
        .window-header {
            background: #0f172a;
            border: 1px solid #334155;
            padding: 12px 20px;
            font-size: 14px;
            font-weight: bold;
            margin-bottom: 15px;
            border-radius: 8px;
            color: #60a5fa;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .editor-actions { display: flex; gap: 10px; }
        
        .current-file {
            font-size: 13px;
            color: #94a3b8;
            font-weight: normal;
        }
        
        #monaco-editor {
            flex: 1;
            border: 1px solid #334155;
            border-radius: 8px;
            overflow: hidden;
        }
        

        
        .command-header {
            background: #0f172a;
            border: 1px solid #334155;
            padding: 10px 20px;
            font-size: 13px;
            font-weight: bold;
            margin-bottom: 10px;
            border-radius: 8px;
            color: #60a5fa;
        }
        
        .command-content {
            background: #000;
            color: #0f0;
            border: 1px solid #334155;
            padding: 15px;
            font-family: 'Courier New', monospace;
            font-size: 12px;
            max-height: 100px;
            border-radius: 8px;
            overflow-y: auto;
        }
    </style>
</head>
<body>
    <!-- GitHub repo modal -->
    <div class="modal" id="github-modal">
        <div class="modal-content">
            <div class="modal-header">Add GitHub Repository</div>
            <div class="form-group">
                <label>GitHub Personal Access Token</label>
                <input type="password" id="github-token" placeholder="ghp_xxxxxxxxxxxx">
                <p style="font-size: 11px; color: #94a3b8; margin-top: 5px;">
                    Create token at: <a href="https://github.com/settings/tokens" target="_blank" style="color: #60a5fa;">github.com/settings/tokens</a><br>
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

    <!-- New file modal -->
    <div class="modal" id="new-file-modal">
        <div class="modal-content">
            <div class="modal-header">Create New File</div>
            <div class="form-group">
                <label>File Path</label>
                <input type="text" id="new-file-path" placeholder="filename.py or folder/filename.py">
                <p style="font-size: 11px; color: #94a3b8; margin-top: 5px;">
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

    <!-- New folder modal — supports empty folder OR folder with a file -->
    <div class="modal" id="new-folder-modal">
        <div class="modal-content">
            <div class="modal-header">Create New Folder</div>

            <!-- Mode selector -->
            <div class="folder-mode-tabs">
                <div class="folder-mode-tab active" id="tab-empty" onclick="setFolderMode('empty')">
                    📁 Empty Folder
                </div>
                <div class="folder-mode-tab" id="tab-with-file" onclick="setFolderMode('with-file')">
                    📄 Folder + File
                </div>
            </div>

            <div class="form-group">
                <label>Repository</label>
                <div id="new-folder-repo-name" style="color: #22c55e; font-weight: bold; margin-bottom: 4px;"></div>
                <div style="font-size: 11px; color: #64748b;">
                    Creating inside: <span id="new-folder-parent-display" style="color: #94a3b8;">/ (root)</span>
                </div>
            </div>

            <div class="form-group">
                <label>New Folder Name</label>
                <input type="text" id="new-folder-name" placeholder="my-folder">
            </div>

            <!-- Only shown in "with-file" mode -->
            <div class="folder-with-file-section" id="folder-file-section">
                <div class="form-group">
                    <label>File Name inside new folder</label>
                    <input type="text" id="new-folder-filename" placeholder="main.py">
                    <p style="font-size: 11px; color: #94a3b8; margin-top: 5px;">
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
            <h1>Developer Workspace</h1>
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
                <p style="font-size: 11px; color: #94a3b8; margin-bottom: 8px;">Opens with full Git integration</p>
                <div id="vscode-files" style="margin-top: 10px; overflow-y: auto;">
                    <p style="color: #64748b; font-size: 11px;">Load a file first</p>
                </div>
            </div>
            <div class="box-resizer" data-target="vscode-box" title="Drag to resize"></div>
            
            <div class="file-tree" id="file-tree-box">
                <div class="file-tree-header">
                    <div class="file-tree-title">Microservice Files</div>
                    <button class="tree-header-btn tree-save-btn" onclick="saveAllEdits()" title="Save all unsaved edits locally">💾 Save All</button>
                    <button class="tree-header-btn tree-commit-btn" onclick="commitAllEdits()" title="Push all saved edits to GitHub">⬆ Commit All</button>
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
$ Drag handles on files for reordering
$ Empty folders supported
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
        let selectedFolderParentPath = '';  // '' = repo root, 'foldername' = inside that folder
        let folderCreateMode = 'empty'; // 'empty' or 'with-file'
        let pendingDeletes = {};       // { 'owner/repo': Set(['file/path']) }
        let pendingStagedFolders = {}; // { 'owner/repo': Set(['folderName']) } whole folders staged for delete
        let pendingCreates = [];   // [{ repo, path }] staged new files/folders not yet on GitHub
        let pendingCreateFolders = {}; // { repo: Set(folderPath) } folders staged but not on GitHub yet
        let lastSavedPath = '';    // tracks which file was last locally saved
        
        require.config({ paths: { vs: 'https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/0.44.0/min/vs' }});
        
        require(['vs/editor/editor.main'], function() {
            editor = monaco.editor.create(document.getElementById('monaco-editor'), {
                value: '# SDOS Developer Workspace\\n# \\n# Drag handles on file items\\n# Empty folders supported\\n',
                language: 'python',
                theme: 'vs-dark',
                automaticLayout: true,
                fontSize: 14,
                minimap: { enabled: true },
                scrollBeyondLastLine: false,
                wordWrap: 'on'
            });
            
            addTerminalLine('Monaco Editor initialized');
            loadGithubRepos();
            loadPendingDeletes().then(() => loadFileList());
        });

        // ─── Folder mode toggle ───────────────────────────────────────────
        function setFolderMode(mode) {
            folderCreateMode = mode;
            document.getElementById('tab-empty').classList.toggle('active', mode === 'empty');
            document.getElementById('tab-with-file').classList.toggle('active', mode === 'with-file');
            document.getElementById('folder-file-section').classList.toggle('active', mode === 'with-file');
        }
        
        // ─── Modal helpers ────────────────────────────────────────────────
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
        // parentPath: the subfolder the user clicked from, or '' for repo root
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
        
        // ─── Create new file ──────────────────────────────────────────────
        async function createNewFile() {
            const filePath = document.getElementById('new-file-path').value.trim();
            if (!filePath) { addTerminalLine('✗ Please enter a file path'); return; }
            if (!selectedRepoForNewFile) { addTerminalLine('✗ No repository selected'); return; }

            // Stage locally — do NOT push to GitHub yet
            pendingCreates.push({ repo: selectedRepoForNewFile, path: filePath });
            closeNewFileModal();
            await loadFileList();
            addTerminalLine(`✓ Staged new file ${filePath} — hit Save All then Commit All to push`);

            // Open in editor as empty new file (no GitHub load needed)
            const fileName = filePath.split('/').pop();
            editor.setValue('');
            currentFile = fileName;
            currentFilePath = filePath;
            currentSource = 'github';
            currentRepo = selectedRepoForNewFile;
            currentSha = '';  // no SHA yet — file doesn't exist on GitHub
            document.getElementById('current-file').textContent = filePath + ' [' + selectedRepoForNewFile + '] (new - not yet committed)';
            document.getElementById('commit-btn').style.display = 'inline-block';
            const ext = fileName.split('.').pop();
            const langMap = { 'py': 'python', 'js': 'javascript', 'html': 'html', 'css': 'css',
                'json': 'json', 'yaml': 'yaml', 'yml': 'yaml', 'sh': 'shell', 'md': 'markdown' };
            monaco.editor.setModelLanguage(editor.getModel(), langMap[ext] || 'plaintext');
            editor.focus();
        }
        
        // ─── Create new folder ────────────────────────────────────────────
        async function createNewFolder() {
            const folderName = document.getElementById('new-folder-name').value.trim();
            if (!folderName) { addTerminalLine('✗ Please enter a folder name'); return; }
            if (!selectedRepoForNewFolder) { addTerminalLine('✗ No repository selected'); return; }

            const folderPath = selectedFolderParentPath
                ? selectedFolderParentPath + '/' + folderName
                : folderName;

            let targetPath;
            if (folderCreateMode === 'with-file') {
                const fileName = document.getElementById('new-folder-filename').value.trim();
                if (!fileName) { addTerminalLine('✗ Please enter a file name'); return; }
                targetPath = folderPath + '/' + fileName;
            } else {
                targetPath = folderPath + '/.gitkeep';
            }

            // Stage locally — do NOT push to GitHub yet
            pendingCreates.push({ repo: selectedRepoForNewFolder, path: targetPath, folderPath });
            closeNewFolderModal();

            // Show the folder in the UI immediately by injecting a fake dir entry
            // into the next loadFileList call via a local overlay
            pendingCreateFolders[selectedRepoForNewFolder] = pendingCreateFolders[selectedRepoForNewFolder] || new Set();
            pendingCreateFolders[selectedRepoForNewFolder].add(folderPath);

            await loadFileList();
            if (folderCreateMode === 'with-file') {
                addTerminalLine(`✓ Staged new folder ${folderPath} — hit Save All then Commit All to push`);
            } else {
                addTerminalLine(`✓ Staged empty folder ${folderPath} — hit Save All then Commit All to push`);
            }
        }
        
        // ─── Load GitHub repos ────────────────────────────────────────────
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
            if (!token || !owner || !repo) { addTerminalLine('✗ Please fill in all fields'); return; }
            
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
                addTerminalLine(`✓ Added repository: ${owner}/${repo}`);
            } else {
                addTerminalLine(`✗ Failed: ${data.error}`);
            }
        }
        
        // ─── Folder toggle ────────────────────────────────────────────────
        function toggleFolder(repoName) {
            const folder = document.getElementById('folder-' + repoName.replace(/\//g, '-'));
            if (folder) folder.classList.toggle('collapsed');
        }
        function toggleSubfolder(folderId) {
            const folder = document.getElementById(folderId);
            if (folder) folder.classList.toggle('collapsed');
        }
        
        // ─── Drag-and-drop helpers ────────────────────────────────────────
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

        // Make a drag handle span — clicking the handle doesn't open the file
        function makeDragHandle() {
            const h = document.createElement('span');
            h.className = 'drag-handle';
            h.textContent = '⠿';
            h.title = 'Drag to reorder';
            h.addEventListener('mousedown', e => e.stopPropagation());
            return h;
        }
        
        // ─── Build folder tree ────────────────────────────────────────────
        function buildFolderTree(files, repoName) {
            const tree = {};       // { folderName: [file, ...] }
            const rootFiles = [];  // files at repo root

            files.forEach(file => {
                if (file.type === 'dir') {
                    // Ensure every dir entry creates a tree key so empty folders show
                    const folderName = file.path.split('/')[0];
                    if (!tree[folderName]) tree[folderName] = [];
                } else if (file.type === 'file') {
                    // Filter hidden placeholder files from view but keep folder alive
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
        
        // ─── Load file list ───────────────────────────────────────────────
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
                    // Inject pending-created folders as fake 'dir' entries so they show in UI
                    for (const [repo, folders] of Object.entries(pendingCreateFolders)) {
                        if (!grouped[repo]) grouped[repo] = [];
                        for (const fp of folders) {
                            grouped[repo].push({ name: fp.split('/').pop(), path: fp, repo, type: 'dir', pending: true });
                        }
                    }
                    // Inject pending-created files as fake entries
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
                        
                        // Subfolders
                        Object.keys(tree).sort().forEach(folderName => {
                            const folderId = 'subfolder-' + repoName.replace(/\//g, '-') + '-' + folderName.replace(/\//g, '-');
                            
                            const subfolderDiv = document.createElement('div');
                            subfolderDiv.className = 'subfolder';
                            subfolderDiv.id = folderId;
                            
                            const subfolderHeader = document.createElement('div');
                            const folderIsPendingCreate = pendingCreateFolders[repoName] && pendingCreateFolders[repoName].has(folderName);
                            const folderIsPendingDel = isFolderPendingDelete(repoName, folderName);
                            subfolderHeader.className = 'subfolder-header' + (folderIsPendingCreate ? ' pending-create' : '') + (folderIsPendingDel ? ' pending-delete' : '');

                            // Drag handle for subfolder
                            const sfHandle = document.createElement('span');
                            sfHandle.className = 'subfolder-drag';
                            sfHandle.textContent = '⠿';
                            sfHandle.title = 'Drag to reorder';
                            subfolderHeader.appendChild(sfHandle);

                            // Explicit collapse arrow
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

                            // + Folder button inside subfolder (creates nested folder)
                            const sfFolderBtn = document.createElement('button');
                            sfFolderBtn.className = 'repo-action-btn';
                            sfFolderBtn.textContent = '+ Folder';
                            sfFolderBtn.title = `Create folder inside ${folderName}`;
                            sfFolderBtn.onclick = e => {
                                e.stopPropagation();
                                showNewFolderModal(repoName, folderName);
                            };
                            subfolderHeader.appendChild(sfFolderBtn);

                            // + File button inside subfolder
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

                            // Delete/undo folder button
                            const sfDelBtn = document.createElement('button');
                            sfDelBtn.className = 'delete-btn';
                            if (folderIsPendingDel) {
                                sfDelBtn.textContent = '↩';
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
                                    label.title = 'Staged for deletion — Commit All to apply';
                                }

                                const delBtn = document.createElement('button');
                                delBtn.className = 'delete-btn';
                                delBtn.textContent = isPendingDel ? '↩' : '✕';
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
                        
                        // Root files
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
                                label.title = 'Staged for deletion — Commit All to apply';
                            }

                            const delBtn = document.createElement('button');
                            delBtn.className = 'delete-btn';
                            delBtn.textContent = isPendingDel ? '↩' : '✕';
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
                    fileList.innerHTML = '<div style="color: #94a3b8;">No files found</div>';
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
            if (!currentFile) { addTerminalLine('✗ Load a file first'); return; }
            try {
                const response = await fetch('/api/open-in-vscode-git', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ filename: currentFile, filepath: currentFilePath, repo: currentRepo })
                });
                const data = await response.json();
                if (data.success) {
                    addTerminalLine(`✓ Opened in VS Code: ${data.repo_path}`);
                    addTerminalLine('You can now commit/push from VS Code');
                } else {
                    addTerminalLine(`✗ Error: ${data.error}`);
                }
            } catch (error) {
                addTerminalLine(`✗ Error: ${error.message}`);
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
                    addTerminalLine(`✓ Saved ${currentFile} locally`);
                } else {
                    addTerminalLine(`✗ Error: ${data.error}`);
                }
            } catch (error) {
                addTerminalLine(`✗ Error: ${error.message}`);
            }
        }
        
        async function commitToGithub() {
            if (!currentFilePath) { addTerminalLine('Not a GitHub file'); return; }
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
                    addTerminalLine(`✓ Pushed to ${currentRepo}`);
                    showPipelineModal(currentRepo);
                } else {
                    addTerminalLine(`✗ Error: ${data.error}`);
                }
            } catch (error) {
                addTerminalLine(`✗ Error: ${error.message}`);
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
                    addTerminalLine(`✓ Reloaded from GitHub (cleared local save)`);
                    editor.focus();
                } else {
                    addTerminalLine(`Error: ${data.error}`);
                }
            } catch (error) {
                addTerminalLine(`Error: ${error.message}`);
            }
        }
        
        // ─── Pending deletes tracking ─────────────────────────────────────
        // Keyed by repo -> set of paths staged for deletion
        async function loadPendingDeletes() {
            try {
                const r = await fetch('/api/pending-deletes');
                const data = await r.json();
                pendingDeletes = {};
                pendingStagedFolders = {};
                for (const [repo, items] of Object.entries(data)) {
                    pendingDeletes[repo] = new Set(items.map(i => i.path));
                    // A folder is staged if ALL items with folder_delete:true share a common folder prefix
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

        // ─── Undo a staged file delete ────────────────────────────────────
        async function unstageDelete(filepath, repo) {
            try {
                const r = await fetch('/api/unstage-delete', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ filepath, repo })
                });
                const d = await r.json();
                if (d.success) {
                    addTerminalLine(`↩ Unstaged delete for ${filepath.split('/').pop()}`);
                    await loadPendingDeletes();
                    await loadFileList();
                } else {
                    addTerminalLine(`✗ Undo failed: ${d.error}`);
                }
            } catch(e) { addTerminalLine(`✗ Error: ${e.message}`); }
        }

        // ─── Undo a staged folder delete ──────────────────────────────────
        async function unstageFolderDelete(folderName, repo) {
            try {
                const r = await fetch('/api/unstage-folder-delete', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ folder: folderName, repo })
                });
                const d = await r.json();
                if (d.success) {
                    addTerminalLine(`↩ Unstaged deletion of folder ${folderName} (${d.restored} file(s) restored)`);
                    await loadPendingDeletes();
                    await loadFileList();
                } else {
                    addTerminalLine(`✗ Undo failed: ${d.error}`);
                }
            } catch(e) { addTerminalLine(`✗ Error: ${e.message}`); }
        }

        // ─── Delete file (staged locally, not pushed yet) ─────────────────
        async function confirmDeleteFile(filepath, sha, repo) {
            const name = filepath.split('/').pop();
            if (!confirm(`Mark "${name}" for deletion?\n\nNothing changes on GitHub yet.\nHit Save All → then Commit All to apply.`)) return;
            try {
                const response = await fetch('/api/delete-file', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ filepath, sha, repo })
                });
                const data = await response.json();
                if (data.success) {
                    addTerminalLine(`✓ Staged delete: ${filepath} — hit Commit All to push to GitHub`);
                    if (currentFilePath === filepath) {
                        currentFile = ''; currentFilePath = ''; currentRepo = ''; currentSha = '';
                        editor.setValue('');
                        document.getElementById('current-file').textContent = 'No file selected';
                        document.getElementById('commit-btn').style.display = 'none';
                    }
                    await loadPendingDeletes();
                    await loadFileList();
                } else {
                    addTerminalLine(`✗ Stage delete failed: ${data.error}`);
                }
            } catch (e) { addTerminalLine(`✗ Error: ${e.message}`); }
        }

        // ─── Delete folder (staged locally, not pushed yet) ───────────────
        async function confirmDeleteFolder(folderName, repo) {
            if (!confirm(`Mark folder "${folderName}" and ALL its files for deletion?\n\nNothing changes on GitHub yet.\nHit Save All → then Commit All to apply.`)) return;
            addTerminalLine(`Staging folder ${folderName} for deletion...`);
            try {
                const response = await fetch('/api/delete-folder', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ folder: folderName, repo })
                });
                const data = await response.json();
                if (data.success) {
                    addTerminalLine(`✓ Staged ${data.staged} files for deletion — hit Commit All to push to GitHub`);
                    if (currentFilePath.startsWith(folderName + '/')) {
                        currentFile = ''; currentFilePath = ''; currentRepo = ''; currentSha = '';
                        editor.setValue('');
                        document.getElementById('current-file').textContent = 'No file selected';
                        document.getElementById('commit-btn').style.display = 'none';
                    }
                    await loadPendingDeletes();
                    await loadFileList();
                } else {
                    addTerminalLine(`✗ Stage delete failed: ${data.error}`);
                }
            } catch (e) { addTerminalLine(`✗ Error: ${e.message}`); }
        }

        // ─── Save All (saves current editor content locally) ─────────────
        async function saveAllEdits() {
            let savedAnything = false;

            // Save current open file locally if there is one
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
                        addTerminalLine(`✓ Saved ${currentFile} locally`);
                        savedAnything = true;
                    } else {
                        addTerminalLine(`✗ Save failed: ${data.error}`);
                    }
                } catch (e) { addTerminalLine(`✗ Error: ${e.message}`); }
            }

            // Push any pending-created files/folders to GitHub now
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
                            addTerminalLine(`✓ Created ${pc.path} on GitHub`);
                            // If it had a folderPath, clear from pendingCreateFolders
                            if (pc.folderPath && pendingCreateFolders[pc.repo]) {
                                pendingCreateFolders[pc.repo].delete(pc.folderPath);
                            }
                            savedAnything = true;
                        } else {
                            addTerminalLine(`✗ Failed to create ${pc.path}: ${d.error}`);
                            pendingCreates.push(pc); // put back if failed
                        }
                    } catch(e) { addTerminalLine(`✗ Error creating ${pc.path}: ${e.message}`); pendingCreates.push(pc); }
                }
                await loadFileList();
            }

            // Report any pending deletes that are staged and ready to commit
            const pending = await (await fetch('/api/pending-deletes')).json();
            let stagedCount = 0;
            for (const items of Object.values(pending)) stagedCount += items.length;
            if (stagedCount > 0) {
                addTerminalLine(`✓ ${stagedCount} deletion(s) staged — hit Commit All to push to GitHub`);
                savedAnything = true;
            }

            if (!savedAnything) { addTerminalLine('Nothing to save'); }
        }

        // ─── Commit All: push file edits AND flush staged deletes ─────────
        async function commitAllEdits() {
            let didSomething = false;
            let fileContentWasPushed = false;

            // 1. Push current file edit — only if user hit Save first
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
                        lastSavedPath = '';  // clear after commit
                        addTerminalLine(`✓ Committed & pushed ${currentFile} to GitHub`);
                        didSomething = true;
                        fileContentWasPushed = true;
                    } else {
                        addTerminalLine(`✗ Commit failed: ${data.error}`);
                    }
                } catch (e) { addTerminalLine(`✗ Error: ${e.message}`); }
            } else if (currentFilePath && lastSavedPath !== currentFilePath) {
                addTerminalLine(`⚠ ${currentFile} has unsaved changes — hit Save All first`);
            }

            // 2. Flush all staged deletes for all repos
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
                        addTerminalLine(`✓ Committed ${d.deleted} deletion(s) to ${repo}`);
                        didSomething = true;
                    } else {
                        addTerminalLine(`✗ Delete commit failed: ${d.error}`);
                    }
                } catch(e) { addTerminalLine(`✗ Error: ${e.message}`); }
            }

            if (!didSomething) { addTerminalLine('Nothing to commit'); }
            await loadPendingDeletes();
            await loadFileList();
            // Only show pipeline modal if actual file content was edited and pushed
            if (fileContentWasPushed) { showPipelineModal(currentRepo); }
        }

        // ─── Panel resizer — drag left edge of editor left/right ────────────
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

        // ─── Row resizer — drag between editor and terminal ─────────────
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
                    const delta  = startY - e.clientY;  // drag up = bigger terminal
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

        // ─── Box resizers — one handler for all 3 left-panel resizable boxes ──
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
                    // Cap: can't be smaller than 50px, can't be larger than
                    // the left panel height minus 150px (keeps other boxes visible)
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
        
        // ─── Jenkins Pipeline Modal logic ───────────────────────────────
        let _pipelineRepo = null;

        async function showPipelineModal(repo) {
            _pipelineRepo = repo;
            const status = document.getElementById('pipeline-modal-status');
            status.textContent = '';
            document.getElementById('pipeline-name-input').value = '';
            document.getElementById('pipeline-existing-select').value = '';

            // Check if already linked
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
                // Already linked — just show it, no action needed
                msg.textContent = `Repo "${repo}" is already linked to a Jenkins pipeline:`;
                document.getElementById('pipeline-linked-name').textContent = '✓ ' + data.pipeline;
                linkedSection.style.display   = 'block';
                unlinkedSection.style.display = 'none';
                linkBtn.textContent = 'Update Link';
                linkBtn.style.background = '#22c55e';
                // Also show unlinked section so user can re-link if they want
                unlinkedSection.style.display = 'block';
                // Pre-load existing Jenkins jobs into dropdown
                loadJenkinsJobs();
            } else {
                msg.textContent = `Repo "${repo}" is not linked to a Jenkins pipeline yet. Pick an existing job or create a new empty one:`;
                linkedSection.style.display   = 'none';
                unlinkedSection.style.display = 'block';
                linkBtn.textContent = 'Link Pipeline';
                linkBtn.style.background = '#3b82f6';
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
                select.innerHTML = '<option value="">— select existing job —</option>';
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
                    status.textContent = '✗ Server error: ' + text.substring(0, 120);
                    document.getElementById('pipeline-modal-link').disabled = false;
                    return;
                }
                if (data.success) {
                    status.style.color = '#22c55e';
                    status.textContent = data.message;
                    addTerminalLine('✓ ' + data.message);
                    setTimeout(closePipelineModal, 2000);
                } else {
                    status.style.color = '#ef4444';
                    status.textContent = '✗ ' + data.error;
                }
            } catch(e) {
                status.style.color = '#ef4444';
                status.textContent = '✗ ' + e.message;
            }

            document.getElementById('pipeline-modal-link').disabled = false;
        }

        function addTerminalLine(text) {
            const terminal = document.getElementById('terminal');
            terminal.innerHTML += '$ ' + text + '<br>';
            terminal.scrollTop = terminal.scrollHeight;
        }
    </script>

        <!-- ── Jenkins Pipeline Modal ───────────────────────────────── -->
        <div id="pipeline-modal" style="display:none;position:fixed;inset:0;background:rgba(0,0,0,0.7);z-index:9999;align-items:center;justify-content:center;">
            <div style="background:#1e293b;border:1px solid #3b82f6;border-radius:12px;padding:30px;width:460px;box-shadow:0 20px 60px rgba(0,0,0,0.5);">
                <h3 style="color:#60a5fa;margin-bottom:6px;font-size:18px;">Link Jenkins Pipeline</h3>
                <p id="pipeline-modal-msg" style="color:#94a3b8;font-size:13px;margin-bottom:20px;line-height:1.5;"></p>

                <!-- Already linked: just show the name, no action needed -->
                <div id="pipeline-linked-section" style="display:none;margin-bottom:18px;">
                    <div style="background:#0f172a;border:1px solid #22c55e;border-radius:6px;padding:10px 14px;color:#22c55e;font-size:13px;font-weight:600;" id="pipeline-linked-name"></div>
                </div>

                <!-- Not linked: choose existing or create new -->
                <div id="pipeline-unlinked-section" style="display:none;margin-bottom:18px;">
                    <!-- Fetch existing Jenkins jobs -->
                    <label style="color:#cbd5e1;font-size:13px;display:block;margin-bottom:6px;">Pick an existing Jenkins pipeline:</label>
                    <select id="pipeline-existing-select"
                        style="width:100%;background:#0f172a;border:1px solid #334155;border-radius:6px;
                               padding:8px 12px;color:#e2e8f0;font-size:14px;margin-bottom:14px;"
                        onchange="onExistingSelect()">
                        <option value="">— select existing job —</option>
                    </select>

                    <div style="text-align:center;color:#475569;font-size:12px;margin-bottom:12px;">— or create a new one —</div>

                    <label style="color:#cbd5e1;font-size:13px;display:block;margin-bottom:6px;">New pipeline name:</label>
                    <input id="pipeline-name-input" type="text" placeholder="e.g. my-pipeline"
                        style="width:100%;background:#0f172a;border:1px solid #334155;border-radius:6px;
                               padding:8px 12px;color:#e2e8f0;font-size:14px;outline:none;"
                        oninput="onNameInput()" />
                </div>

                <div style="display:flex;gap:10px;justify-content:flex-end;">
                    <button style="background:#334155;color:#94a3b8;border:none;padding:9px 18px;border-radius:6px;cursor:pointer;font-size:13px;"
                        onclick="closePipelineModal()">Skip
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
    filename = data.get('filename', '')
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
    """Stage a file deletion locally. Does NOT touch GitHub until commit."""
    data = request.json
    filepath = data.get('filepath', '')
    sha      = data.get('sha', '')
    repo     = data.get('repo', '')
    if not filepath or not sha or not repo:
        return jsonify({'success': False, 'error': 'Missing fields'})

    # Clear any unsaved local edit for this file
    edits = load_edits_from_file()
    file_key = f"{repo}:{filepath}"
    if file_key in edits:
        del edits[file_key]
        save_edits_to_file(edits)

    # Stage the delete - do NOT call GitHub yet
    pending = load_pending_deletes()
    if repo not in pending:
        pending[repo] = []
    # Avoid duplicates
    pending[repo] = [d for d in pending[repo] if d['path'] != filepath]
    pending[repo].append({'path': filepath, 'sha': sha, 'folder_delete': False})
    save_pending_deletes(pending)

    return jsonify({'success': True, 'staged': True})

@app.route('/api/delete-folder', methods=['POST'])
def api_delete_folder():
    """Stage deletion of all files in a folder. Does NOT touch GitHub until commit."""
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
            # Get all files currently in the folder from GitHub
            files = get_folder_files_with_sha(token, owner, repo_name_only, folder)
            if not files:
                return jsonify({'success': False, 'error': 'Folder not found or already empty'})

            # Stage all as pending deletes
            pending = load_pending_deletes()
            if repo not in pending:
                pending[repo] = []
            for f in files:
                # Clear any local edit
                edits = load_edits_from_file()
                file_key = f"{repo}:{f['path']}"
                if file_key in edits:
                    del edits[file_key]
                    save_edits_to_file(edits)
                # Stage
                pending[repo] = [d for d in pending[repo] if d['path'] != f['path']]
                pending[repo].append({'path': f['path'], 'sha': f['sha'], 'folder_delete': True})
            save_pending_deletes(pending)

            return jsonify({'success': True, 'staged': len(files), 'deleted': len(files)})
    return jsonify({'success': False, 'error': 'Repository not found'})

@app.route('/api/pending-deletes', methods=['GET'])
def api_get_pending_deletes():
    """Return current staged deletions so the UI can show them."""
    return jsonify(load_pending_deletes())

@app.route('/api/unstage-delete', methods=['POST'])
def api_unstage_delete():
    """Remove a single file from the pending-deletes list (undo staged delete)."""
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
    """Remove all files under a folder from pending-deletes (undo folder staged delete)."""
    data   = request.json
    folder = data.get('folder', '')
    repo   = data.get('repo', '')
    if not folder or not repo:
        return jsonify({'success': False, 'error': 'Missing fields'})
    pending = load_pending_deletes()
    if repo in pending:
        before = len(pending[repo])
        # Remove all items that belong to this folder (path starts with folder/)
        pending[repo] = [d for d in pending[repo] if not d['path'].startswith(folder + '/') and d['path'] != folder]
        restored = before - len(pending[repo])
        if not pending[repo]:
            del pending[repo]
        save_pending_deletes(pending)
        return jsonify({'success': True, 'restored': restored})
    return jsonify({'success': True, 'restored': 0})

@app.route('/api/commit-deletes', methods=['POST'])
def api_commit_deletes():
    """Actually delete staged files from GitHub."""
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
            # Track which folders had files deleted so we can keep them alive
            affected_folders = set()
            for item in items:
                result = delete_github_file(token, owner, repo_name_only, item['path'], item['sha'])
                if result['success']:
                    deleted += 1
                    # Track parent folder
                    parts = item['path'].split('/')
                    if len(parts) > 1 and not item.get('folder_delete'):
                        affected_folders.add(parts[0])
                else:
                    errors.append(item['path'])

            # For file-only deletes: if the folder is now empty on GitHub,
            # re-add .gitkeep so the folder survives
            for folder in affected_folders:
                remaining = get_folder_files_with_sha(token, owner, repo_name_only, folder)
                if not remaining:
                    create_github_file(token, owner, repo_name_only, f'{folder}/.gitkeep', '')

            # Clear committed items from pending (keep any that failed)
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

JENKINS_URL = "http://192.168.121.40:32080"
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
    """Make a request to Jenkins API with crumb authentication"""
    import urllib.request, urllib.error, base64
    JENKINS_USER  = 'admin'
    JENKINS_TOKEN = '119841289d2010c9d2b89611641fd17bef'

    creds = base64.b64encode(f'{JENKINS_USER}:{JENKINS_TOKEN}'.encode()).decode()
    headers = {'Authorization': f'Basic {creds}', 'Content-Type': 'application/x-www-form-urlencoded'}

    # Get Jenkins crumb for CSRF
    try:
        crumb_req = urllib.request.Request(
            f'{JENKINS_URL}/crumbIssuer/api/json',
            headers={'Authorization': f'Basic {creds}'}
        )
        with urllib.request.urlopen(crumb_req, timeout=5) as r:
            crumb_data = json.loads(r.read().decode())
            headers[crumb_data['crumbRequestField']] = crumb_data['crumb']
    except Exception:
        pass  # Some Jenkins configs don't need crumb

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

def create_jenkins_job(job_name, repo=''):
    import urllib.request, urllib.error, urllib.parse, base64, json as _json
    import xml.sax.saxutils as saxutils

    JENKINS_USER  = 'admin'
    JENKINS_TOKEN = '119b0a43cfb46d628a7d35d0981b73fb38'
    github_url    = f'https://github.com/{repo}.git' if repo else ''

    groovy_lines = [
        "pipeline {",
        "    agent any",
        "    stages {",
        "        stage('Build') {",
        "            steps {",
        "                echo 'Cloning " + repo + "...'",
        "                sh 'rm -rf repo && git clone " + github_url + " repo'",
        "                sh 'ls -la repo/'",
        "            }",
        "        }",
        "        stage('Test') {",
        "            steps {",
        "                sh 'cd repo && find . -name \'*.py\' -exec python3 -m py_compile {} + && echo \'Syntax OK\' || echo \'Syntax errors found\''",
        "            }",
        "        }",
        "        stage('Staging') {",
        "            steps {",
        "                sh 'cd repo && find . -name \'*.py\' | head -20'",
        "            }",
        "        }",
        "        stage('Load') {",
        "            steps {",
        "                sh 'cd repo && find . -name *.py | wc -l'",
        "            }",
        "        }",
        "        stage('Production') {",
        "            steps {",
        "                sh 'cd repo && git log -1 --oneline && echo \'Deployment complete\''",
        "            }",
        "        }",
        "    }",
        "    post {",
        "        always { sh 'rm -rf repo || true' }",
        "        success { echo 'Pipeline passed' }",
        "        failure { echo 'Pipeline failed' }",
        "    }",
        "}",
    ]
    groovy = "\n".join(groovy_lines)
    escaped_script = saxutils.escape(groovy)

    job_xml = (
        "<?xml version='1.1' encoding='UTF-8'?>\n"
        '<flow-definition plugin="workflow-job">\n'
        '  <description>Pipeline for ' + job_name + ' (' + repo + ')</description>\n'
        '  <keepDependencies>false</keepDependencies>\n'
        '  <definition class="org.jenkinsci.plugins.workflow.cps.CpsFlowDefinition" plugin="workflow-cps">\n'
        '    <script>' + escaped_script + '</script>\n'
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
    req = urllib.request.Request(url, data=job_xml.encode('utf-8'), headers=headers, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return True, 'Created'
    except urllib.error.HTTPError as e:
        if e.code == 400:
            return False, 'Job already exists'
        body = e.read().decode()[:300]
        return False, f'HTTP {e.code}: {body}'
    except Exception as e:
        return False, str(e)


@app.route('/api/get-pipeline-for-repo', methods=['POST'])
def get_pipeline_for_repo():
    try:
        import urllib.request, base64, json as _json
        data     = request.get_json(force=True)
        repo     = data.get('repo', '')
        mappings = load_pipeline_mappings()
        pipeline = mappings.get(repo)

        # If we have a saved mapping, verify the job still exists in Jenkins
        if pipeline:
            try:
                JENKINS_USER  = 'admin'
                JENKINS_TOKEN = '119b0a43cfb46d628a7d35d0981b73fb38'
                creds = base64.b64encode(f'{JENKINS_USER}:{JENKINS_TOKEN}'.encode()).decode()
                req = urllib.request.Request(
                    f'{JENKINS_URL}/job/{urllib.parse.quote(pipeline)}/api/json',
                    headers={'Authorization': f'Basic {creds}'}
                )
                with urllib.request.urlopen(req, timeout=5) as r:
                    pass  # job exists
            except Exception:
                # Job no longer exists in Jenkins — clear the stale mapping
                del mappings[repo]
                save_pipeline_mappings(mappings)
                pipeline = None

        return jsonify({'pipeline': pipeline, 'repo': repo})
    except Exception as e:
        return jsonify({'pipeline': None, 'repo': '', 'error': str(e)})

@app.route('/api/list-jenkins-jobs')
def list_jenkins_jobs():
    """Return all existing Jenkins job names"""
    try:
        import urllib.request, base64, json as _json
        JENKINS_USER  = 'admin'
        JENKINS_TOKEN = '119b0a43cfb46d628a7d35d0981b73fb38'
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
    """Link a repo to a pipeline. If create_new=True, create an empty job in Jenkins first."""
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
            # Create an EMPTY pipeline in Jenkins (user will fill in the script)
            JENKINS_USER  = 'admin'
            JENKINS_TOKEN = '119b0a43cfb46d628a7d35d0981b73fb38'
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
                    pass  # 200 = created
            except urllib.error.HTTPError as e:
                if e.code != 400:  # 400 = already exists, that's fine
                    body = e.read().decode()[:200]
                    return jsonify({'success': False, 'error': f'Could not create Jenkins job: HTTP {e.code}: {body}'})

        # Save the mapping
        mappings = load_pipeline_mappings()
        mappings[repo] = job_name
        save_pipeline_mappings(mappings)

        action = 'Created and linked' if create_new else 'Linked'
        return jsonify({'success': True, 'message': f'{action} pipeline "{job_name}" to {repo}. You can now edit the script in Jenkins.'})

    except Exception as e:
        import traceback; traceback.print_exc()
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
    print("Features:")
    print("  - Empty folders (uses hidden .gitkeep)")
    print("  - Folder + file creation in one step")
    print("  - Drag handles on all file items")
    print("  - Collapsible folder structure")
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
