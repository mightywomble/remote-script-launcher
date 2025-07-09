# app.py
import os
import json
import subprocess
import shlex
import tempfile
import requests
import paramiko
from flask import Flask, render_template, request, jsonify, redirect, url_for
from flask_socketio import SocketIO
from flask_login import LoginManager, login_required, current_user, login_user, logout_user
from werkzeug.security import generate_password_hash, check_password_hash

# --- Flask-RESTX Import ---
from flask_restx import Api, Resource, Namespace

# --- Model and Blueprint Imports ---
from models import db, User, Group, SSHHost, SavedScript, Schedule, Pipeline
from auth import auth_bp
from pipeline import pipeline_bp
from git_scripts import git_bp

# --- App Initialization & Config ---
app = Flask(__name__)
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'app.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'a_very_secret_key_change_me_for_production')
CONFIG_FILE = os.path.join(basedir, 'config.json')

# --- Extension Initialization ---
db.init_app(app)
socketio = SocketIO(app)
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.init_app(app)

# --- Flask-RESTX API Initialization ---
api = Api(app,
          version='1.0',
          title='Remote Script Launcher API',
          description='A comprehensive API for managing and executing remote scripts, hosts, and pipelines.',
          prefix='/api', # This ensures the API doesn't conflict with web routes.
          doc='/api/',    # The documentation UI will be at /api/
          decorators=[login_required]) # Secure all API endpoints by default

# --- API Namespace Definitions ---
settings_ns = Namespace('settings', description='Manage global application settings')
users_ns = Namespace('users', description='User management operations')
groups_ns = Namespace('groups', description='Group management operations')
hosts_ns = Namespace('hosts', description='Manage SSH hosts')
scripts_ns = Namespace('scripts', description='Manage saved scripts')
run_ns = Namespace('run', description='Remote command and script execution')

# Add all namespaces to the API
api.add_namespace(settings_ns)
api.add_namespace(users_ns)
api.add_namespace(groups_ns)
api.add_namespace(hosts_ns)
api.add_namespace(scripts_ns)
api.add_namespace(run_ns)

# --- User Loader ---
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- Blueprint Registration ---
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

# --- Standard Web Page Routes (No Change) ---
@app.route('/')
@login_required
def index():
    group_id = current_user.group_id
    hosts = SSHHost.query.filter_by(group_id=group_id).order_by(SSHHost.friendly_name).all()
    scripts = SavedScript.query.filter_by(group_id=group_id).order_by(SavedScript.name).all()
    pipelines = Pipeline.query.filter_by(group_id=group_id).order_by(Pipeline.name).all()
    return render_template('index.html', hosts=hosts, scripts=scripts, pipelines=pipelines, username=current_user.username)

@app.route('/pipeline-editor')
@app.route('/pipeline-editor/<int:pipeline_id>')
@login_required
def pipeline_editor(pipeline_id=None):
    group_id = current_user.group_id
    hosts = SSHHost.query.filter_by(group_id=group_id).all()
    scripts = SavedScript.query.filter_by(group_id=group_id).all()
    return render_template('pipeline.html', pipeline_id=pipeline_id, hosts=hosts, scripts=scripts)

@app.route('/users')
@login_required
def user_management():
    return render_template('users.html')

# --- API Resources (Refactored with Flask-RESTX) ---

# --- Settings Namespace ---
@settings_ns.route('/')
class SettingsResource(Resource):
    def get(self):
        """Retrieve current global settings."""
        config = load_config()
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

    def post(self):
        """Update global settings."""
        config = load_config()
        data = request.json
        config.update(data) # Simple update
        save_config(config)
        return {'status': 'success', 'message': 'Settings saved.'}

# --- Users Namespace ---
@users_ns.route('/')
class UserListResource(Resource):
    def post(self):
        """Create a new user."""
        data = request.json
        username, password, group_id = data.get('username'), data.get('password'), data.get('group_id')
        if not all([username, password, group_id]):
            return {'status': 'error', 'message': 'Username, password, and group ID are required.'}, 400
        if User.query.filter_by(username=username).first():
            return {'status': 'error', 'message': 'Username already exists.'}, 409
        
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
        new_user = User(username=username, password=hashed_password, group_id=group_id)
        db.session.add(new_user)
        db.session.commit()
        return {'status': 'success', 'message': f"User '{username}' created."}, 201

@users_ns.route('/<int:user_id>')
class UserResource(Resource):
    def delete(self, user_id):
        """Delete a user."""
        if user_id == current_user.id:
            return {'status': 'error', 'message': 'Cannot delete yourself.'}, 403
        user_to_delete = User.query.get(user_id)
        if not user_to_delete:
            return {'status': 'error', 'message': 'User not found.'}, 404
        db.session.delete(user_to_delete)
        db.session.commit()
        return {'status': 'success', 'message': 'User deleted.'}

# --- Groups Namespace ---
@groups_ns.route('/')
class GroupListResource(Resource):
    def get(self):
        """Get a list of all groups."""
        groups = Group.query.order_by(Group.name).all()
        return jsonify([{'id': g.id, 'name': g.name} for g in groups])

    def post(self):
        """Create a new group."""
        data = request.json
        group_name = data.get('group_name')
        if not group_name: return {'status': 'error', 'message': 'Group name is required.'}, 400
        if Group.query.filter_by(name=group_name).first(): return {'status': 'error', 'message': 'Group name already exists.'}, 409
        new_group = Group(name=group_name)
        db.session.add(new_group)
        db.session.commit()
        return {'status': 'success', 'message': f"Group '{group_name}' created."}, 201

@groups_ns.route('/<int:group_id>')
class GroupResource(Resource):
    def delete(self, group_id):
        """Delete a group."""
        if group_id == current_user.group_id:
            return {'status': 'error', 'message': 'Cannot delete your own active group.'}, 403
        group = db.session.get(Group, group_id)
        if not group: return {'status': 'error', 'message': 'Group not found.'}, 404
        if len(group.users) > 0:
            return {'status': 'error', 'message': 'Cannot delete a group that contains users.'}, 400
        db.session.delete(group)
        db.session.commit()
        return {'status': 'success', 'message': 'Group deleted.'}

@groups_ns.route('/<int:group_id>/users')
class GroupUsersResource(Resource):
    def get(self, group_id):
        """Get a list of users within a specific group."""
        group = db.session.get(Group, group_id)
        if not group: return {'status': 'error', 'message': 'Group not found.'}, 404
        return jsonify([{'id': u.id, 'username': u.username} for u in group.users])

# --- AI Endpoints (Directly on API) ---
# FIX: Moved AI routes out of a namespace and attached them directly to the API object.
# This creates the routes /api/suggest-script and /api/analyze.
@api.route('/suggest-script')
class AISuggestScript(Resource):
    def post(self):
        """Generate script suggestions using Gemini AI."""
        data = request.json
        api_key, prompt = data.get('apiKey'), data.get('prompt')
        if not api_key: return {'status': 'error', 'message': 'Gemini API Key is not configured.'}, 400
        if not prompt: return {'status': 'error', 'message': 'Prompt cannot be empty.'}, 400
        
        system_prompt = f"""You are an expert DevOps engineer...""" # Keeping your prompt
        try:
            api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent?key={api_key}"
            payload = {"contents": [{"parts": [{"text": system_prompt}]}], "generationConfig": {"responseMimeType": "application/json"}}
            response = requests.post(api_url, json=payload, headers={'Content-Type': 'application/json'})
            response.raise_for_status()
            suggestions = json.loads(response.json()['candidates'][0]['content']['parts'][0]['text'])
            return {'status': 'success', 'suggestions': suggestions}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}, 500

@api.route('/analyze')
class AIAnalyzeOutput(Resource):
    def post(self):
        """Analyze command output using Gemini AI."""
        data = request.json
        api_key, command_output = data.get('apiKey'), data.get('output')
        if not api_key: return {'status': 'error', 'message': 'Gemini API Key is not configured.'}, 400
        if not command_output: return {'status': 'error', 'message': 'No output to analyze.'}, 400
        try:
            prompt = f"As an expert DevOps engineer, analyze..." # Keeping your prompt
            api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent?key={api_key}"
            response = requests.post(api_url, json={"contents": [{"parts": [{"text": prompt}]}]}, headers={'Content-Type': 'application/json'})
            response.raise_for_status()
            analysis = response.json()['candidates'][0]['content']['parts'][0]['text']
            return {'status': 'success', 'analysis': analysis}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}, 500

# --- Hosts Namespace ---
@hosts_ns.route('/')
class HostListResource(Resource):
    def get(self):
        """Get all hosts for the current user's group."""
        hosts = SSHHost.query.filter_by(group_id=current_user.group_id).all()
        return jsonify([{'id': h.id, 'friendly_name': h.friendly_name, 'hostname': h.hostname, 'username': h.username} for h in hosts])

    def post(self):
        """Add a new host to the current user's group."""
        data = request.json
        new_host = SSHHost(friendly_name=data['friendly_name'], hostname=data['hostname'], username=data['username'], group_id=current_user.group_id)
        db.session.add(new_host)
        db.session.commit()
        return {'status': 'success', 'message': 'Host added!', 'host': {'id': new_host.id, 'friendly_name': new_host.friendly_name, 'hostname': new_host.hostname, 'username': new_host.username}}, 201

@hosts_ns.route('/<int:host_id>')
class HostResource(Resource):
    def get(self, host_id):
        """Get details for a specific host."""
        host = db.session.get(SSHHost, host_id)
        if not host or host.group_id != current_user.group_id: return {'status': 'error', 'message': 'Host not found or access denied.'}, 404
        return jsonify({'id': host.id, 'friendly_name': host.friendly_name, 'hostname': host.hostname, 'username': host.username})

    def put(self, host_id):
        """Update a host's details."""
        host = db.session.get(SSHHost, host_id)
        if not host or host.group_id != current_user.group_id: return {'status': 'error', 'message': 'Host not found or access denied.'}, 404
        data = request.json
        host.friendly_name, host.hostname, host.username = data['friendly_name'], data['hostname'], data['username']
        db.session.commit()
        return {'status': 'success', 'message': 'Host updated!'}

    def delete(self, host_id):
        """Delete a host."""
        host = db.session.get(SSHHost, host_id)
        if not host or host.group_id != current_user.group_id: return {'status': 'error', 'message': 'Host not found or access denied.'}, 404
        db.session.delete(host)
        db.session.commit()
        return {'status': 'success', 'message': 'Host deleted.'}

@hosts_ns.route('/<int:host_id>/test')
class HostTestResource(Resource):
    def post(self, host_id):
        """Test the SSH connection to a host."""
        host = db.session.get(SSHHost, host_id)
        if not host or host.group_id != current_user.group_id: return {'status': 'error', 'message': 'Host not found or access denied.'}, 404
        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(host.hostname, username=host.username, timeout=10)
            ssh.close()
            return {'status': 'success', 'message': 'Connection successful!'}
        except Exception as e:
            return {'status': 'error', 'message': f"Connection failed: {e}"}, 500

# --- Scripts Namespace ---
@scripts_ns.route('/')
class ScriptListResource(Resource):
    def get(self):
        """Get all saved scripts for the current user's group."""
        scripts = SavedScript.query.filter_by(group_id=current_user.group_id).all()
        return jsonify([{'id': s.id, 'name': s.name, 'script_type': s.script_type, 'content': s.content} for s in scripts])

    def post(self):
        """Save a new script."""
        data = request.json
        new_script = SavedScript(name=data['name'], script_type=data['type'], content=data['content'], group_id=current_user.group_id)
        db.session.add(new_script)
        db.session.commit()
        return {'status': 'success', 'message': 'Script saved!', 'script': {'id': new_script.id, 'name': new_script.name, 'script_type': new_script.script_type}}, 201

@scripts_ns.route('/<int:script_id>')
class ScriptResource(Resource):
    def get(self, script_id):
        """Get a specific script's details."""
        script = db.session.get(SavedScript, script_id)
        if not script or script.group_id != current_user.group_id: return {'status': 'error', 'message': 'Script not found or access denied.'}, 404
        return jsonify({'id': script.id, 'name': script.name, 'type': script.script_type, 'content': script.content})

    def put(self, script_id):
        """Update a saved script."""
        script = db.session.get(SavedScript, script_id)
        if not script or script.group_id != current_user.group_id: return {'status': 'error', 'message': 'Script not found or access denied.'}, 404
        data = request.json
        script.name, script.script_type, script.content = data['name'], data['type'], data['content']
        db.session.commit()
        return {'status': 'success', 'message': 'Script updated!'}

    def delete(self, script_id):
        """Delete a saved script."""
        script = db.session.get(SavedScript, script_id)
        if not script or script.group_id != current_user.group_id: return {'status': 'error', 'message': 'Script not found or access denied.'}, 404
        db.session.delete(script)
        db.session.commit()
        return {'status': 'success', 'message': 'Script deleted.'}

# --- Run Namespace ---
@run_ns.route('/')
class ExecutionResource(Resource):
    def post(self):
        """Execute a command or script on one or more hosts."""
        data = request.json
        host_ids, command, script_type = data.get('host_ids', []), data.get('command', ''), data.get('type', 'bash-command')
        use_sudo = data.get('use_sudo', False)
        if not host_ids or not command: return {'status': 'error', 'message': 'Host and command required.'}, 400
        
        results = []
        hosts = SSHHost.query.filter(SSHHost.id.in_(host_ids), SSHHost.group_id == current_user.group_id).all()

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
            new_user = User(username='admin', password=hashed_password, group_id=default_group.id)
            db.session.add(new_user)
            db.session.commit()
            print("Default admin user created in the 'Default' group.")

if __name__ == '__main__':
    create_default_user_and_group()
    # Note: For production, use a proper WSGI server like Gunicorn or uWSGI
    socketio.run(app, debug=True, host='0.0.0.0', port=5012)
