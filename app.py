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

# --- API: Scripts ---
@app.route('/api/scripts', methods=['POST'])
def add_script():
    data = request.json
    new_script = SavedScript(name=data['name'], script_type=data['type'], content=data['content'])
    db.session.add(new_script)
    db.session.commit()
    return jsonify({'status': 'success', 'message': 'Script saved!', 'script': {'id': new_script.id, 'name': new_script.name, 'script_type': new_script.script_type}}), 201

@app.route('/api/scripts/<int:script_id>', methods=['GET', 'PUT', 'DELETE'])
def handle_script(script_id):
    script = db.session.get(SavedScript, script_id)
    if not script:
        return jsonify({'status': 'error', 'message': 'Script not found.'}), 404
    
    if request.method == 'GET':
        return jsonify({'status': 'success', 'script': {'id': script.id, 'name': script.name, 'type': script.script_type, 'content': script.content}})
    
    elif request.method == 'PUT':
        data = request.json
        script.name = data['name']
        script.script_type = data['type']
        script.content = data['content']
        db.session.commit()
        return jsonify({'status': 'success', 'message': 'Script updated!', 'script': {'id': script.id, 'name': script.name, 'script_type': script.script_type}})

    elif request.method == 'DELETE':
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

# Other routes (schedules, run, analyze) would go here...

if __name__ == '__main__':
    with app.app_context(): db.create_all()
    app.run(debug=True, host='0.0.0.0', port=5012)
