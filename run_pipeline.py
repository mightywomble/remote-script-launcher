# run_pipeline.py
import os
import shlex
import json
import paramiko
import subprocess
import tempfile
from models import db, Pipeline, SSHHost, SavedScript
from flask_socketio import SocketIO

class PipelineRunner:
    def __init__(self, pipeline_id, app, socketio, dry_run=False):
        self.pipeline_id = pipeline_id
        self.app = app # Store the app instance
        self.socketio = socketio
        self.dry_run = dry_run
        self.pipeline = None
        self.nodes = {}
        self.edges = []

    def run(self):
        """Starts the pipeline execution within an application context."""
        with self.app.app_context():
            self.pipeline = db.session.get(Pipeline, self.pipeline_id)
            if not self.pipeline:
                self.emit_log("error", f"Pipeline with ID {self.pipeline_id} not found.")
                return

            self.nodes = {node['id']: node for node in json.loads(self.pipeline.nodes)}
            self.edges = json.loads(self.pipeline.edges)
            
            self.emit_log("info", f"Starting pipeline: '{self.pipeline.name}'")
            if self.dry_run:
                self.emit_log("info", "*** This is a DRY RUN. No commands will be executed. ***")

            start_nodes = self.find_start_nodes()
            if not start_nodes:
                self.emit_log("error", "Pipeline has no starting point (e.g., a Host node).")
                return

            for start_node_id in start_nodes:
                self.execute_from_node(start_node_id)

            self.emit_log("info", "Pipeline execution finished.")

    def execute_from_node(self, node_id):
        """Recursively executes nodes in the pipeline."""
        node = self.nodes.get(node_id)
        if not node:
            return

        self.emit_log("info", f"Executing step: {node['name']}")
        
        success = self.execute_step(node)

        next_edges = self.find_next_edges(node_id, 'success' if success else 'failure')
        for edge in next_edges:
            self.execute_from_node(edge['to'])

    def execute_step(self, node):
        """Executes the logic for a single step."""
        if node['type'] == 'host':
            self.emit_log("success", f"Targeting host: {node['name']}")
            return True
        
        if node['type'] == 'script':
            host_node = self.find_host_for_script(node['id'])
            if not host_node:
                self.emit_log("error", f"No host found for script: {node['name']}")
                return False

            script = db.session.get(SavedScript, int(node['scriptId']))
            if not script:
                self.emit_log("error", f"Script '{node['name']}' not found in database.")
                return False

            if self.dry_run:
                self.emit_log("info", f"[DRY RUN] Would execute script '{script.name}' on host '{host_node['name']}'.")
                self.emit_log("output", script.content)
                return True

            # Real execution
            try:
                host_details = db.session.get(SSHHost, int(host_node['hostId']))
                
                if script.script_type == 'ansible-playbook':
                    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.yml') as playbook_file:
                        playbook_file.write(script.content)
                        playbook_path = playbook_file.name

                    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.ini') as inventory_file:
                        inventory_file.write(f"[{host_details.friendly_name}]\n")
                        inventory_file.write(f"{host_details.hostname} ansible_user={host_details.username}\n")
                        inventory_path = inventory_file.name
                    
                    ansible_command = ['ansible-playbook', '-i', inventory_path, playbook_path]
                    
                    process = subprocess.run(ansible_command, capture_output=True, text=True)
                    output = process.stdout
                    error = process.stderr

                    os.unlink(playbook_path)
                    os.unlink(inventory_path)
                    
                    if output: self.emit_log("output", output)
                    if error and process.returncode != 0:
                        self.emit_log("error", error)
                        return False

                else: # Bash and Python
                    ssh = paramiko.SSHClient()
                    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                    ssh.connect(host_details.hostname, username=host_details.username, timeout=10)
                    
                    exec_command = script.content
                    if script.script_type == 'python-script':
                        exec_command = f"python3 -c {shlex.quote(script.content)}"

                    _, stdout, stderr = ssh.exec_command(exec_command)
                    output = stdout.read().decode()
                    error = stderr.read().decode()
                    ssh.close()

                    if output: self.emit_log("output", output)
                    if error: 
                        self.emit_log("error", error)
                        return False
                
                self.emit_log("success", f"Step '{node['name']}' completed successfully.")
                return True

            except Exception as e:
                self.emit_log("error", f"Failed to execute script: {e}")
                return False
        
        return True

    def find_start_nodes(self):
        all_to_nodes = {edge['to'] for edge in self.edges}
        return [node_id for node_id in self.nodes if node_id not in all_to_nodes]

    def find_next_edges(self, node_id, outcome_type):
        return [edge for edge in self.edges if edge['from'] == node_id and edge['type'] == outcome_type]

    def find_host_for_script(self, script_node_id):
        edge = next((e for e in self.edges if e['to'] == script_node_id), None)
        if not edge: return None
        
        prev_node = self.nodes.get(edge['from'])
        if not prev_node: return None

        if prev_node['type'] == 'host':
            return prev_node
        else:
            return self.find_host_for_script(prev_node['id'])

    def emit_log(self, log_type, message):
        self.socketio.emit('pipeline_log', {'type': log_type, 'message': message})
