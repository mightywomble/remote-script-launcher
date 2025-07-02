# app.py
# Main Flask application file

from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy
import paramiko
import os
import shlex
import json
import requests

# --- App Initialization ---
app = Flask(__name__)

# --- Configuration ---
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'app.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'a_very_secret_key_change_me'
CONFIG_FILE = os.path.join(basedir, 'config.json')

# --- Database Setup ---
db = SQLAlchemy(app)

# --- Helper Functions ---
def load_config():
    if not os.path.exists(CONFIG_FILE): return {}
    with open(CONFIG_FILE, 'r') as f: return json.load(f)

def save_config(config_data):
    with open(CONFIG_FILE, 'w') as f: json.dump(config_data, f, indent=4)

# --- Database Models ---
class SSHHost(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    friendly_name = db.Column(db.String(100), nullable=False, unique=True)
    hostname = db.Column(db.String(100), nullable=False)
    username = db.Column(db.String(100), nullable=False)

class SavedScript(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    script_type = db.Column(db.String(50), nullable=False)
    content = db.Column(db.Text, nullable=False)

# --- Routes ---
@app.route('/')
def index():
    hosts = SSHHost.query.order_by(SSHHost.friendly_name).all()
    scripts = SavedScript.query.order_by(SavedScript.name).all()
    return render_template('index.html', hosts=hosts, scripts=scripts)

# --- API: Settings ---
@app.route('/api/settings', methods=['GET', 'POST'])
def handle_settings():
    if request.method == 'POST':
        config = load_config()
        config['GEMINI_API_KEY'] = request.json.get('apiKey', '')
        save_config(config)
        return jsonify({'status': 'success', 'message': 'API Key saved.'})
    else:
        return jsonify({'apiKey': load_config().get('GEMINI_API_KEY', '')})

# --- API: AI Analysis ---
@app.route('/api/analyze', methods=['POST'])
def analyze_output():
    data = request.json
    api_key, command_output = data.get('apiKey'), data.get('output')
    if not api_key: return jsonify({'status': 'error', 'message': 'Gemini API Key is not configured.'}), 400
    if not command_output: return jsonify({'status': 'error', 'message': 'No output to analyze.'}), 400
    try:
        prompt = f"As an expert DevOps engineer, analyze the following command line output. Provide a concise summary and potential troubleshooting steps in Markdown.\n\nOutput:\n---\n{command_output}\n---"
        api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent?key={api_key}"
        response = requests.post(api_url, json={"contents": [{"parts": [{"text": prompt}]}]}, headers={'Content-Type': 'application/json'})
        response.raise_for_status()
        analysis = response.json()['candidates'][0]['content']['parts'][0]['text']
        return jsonify({'status': 'success', 'analysis': analysis})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

# --- API: Hosts ---
@app.route('/api/hosts', methods=['POST'])
def add_host():
    data = request.json
    new_host = SSHHost(friendly_name=data['friendly_name'], hostname=data['hostname'], username=data['username'])
    db.session.add(new_host)
    db.session.commit()
    return jsonify({'status': 'success', 'message': 'Host added!', 'host': {'id': new_host.id, 'friendly_name': new_host.friendly_name, 'hostname': new_host.hostname, 'username': new_host.username}}), 201

@app.route('/api/hosts/<int:host_id>', methods=['GET'])
def get_host(host_id):
    host = db.session.get(SSHHost, host_id)
    if not host: return jsonify({'status': 'error', 'message': 'Host not found.'}), 404
    return jsonify({'status': 'success', 'host': {'id': host.id, 'friendly_name': host.friendly_name, 'hostname': host.hostname, 'username': host.username}})

@app.route('/api/hosts/<int:host_id>', methods=['PUT'])
def update_host(host_id):
    host = db.session.get(SSHHost, host_id)
    if not host: return jsonify({'status': 'error', 'message': 'Host not found.'}), 404
    data = request.json
    host.friendly_name, host.hostname, host.username = data['friendly_name'], data['hostname'], data['username']
    db.session.commit()
    return jsonify({'status': 'success', 'message': 'Host updated!', 'host': {'id': host.id, 'friendly_name': host.friendly_name, 'hostname': host.hostname, 'username': host.username}})

@app.route('/api/hosts/<int:host_id>', methods=['DELETE'])
def delete_host(host_id):
    host = db.session.get(SSHHost, host_id)
    if not host: return jsonify({'status': 'error', 'message': 'Host not found.'}), 404
    db.session.delete(host)
    db.session.commit()
    return jsonify({'status': 'success', 'message': 'Host deleted.'})

@app.route('/api/hosts/<int:host_id>/test', methods=['POST'])
def test_ssh_connection(host_id):
    host = db.session.get(SSHHost, host_id)
    if not host: return jsonify({'status': 'error', 'message': 'Host not found.'}), 404
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(host.hostname, username=host.username, timeout=10)
        ssh.close()
        return jsonify({'status': 'success', 'message': 'Connection successful!'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': f"Connection failed: {e}"}), 500

# --- API: Scripts ---
@app.route('/api/scripts', methods=['POST'])
def save_script():
    data = request.json
    new_script = SavedScript(name=data['name'], script_type=data['type'], content=data['content'])
    db.session.add(new_script)
    db.session.commit()
    return jsonify({'status': 'success', 'message': 'Script saved!', 'script': {'id': new_script.id, 'name': new_script.name, 'script_type': new_script.script_type}}), 201

@app.route('/api/scripts/<int:script_id>', methods=['GET'])
def get_script(script_id):
    script = db.session.get(SavedScript, script_id)
    if not script: return jsonify({'status': 'error', 'message': 'Script not found.'}), 404
    return jsonify({'status': 'success', 'script': {'id': script.id, 'name': script.name, 'type': script.script_type, 'content': script.content}})

@app.route('/api/scripts/<int:script_id>', methods=['DELETE'])
def delete_script(script_id):
    script = db.session.get(SavedScript, script_id)
    if not script: return jsonify({'status': 'error', 'message': 'Script not found.'}), 404
    db.session.delete(script)
    db.session.commit()
    return jsonify({'status': 'success', 'message': 'Script deleted.'})

@app.route('/api/scripts/delete', methods=['POST'])
def delete_batch_scripts():
    script_ids = request.json.get('ids', [])
    if not script_ids: return jsonify({'status': 'error', 'message': 'No script IDs provided.'}), 400
    count = SavedScript.query.filter(SavedScript.id.in_(script_ids)).delete(synchronize_session=False)
    db.session.commit()
    return jsonify({'status': 'success', 'message': f'{count} scripts deleted.'})

# --- API: Execution ---
@app.route('/api/run', methods=['POST'])
def run_command():
    data = request.json
    host_ids, command, script_type = data.get('host_ids', []), data.get('command', ''), data.get('type', 'bash')
    if not host_ids or not command: return jsonify({'status': 'error', 'message': 'Host selection and command are required.'}), 400
    results, hosts = [], SSHHost.query.filter(SSHHost.id.in_(host_ids)).all()
    exec_command = f"python3 -c {shlex.quote(command)}" if script_type == 'python' else command
    for host in hosts:
        try:
            if script_type == 'ansible': raise NotImplementedError("Ansible execution is not supported.")
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(host.hostname, username=host.username, timeout=10)
            _, stdout, stderr = ssh.exec_command(exec_command)
            results.append({'host_name': host.friendly_name, 'status': 'error' if stderr.read() else 'success', 'output': stdout.read().decode(), 'error': stderr.read().decode()})
            ssh.close()
        except Exception as e:
            results.append({'host_name': host.friendly_name, 'status': 'error', 'output': '', 'error': f"Execution failed: {e}"})
    return jsonify({'results': results})

# --- Main Execution ---
if __name__ == '__main__':
    with app.app_context(): db.create_all()
    app.run(debug=True, host='0.0.0.0', port=5012)
