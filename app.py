# app.py
# Main Flask application file

from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy
import paramiko
import os
import shlex
import json
import requests
from apscheduler.schedulers.background import BackgroundScheduler

# --- App Initialization & Config ---
app = Flask(__name__)
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'app.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'a_very_secret_key_change_me'
CONFIG_FILE = os.path.join(basedir, 'config.json')

# --- Database & Scheduler Setup ---
db = SQLAlchemy(app)
# We need a scheduler instance here too to manage jobs from the web UI
scheduler = BackgroundScheduler(daemon=True)

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

# --- Routes ---
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

# --- API: Schedules ---
@app.route('/api/schedules', methods=['GET', 'POST'])
def handle_schedules():
    if request.method == 'POST':
        data = request.json
        new_schedule = Schedule(name=data['name'], host_id=data['host_id'], script_id=data['script_id'], hour=data['hour'], minute=data['minute'])
        db.session.add(new_schedule)
        db.session.commit()
        # Here you would signal the running scheduler to add the new job.
        # This is complex and often handled by restarting the scheduler or using a shared message queue.
        # For this example, we assume the scheduler will pick it up on its next full load or restart.
        return jsonify({'status': 'success', 'message': 'Schedule saved. It will become active on the next scheduler restart.'}), 201
    else: # GET
        schedules = Schedule.query.all()
        return jsonify([{'id': s.id, 'name': s.name, 'host_name': s.host.friendly_name, 'script_name': s.script.name, 'hour': s.hour, 'minute': s.minute} for s in schedules])

@app.route('/api/schedules/<int:schedule_id>', methods=['DELETE'])
def delete_schedule(schedule_id):
    schedule = db.session.get(Schedule, schedule_id)
    if not schedule: return jsonify({'status': 'error', 'message': 'Schedule not found.'}), 404
    db.session.delete(schedule)
    db.session.commit()
    # Signal the scheduler to remove the job
    return jsonify({'status': 'success', 'message': 'Schedule deleted. It will be removed on the next scheduler restart.'})


# --- API: Scripts ---
# (Script APIs remain largely the same)
@app.route('/api/scripts', methods=['POST'])
def save_script():
    data = request.json
    new_script = SavedScript(name=data['name'], script_type=data['type'], content=data['content'])
    db.session.add(new_script)
    db.session.commit()
    return jsonify({'status': 'success', 'message': 'Script saved!', 'script': {'id': new_script.id, 'name': new_script.name, 'script_type': new_script.script_type}}), 201

# --- API: Execution ---
@app.route('/api/run', methods=['POST'])
def run_command():
    data = request.json
    host_ids, command, script_type = data.get('host_ids', []), data.get('command', ''), data.get('type', 'bash-command')
    if not host_ids or not command: return jsonify({'status': 'error', 'message': 'Host selection and command are required.'}), 400
    results, hosts = [], SSHHost.query.filter(SSHHost.id.in_(host_ids)).all()
    exec_command = command
    if script_type == 'python-script': exec_command = f"python3 -c {shlex.quote(command)}"
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

# --- Main Execution ---
if __name__ == '__main__':
    with app.app_context(): db.create_all()
    app.run(debug=True, host='0.0.0.0', port=5012)
