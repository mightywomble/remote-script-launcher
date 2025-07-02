# app.py
# Main Flask application file

from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy
import paramiko
import os
import shlex
import json
import requests

# --- App Initialization & Config ---
app = Flask(__name__)
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'app.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'a_very_secret_key_change_me'
CONFIG_FILE = os.path.join(basedir, 'config.json')

# --- Database Setup ---
db = SQLAlchemy(app)

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

class Schedule(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    host_id = db.Column(db.Integer, db.ForeignKey('ssh_host.id'), nullable=False)
    script_id = db.Column(db.Integer, db.ForeignKey('saved_script.id'), nullable=False)
    hour = db.Column(db.Integer, nullable=False)
    minute = db.Column(db.Integer, nullable=False)
    host = db.relationship('SSHHost')
    script = db.relationship('SavedScript')

# --- Helper Functions ---
def load_config():
    if not os.path.exists(CONFIG_FILE): return {}
    with open(CONFIG_FILE, 'r') as f: return json.load(f)

def save_config(config_data):
    with open(CONFIG_FILE, 'w') as f: json.dump(config_data, f, indent=4)

# --- Main Route ---
@app.route('/')
def index():
    hosts = SSHHost.query.order_by(SSHHost.friendly_name).all()
    scripts = SavedScript.query.order_by(SavedScript.name).all()
    return render_template('index.html', hosts=hosts, scripts=scripts)

# --- API: Settings ---
@app.route('/api/settings', methods=['GET', 'POST'])
def handle_settings():
    config = load_config()
    if request.method == 'POST':
        data = request.json
        config['GEMINI_API_KEY'] = data.get('apiKey', config.get('GEMINI_API_KEY'))
        config['DISCORD_WEBHOOK_URL'] = data.get('discordUrl', config.get('DISCORD_WEBHOOK_URL'))
        save_config(config)
        return jsonify({'status': 'success', 'message': 'Settings saved.'})
    else:
        return jsonify({
            'apiKey': config.get('GEMINI_API_KEY', ''),
            'discordUrl': config.get('DISCORD_WEBHOOK_URL', '')
        })

# --- API: AI ---
@app.route('/api/suggest-script', methods=['POST'])
def suggest_script():
    data = request.json
    api_key, prompt = data.get('apiKey'), data.get('prompt')
    if not api_key: return jsonify({'status': 'error', 'message': 'Gemini API Key is not configured.'}), 400
    if not prompt: return jsonify({'status': 'error', 'message': 'Prompt cannot be empty.'}), 400
    
    system_prompt = f"""
    You are an expert DevOps engineer. Based on the user's request, generate four different code snippets to accomplish the task.
    Provide the output in a JSON object with the following exact keys: "bash_command", "bash_script", "python_script", "ansible_playbook".
    Each value should be a string containing only the code for that snippet. Do not include any extra explanation or markdown formatting like ```.

    User request: "{prompt}"
    """
    try:
        # Corrected the URL to be a simple string, removing the Markdown formatting.
        api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent?key={api_key}"
        payload = {"contents": [{"parts": [{"text": system_prompt}]}], "generationConfig": {"responseMimeType": "application/json"}}
        response = requests.post(api_url, json=payload, headers={'Content-Type': 'application/json'})
        response.raise_for_status()
        suggestions = json.loads(response.json()['candidates'][0]['content']['parts'][0]['text'])
        return jsonify({'status': 'success', 'suggestions': suggestions})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/analyze', methods=['POST'])
def analyze_output():
    data = request.json
    api_key, command_output = data.get('apiKey'), data.get('output')
    if not api_key: return jsonify({'status': 'error', 'message': 'Gemini API Key is not configured.'}), 400
    if not command_output: return jsonify({'status': 'error', 'message': 'No output to analyze.'}), 400
    try:
        prompt = f"As an expert DevOps engineer, analyze the following command line output. Provide a concise summary and potential troubleshooting steps in Markdown.\n\nOutput:\n---\n{command_output}\n---"
        # Corrected the URL to be a simple string, removing the Markdown formatting.
        api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent?key={api_key}"
        response = requests.post(api_url, json={"contents": [{"parts": [{"text": prompt}]}]}, headers={'Content-Type': 'application/json'})
        response.raise_for_status()
        analysis = response.json()['candidates'][0]['content']['parts'][0]['text']
        return jsonify({'status': 'success', 'analysis': analysis})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

# --- API: Hosts ---
@app.route('/api/hosts', methods=['GET','POST'])
def handle_hosts():
    if request.method == 'POST':
        data = request.json
        new_host = SSHHost(friendly_name=data['friendly_name'], hostname=data['hostname'], username=data['username'])
        db.session.add(new_host)
        db.session.commit()
        return jsonify({'status': 'success', 'message': 'Host added!', 'host': {'id': new_host.id, 'friendly_name': new_host.friendly_name, 'hostname': new_host.hostname, 'username': new_host.username}}), 201
    else: # GET
        return jsonify([{'id': h.id, 'friendly_name': h.friendly_name, 'hostname': h.hostname, 'username': h.username} for h in SSHHost.query.all()])

@app.route('/api/hosts/<int:host_id>', methods=['GET','PUT','DELETE'])
def handle_host(host_id):
    host = db.session.get(SSHHost, host_id)
    if not host: return jsonify({'status': 'error', 'message': 'Host not found.'}), 404
    if request.method == 'GET':
        return jsonify({'status': 'success', 'host': {'id': host.id, 'friendly_name': host.friendly_name, 'hostname': host.hostname, 'username': host.username}})
    elif request.method == 'PUT':
        data = request.json
        host.friendly_name, host.hostname, host.username = data['friendly_name'], data['hostname'], data['username']
        db.session.commit()
        return jsonify({'status': 'success', 'message': 'Host updated!', 'host': {'id': host.id, 'friendly_name': host.friendly_name, 'hostname': host.hostname, 'username': host.username}})
    elif request.method == 'DELETE':
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
@app.route('/api/scripts', methods=['GET', 'POST'])
def handle_scripts():
    if request.method == 'POST':
        data = request.json
        new_script = SavedScript(name=data['name'], script_type=data['type'], content=data['content'])
        db.session.add(new_script)
        db.session.commit()
        return jsonify({'status': 'success', 'message': 'Script saved!', 'script': {'id': new_script.id, 'name': new_script.name, 'script_type': new_script.script_type}}), 201
    else: # GET
        return jsonify([{'id': s.id, 'name': s.name, 'script_type': s.script_type} for s in SavedScript.query.all()])

@app.route('/api/scripts/<int:script_id>', methods=['GET', 'PUT', 'DELETE'])
def handle_script(script_id):
    script = db.session.get(SavedScript, script_id)
    if not script: return jsonify({'status': 'error', 'message': 'Script not found.'}), 404
    if request.method == 'GET':
        return jsonify({'status': 'success', 'script': {'id': script.id, 'name': script.name, 'type': script.script_type, 'content': script.content}})
    elif request.method == 'PUT':
        data = request.json
        script.name, script.script_type, script.content = data['name'], data['type'], data['content']
        db.session.commit()
        return jsonify({'status': 'success', 'message': 'Script updated!', 'script': {'id': script.id, 'name': script.name, 'script_type': script.script_type}})
    elif request.method == 'DELETE':
        db.session.delete(script)
        db.session.commit()
        return jsonify({'status': 'success', 'message': 'Script deleted.'})

# --- API: Schedules ---
@app.route('/api/schedules', methods=['GET', 'POST'])
def handle_schedules():
    if request.method == 'POST':
        data = request.json
        new_schedule = Schedule(name=data['name'], host_id=data['host_id'], script_id=data['script_id'], hour=data['hour'], minute=data['minute'])
        db.session.add(new_schedule)
        db.session.commit()
        return jsonify({'status': 'success', 'message': 'Schedule saved. Restart scheduler to activate.'}), 201
    else: # GET
        schedules = Schedule.query.all()
        return jsonify([{'id': s.id, 'name': s.name, 'host_name': s.host.friendly_name, 'script_name': s.script.name, 'hour': s.hour, 'minute': s.minute} for s in schedules])

@app.route('/api/schedules/<int:schedule_id>', methods=['DELETE'])
def delete_schedule(schedule_id):
    schedule = db.session.get(Schedule, schedule_id)
    if not schedule: return jsonify({'status': 'error', 'message': 'Schedule not found.'}), 404
    db.session.delete(schedule)
    db.session.commit()
    return jsonify({'status': 'success', 'message': 'Schedule deleted. Restart scheduler to deactivate.'})

# --- API: Execution ---
@app.route('/api/run', methods=['POST'])
def run_command():
    data = request.json
    host_ids, command, script_type = data.get('host_ids', []), data.get('command', ''), data.get('type', 'bash-command')
    if not host_ids or not command: return jsonify({'status': 'error', 'message': 'Host and command required.'}), 400
    results, hosts = [], SSHHost.query.filter(SSHHost.id.in_(host_ids)).all()
    exec_command = f"python3 -c {shlex.quote(command)}" if script_type == 'python-script' else command
    for host in hosts:
        try:
            if script_type == 'ansible-playbook': raise NotImplementedError("Ansible execution is not supported.")
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(host.hostname, username=host.username, timeout=10)
            _, stdout, stderr = ssh.exec_command(exec_command)
            output, error = stdout.read().decode(), stderr.read().decode()
            results.append({'host_name': host.friendly_name, 'status': 'error' if error else 'success', 'output': output, 'error': error})
            ssh.close()
        except Exception as e:
            results.append({'host_name': host.friendly_name, 'status': 'error', 'output': '', 'error': f"Execution failed: {e}"})
    return jsonify({'results': results})


if __name__ == '__main__':
    with app.app_context(): db.create_all()
    app.run(debug=True, host='0.0.0.0', port=5012)
