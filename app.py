# app.py
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from flask_socketio import SocketIO
from flask_login import LoginManager, login_required, current_user, login_user, logout_user
from werkzeug.security import generate_password_hash, check_password_hash
import os
import json
import requests
import paramiko
import shlex
import subprocess
import tempfile
import hmac
import hashlib
import secrets
from collections import Counter

# Import db and models from the new models.py file
from models import db, User, Group, SSHHost, SavedScript, Schedule, Pipeline, APIToken, ActivityLog
from decorators import admin_required

# --- App Initialization & Config ---
app = Flask(__name__)
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'app.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'a_very_secret_key_change_me_for_production'
CONFIG_FILE = os.path.join(basedir, 'config.json')

# Initialize extensions
db.init_app(app)
socketio = SocketIO(app)

# --- Login Manager Setup ---
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- Blueprint Registration ---
from auth import auth_bp
from pipeline import pipeline_bp
from git_scripts import git_bp

# Pass necessary instances to blueprints
pipeline_bp.app = app
pipeline_bp.socketio = socketio
git_bp.load_config = lambda: load_config()

app.register_blueprint(auth_bp)
app.register_blueprint(pipeline_bp)
app.register_blueprint(git_bp)


# --- Helper Functions ---
def load_config():
    if not os.path.exists(CONFIG_FILE): return {}
    with open(CONFIG_FILE, 'r') as f: return json.load(f)

def save_config(config_data):
    with open(CONFIG_FILE, 'w') as f: json.dump(config_data, f, indent=4)

def log_activity(action):
    try:
        log = ActivityLog(action=action, user_id=current_user.id, group_id=current_user.group_id)
        db.session.add(log)
        db.session.commit()
    except Exception as e:
        print(f"Error logging activity: {e}")


# --- Main Routes ---
@app.route('/')
@login_required
def index():
    group_id = current_user.group_id
    hosts = SSHHost.query.filter_by(group_id=group_id).order_by(SSHHost.friendly_name).all()
    scripts = SavedScript.query.filter_by(group_id=group_id).order_by(SavedScript.name).all()
    pipelines = Pipeline.query.filter_by(group_id=group_id).order_by(Pipeline.name).all()
    return render_template('index.html', hosts=hosts, scripts=scripts, pipelines=pipelines, username=current_user.username, is_admin=current_user.is_admin)

@app.route('/pipeline-editor')
@app.route('/pipeline-editor/<int:pipeline_id>')
@login_required
def pipeline_editor(pipeline_id=None):
    group_id = current_user.group_id
    hosts = SSHHost.query.filter_by(group_id=group_id).all()
    scripts = SavedScript.query.filter_by(group_id=group_id).all()
    return render_template('pipeline.html', pipeline_id=pipeline_id, hosts=hosts, scripts=scripts)

@app.route('/users')
@admin_required
def user_management():
    return render_template('users.html')

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html', username=current_user.username)

# --- API Routes ---

@app.route('/api/dashboard-stats')
@login_required
def dashboard_stats():
    group_id = current_user.group_id
    
    counts = {
        "hosts": SSHHost.query.filter_by(group_id=group_id).count(),
        "scripts": SavedScript.query.filter_by(group_id=group_id).count(),
        "pipelines": Pipeline.query.filter_by(group_id=group_id).count(),
        "users": User.query.filter_by(group_id=group_id).count()
    }

    logs = ActivityLog.query.filter_by(group_id=group_id).order_by(ActivityLog.timestamp.desc()).limit(10).all()
    log_list = [{'timestamp': l.timestamp.isoformat(), 'user': l.user.username, 'action': l.action} for l in logs]

    scripts = SavedScript.query.filter_by(group_id=group_id).all()
    script_types = Counter(s.script_type for s in scripts)
    
    return jsonify({
        "counts": counts,
        "logs": log_list,
        "script_types": dict(script_types)
    })

# --- API: Settings & User Management ---
@app.route('/api/settings', methods=['GET', 'POST'])
@admin_required
def handle_settings():
    config = load_config()
    if request.method == 'POST':
        data = request.json
        config['GEMINI_API_KEY'] = data.get('apiKey', config.get('GEMINI_API_KEY'))
        config['DISCORD_WEBHOOK_URL'] = data.get('discordUrl', config.get('DISCORD_WEBHOOK_URL'))
        config['EMAIL_TO'] = data.get('email_to', config.get('EMAIL_TO'))
        config['SMTP_SERVER'] = data.get('smtp_server', config.get('SMTP_SERVER'))
        config['SMTP_PORT'] = data.get('smtp_port', config.get('SMTP_PORT'))
        config['SMTP_USER'] = data.get('smtp_user', config.get('SMTP_USER'))
        config['SMTP_PASSWORD'] = data.get('smtp_password', config.get('SMTP_PASSWORD'))
        config['GITHUB_REPO'] = data.get('github_repo', config.get('GITHUB_REPO'))
        config['GITHUB_PAT'] = data.get('github_pat', config.get('GITHUB_PAT'))
        config['GITHUB_DEV_BRANCH'] = data.get('github_dev_branch', config.get('GITHUB_DEV_BRANCH'))
        config['ZABBIX_API_KEY'] = data.get('zabbix_api_key', config.get('ZABBIX_API_KEY'))
        save_config(config)
        return jsonify({'status': 'success', 'message': 'Settings saved.'})
    else: # GET
        return jsonify({
            'apiKey': config.get('GEMINI_API_KEY', ''),
            'discordUrl': config.get('DISCORD_WEBHOOK_URL', ''),
            'email_to': config.get('EMAIL_TO', ''),
            'smtp_server': config.get('SMTP_SERVER', ''),
            'smtp_port': config.get('SMTP_PORT', ''),
            'smtp_user': config.get('SMTP_USER', ''),
            'smtp_password': config.get('SMTP_PASSWORD', ''),
            'github_repo': config.get('GITHUB_REPO', ''),
            'github_pat': config.get('GITHUB_PAT', ''),
            'github_dev_branch': config.get('GITHUB_DEV_BRANCH', 'dev'),
            'zabbix_api_key': config.get('ZABBIX_API_KEY', '')
        })

@app.route('/api/users', methods=['POST'])
@admin_required
def add_user():
    data = request.json
    username, password, group_id, role = data.get('username'), data.get('password'), data.get('group_id'), data.get('role', 'operator')
    if not all([username, password, group_id]):
        return jsonify({'status': 'error', 'message': 'Username, password, and group ID are required.'}), 400
    if User.query.filter_by(username=username).first():
        return jsonify({'status': 'error', 'message': 'Username already exists.'}), 409
    
    hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
    new_user = User(username=username, password=hashed_password, group_id=group_id, role=role)
    db.session.add(new_user)
    db.session.commit()
    log_activity(f"Created user: {username}")
    return jsonify({'status': 'success', 'message': f"User '{username}' created."}), 201

@app.route('/api/users/<int:user_id>', methods=['DELETE'])
@admin_required
def delete_user(user_id):
    if user_id == current_user.id:
        return jsonify({'status': 'error', 'message': 'Cannot delete yourself.'}), 403
    user_to_delete = User.query.get(user_id)
    if not user_to_delete:
        return jsonify({'status': 'error', 'message': 'User not found.'}), 404
    log_activity(f"Deleted user: {user_to_delete.username}")
    db.session.delete(user_to_delete)
    db.session.commit()
    return jsonify({'status': 'success', 'message': 'User deleted.'})

@app.route('/api/groups', methods=['GET', 'POST'])
@admin_required
def handle_groups():
    if request.method == 'POST':
        data = request.json
        group_name = data.get('group_name')
        if not group_name: return jsonify({'status': 'error', 'message': 'Group name is required.'}), 400
        if Group.query.filter_by(name=group_name).first(): return jsonify({'status': 'error', 'message': 'Group name already exists.'}), 409
        new_group = Group(name=group_name)
        db.session.add(new_group)
        db.session.commit()
        log_activity(f"Created group: {group_name}")
        return jsonify({'status': 'success', 'message': f"Group '{group_name}' created."}), 201
    else: # GET
        groups = Group.query.order_by(Group.name).all()
        return jsonify([{'id': g.id, 'name': g.name} for g in groups])

@app.route('/api/groups/<int:group_id>', methods=['DELETE'])
@admin_required
def delete_group(group_id):
    if group_id == current_user.group_id:
        return jsonify({'status': 'error', 'message': 'Cannot delete your own active group.'}), 403
    group = db.session.get(Group, group_id)
    if not group: return jsonify({'status': 'error', 'message': 'Group not found.'}), 404
    if len(group.users) > 0:
        return jsonify({'status': 'error', 'message': 'Cannot delete a group that contains users.'}), 400
    log_activity(f"Deleted group: {group.name}")
    db.session.delete(group)
    db.session.commit()
    return jsonify({'status': 'success', 'message': 'Group deleted.'})

@app.route('/api/groups/<int:group_id>/users', methods=['GET'])
@admin_required
def get_users_in_group(group_id):
    group = db.session.get(Group, group_id)
    if not group: return jsonify({'status': 'error', 'message': 'Group not found.'}), 404
    return jsonify([{'id': u.id, 'username': u.username, 'role': u.role} for u in group.users])

@app.route('/api/api-tokens', methods=['GET', 'POST'])
@admin_required
def handle_api_tokens():
    group_id = request.args.get('group_id', current_user.group_id)
    if request.method == 'POST':
        description = request.json.get('description')
        if not description: return jsonify({'status': 'error', 'message': 'Description is required.'}), 400
        new_token = APIToken(description=description, group_id=group_id)
        db.session.add(new_token)
        db.session.commit()
        log_activity(f"Created API token: {description}")
        return jsonify({'status': 'success', 'message': 'API Token created!', 'token': new_token.token})
    else: # GET
        tokens = APIToken.query.filter_by(group_id=group_id).all()
        return jsonify([{'id': t.id, 'description': t.description, 'token_prefix': t.token[:8]} for t in tokens])

@app.route('/api/api-tokens/<int:token_id>', methods=['DELETE'])
@admin_required
def delete_api_token(token_id):
    token = db.session.get(APIToken, token_id)
    if not token or token.group_id != current_user.group_id:
        return jsonify({'status': 'error', 'message': 'Token not found or access denied.'}), 404
    log_activity(f"Deleted API token: {token.description}")
    db.session.delete(token)
    db.session.commit()
    return jsonify({'status': 'success', 'message': 'API Token deleted.'})

# --- API: AI ---
@app.route('/api/suggest-script', methods=['POST'])
@login_required
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
        pi_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent?key={api_key}"
        payload = {"contents": [{"parts": [{"text": system_prompt}]}], "generationConfig": {"responseMimeType": "application/json"}}
        response = requests.post(api_url, json=payload, headers={'Content-Type': 'application/json'})
        response.raise_for_status()
        suggestions = json.loads(response.json()['candidates'][0]['content']['parts'][0]['text'])
        return jsonify({'status': 'success', 'suggestions': suggestions})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/analyze', methods=['POST'])
@login_required
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
@app.route('/api/hosts', methods=['GET','POST'])
@login_required
def handle_hosts():
    group_id = current_user.group_id
    if request.method == 'POST':
        data = request.json
        new_host = SSHHost(friendly_name=data['friendly_name'], hostname=data['hostname'], username=data['username'], group_id=group_id)
        db.session.add(new_host)
        db.session.commit()
        log_activity(f"Created host: {data['friendly_name']}")
        return jsonify({'status': 'success', 'message': 'Host added!', 'host': {'id': new_host.id, 'friendly_name': new_host.friendly_name, 'hostname': new_host.hostname, 'username': new_host.username}}), 201
    else: # GET
        hosts = SSHHost.query.filter_by(group_id=group_id).all()
        return jsonify([{'id': h.id, 'friendly_name': h.friendly_name, 'hostname': h.hostname, 'username': h.username} for h in hosts])

@app.route('/api/hosts/<int:host_id>', methods=['GET','PUT','DELETE'])
@login_required
def handle_host(host_id):
    host = db.session.get(SSHHost, host_id)
    if not host or host.group_id != current_user.group_id:
        return jsonify({'status': 'error', 'message': 'Host not found or access denied.'}), 404
    if request.method == 'GET':
        return jsonify({'status': 'success', 'host': {'id': host.id, 'friendly_name': host.friendly_name, 'hostname': host.hostname, 'username': host.username}})
    elif request.method == 'PUT':
        data = request.json
        host.friendly_name, host.hostname, host.username = data['friendly_name'], data['hostname'], data['username']
        db.session.commit()
        log_activity(f"Updated host: {data['friendly_name']}")
        return jsonify({'status': 'success', 'message': 'Host updated!', 'host': {'id': host.id, 'friendly_name': host.friendly_name, 'hostname': host.hostname, 'username': host.username}})
    elif request.method == 'DELETE':
        log_activity(f"Deleted host: {host.friendly_name}")
        db.session.delete(host)
        db.session.commit()
        return jsonify({'status': 'success', 'message': 'Host deleted.'})

@app.route('/api/hosts/<int:host_id>/test', methods=['POST'])
@login_required
def test_ssh_connection(host_id):
    host = db.session.get(SSHHost, host_id)
    if not host or host.group_id != current_user.group_id:
        return jsonify({'status': 'error', 'message': 'Host not found or access denied.'}), 404
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
@login_required
def handle_scripts():
    group_id = current_user.group_id
    if request.method == 'POST':
        data = request.json
        new_script = SavedScript(name=data['name'], script_type=data['type'], content=data['content'], group_id=group_id)
        db.session.add(new_script)
        db.session.commit()
        log_activity(f"Created script: {data['name']}")
        return jsonify({'status': 'success', 'message': 'Script saved!', 'script': {'id': new_script.id, 'name': new_script.name, 'script_type': new_script.script_type}}), 201
    else: # GET
        scripts = SavedScript.query.filter_by(group_id=group_id).all()
        return jsonify([{'id': s.id, 'name': s.name, 'script_type': s.script_type, 'content': s.content} for s in scripts])

@app.route('/api/scripts/<int:script_id>', methods=['GET', 'PUT', 'DELETE'])
@login_required
def handle_script(script_id):
    script = db.session.get(SavedScript, script_id)
    if not script or script.group_id != current_user.group_id:
        return jsonify({'status': 'error', 'message': 'Script not found or access denied.'}), 404
    if request.method == 'GET':
        return jsonify({'status': 'success', 'script': {'id': script.id, 'name': script.name, 'type': script.script_type, 'content': script.content}})
    elif request.method == 'PUT':
        data = request.json
        script.name, script.script_type, script.content = data['name'], data['type'], data['content']
        db.session.commit()
        log_activity(f"Updated script: {data['name']}")
        return jsonify({'status': 'success', 'message': 'Script updated!', 'script': {'id': script.id, 'name': script.name, 'script_type': script.script_type}})
    elif request.method == 'DELETE':
        log_activity(f"Deleted script: {script.name}")
        db.session.delete(script)
        db.session.commit()
        return jsonify({'status': 'success', 'message': 'Script deleted.'})

# --- API: Execution ---
@app.route('/api/run', methods=['POST'])
@login_required
def run_command():
    data = request.json
    host_ids, command, script_type = data.get('host_ids', []), data.get('command', ''), data.get('type', 'bash-command')
    use_sudo = data.get('use_sudo', False)
    if not host_ids or not command: return jsonify({'status': 'error', 'message': 'Host and command required.'}), 400
    
    results = []
    hosts = SSHHost.query.filter(SSHHost.id.in_(host_ids), SSHHost.group_id == current_user.group_id).all()
    log_activity(f"Ran command on {len(hosts)} host(s).")

    for host in hosts:
        try:
            if script_type == 'ansible-playbook':
                with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.yml') as playbook_file:
                    playbook_file.write(command)
                    playbook_path = playbook_file.name
                with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.ini') as inventory_file:
                    inventory_file.write(f"[{host.friendly_name}]\n{host.hostname} ansible_user={host.username}\n")
                    inventory_path = inventory_file.name
                ansible_command = ['ansible-playbook', '-i', inventory_path, playbook_path]
                if use_sudo: ansible_command.append('--become')
                process = subprocess.run(ansible_command, capture_output=True, text=True)
                output, error = process.stdout, process.stderr
                os.unlink(playbook_path)
                os.unlink(inventory_path)
                results.append({'host_name': host.friendly_name, 'status': 'error' if process.returncode != 0 else 'success', 'output': output, 'error': error})
            else:
                exec_command = f"python3 -c {shlex.quote(command)}" if script_type == 'python-script' else command
                if use_sudo: exec_command = f"sudo {exec_command}"
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

# --- API: Schedules (Restored) ---
@app.route('/api/schedules', methods=['GET', 'POST'])
@login_required
def handle_schedules():
    group_id = current_user.group_id
    if request.method == 'POST':
        data = request.json
        new_schedule = Schedule(name=data['name'], host_id=data['host_id'], script_id=data['script_id'], hour=data['hour'], minute=data['minute'])
        db.session.add(new_schedule)
        db.session.commit()
        log_activity(f"Created schedule: {data['name']}")
        return jsonify({'status': 'success', 'message': 'Schedule saved. Restart scheduler to activate.'}), 201
    else: # GET
        group_scripts = [s.id for s in SavedScript.query.filter_by(group_id=group_id).all()]
        group_hosts = [h.id for h in SSHHost.query.filter_by(group_id=group_id).all()]
        schedules = Schedule.query.filter(Schedule.script_id.in_(group_scripts), Schedule.host_id.in_(group_hosts)).all()
        return jsonify([{'id': s.id, 'name': s.name, 'host_name': s.host.friendly_name, 'script_name': s.script.name, 'hour': s.hour, 'minute': s.minute} for s in schedules])

@app.route('/api/schedules/<int:schedule_id>', methods=['DELETE'])
@login_required
def delete_schedule(schedule_id):
    schedule = db.session.get(Schedule, schedule_id)
    if not schedule: return jsonify({'status': 'error', 'message': 'Schedule not found.'}), 404
    host = db.session.get(SSHHost, schedule.host_id)
    if not host or host.group_id != current_user.group_id:
        return jsonify({'status': 'error', 'message': 'Access denied to this schedule.'}), 403
    log_activity(f"Deleted schedule: {schedule.name}")
    db.session.delete(schedule)
    db.session.commit()
    return jsonify({'status': 'success', 'message': 'Schedule deleted. Restart scheduler to deactivate.'})


# --- First Run Setup ---
def create_default_user_and_group():
    with app.app_context():
        db.create_all()
        if Group.query.first() is None:
            default_group = Group(name='Default')
            db.session.add(default_group)
            db.session.commit()
            print("Default group created.")
        
        if User.query.first() is None:
            default_group = Group.query.first()
            hashed_password = generate_password_hash('admin', method='pbkdf2:sha256')
            new_user = User(username='admin', password=hashed_password, group_id=default_group.id, role='admin')
            db.session.add(new_user)
            db.session.commit()
            print("Default admin user created in the 'Default' group.")

if __name__ == '__main__':
    create_default_user_and_group()
    socketio.run(app, debug=True, host='0.0.0.0', port=5012)
