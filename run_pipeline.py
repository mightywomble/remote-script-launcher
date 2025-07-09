# run_pipeline.py
import os
import shlex
import json
import paramiko
import subprocess
import tempfile
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import requests
from models import db, Pipeline, SSHHost, SavedScript
from github import Github, UnknownObjectException

class PipelineRunner:
    def __init__(self, pipeline_id, app, socketio, dry_run=False):
        self.pipeline_id = pipeline_id
        self.app = app
        self.socketio = socketio
        self.dry_run = dry_run
        self.pipeline = None
        self.nodes = {}
        self.edges = []
        self.config = {}

    def run(self):
        """Starts the pipeline execution within a Flask application context."""
        with self.app.app_context():
            self.pipeline = db.session.get(Pipeline, self.pipeline_id)
            if not self.pipeline:
                self.emit_log("error", f"Pipeline {self.pipeline_id} not found.")
                return

            self.nodes = {node['id']: node for node in json.loads(self.pipeline.nodes)}
            self.edges = json.loads(self.pipeline.edges)
            self.config = self._load_config()
            
            self.emit_log("info", f"Starting pipeline: '{self.pipeline.name}'")
            if self.dry_run:
                self.emit_log("info", "*** DRY RUN MODE: No commands will be executed on remote hosts. ***")

            start_nodes = self.find_start_nodes()
            if not start_nodes:
                self.emit_log("error", "Pipeline has no starting point (e.g., a Host node).")
                return

            for start_node_id in start_nodes:
                self.execute_from_node(start_node_id, {})

            self.emit_log("info", "Pipeline execution finished.")

    def execute_from_node(self, node_id, context):
        """Recursively executes nodes in the pipeline, passing context between them."""
        node = self.nodes.get(node_id)
        if not node: return

        self.emit_log("info", f"Executing step: {node['name']}")
        
        success, new_context = self.execute_step(node, context)
        
        next_edges = self.find_next_edges(node_id, 'success' if success else 'failure')
        for edge in next_edges:
            self.execute_from_node(edge['to'], new_context)

    def execute_step(self, node, context):
        """Dispatches execution based on node type and updates the context."""
        node_type = node.get('type')
        if node_type == 'host':
            context['current_host_node'] = node
            self.emit_log("success", f"Targeting host: {node['name']}")
            return True, context
        
        if node_type == 'script':
            return self._execute_script(node, context)
        
        if node_type == 'ai-analysis':
            return self._execute_ai_analysis(node, context)

        if node_type in ['discord', 'email']:
            return self._execute_notification(node, context)

        return True, context

    def _execute_script(self, node, context):
        host_node = context.get('current_host_node')
        if not host_node:
            self.emit_log("error", f"No host context found for script: {node['name']}")
            return False, context

        script_content = ""
        script_type = ""

        # Differentiate between local and GitHub scripts
        script_id_str = str(node['scriptId'])
        if script_id_str.startswith('gh-'):
            script_path = node.get('scriptPath')
            if not script_path:
                self.emit_log("error", "GitHub script path not found in node data.")
                return False, context
            try:
                script_content = self._get_github_script_content(script_path)
                if 'ansible' in script_path: script_type = 'ansible-playbook'
                elif script_path.endswith('.py'): script_type = 'python-script'
                else: script_type = 'bash-script'
            except Exception as e:
                self.emit_log("error", f"Failed to fetch GitHub script '{script_path}': {e}")
                return False, context
        else:
            script = db.session.get(SavedScript, int(script_id_str))
            if not script:
                self.emit_log("error", f"Local script '{node['name']}' not found in database.")
                return False, context
            script_content = script.content
            script_type = script.script_type

        if self.dry_run:
            self.emit_log("info", f"[DRY RUN] Would execute script '{node['name']}' on host '{host_node['name']}'.")
            self.emit_log("output", script_content)
            context['last_output'] = f"[DRY RUN] Output of {node['name']}:\n{script_content}"
            return True, context

        try:
            host_details = db.session.get(SSHHost, int(host_node['hostId']))
            output, error = "", ""
            
            if script_type == 'ansible-playbook':
                with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.yml') as playbook_file:
                    playbook_file.write(script_content)
                    playbook_path = playbook_file.name
                with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.ini') as inventory_file:
                    inventory_file.write(f"[{host_details.friendly_name}]\n{host_details.hostname} ansible_user={host_details.username}\n")
                    inventory_path = inventory_file.name
                ansible_command = ['ansible-playbook', '-i', inventory_path, playbook_path]
                process = subprocess.run(ansible_command, capture_output=True, text=True)
                output, error = process.stdout, process.stderr
                os.unlink(playbook_path)
                os.unlink(inventory_path)
                if error and process.returncode != 0:
                    raise Exception(error)
            else:
                ssh = paramiko.SSHClient()
                ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                ssh.connect(host_details.hostname, username=host_details.username, timeout=10)
                exec_command = f"python3 -c {shlex.quote(script_content)}" if script_type == 'python-script' else script_content
                _, stdout, stderr = ssh.exec_command(exec_command)
                output, error = stdout.read().decode(), stderr.read().decode()
                ssh.close()
                if error:
                    raise Exception(error)

            context['last_output'] = output
            self.emit_log("output", output)
            self.emit_log("success", f"Step '{node['name']}' completed successfully.")
            return True, context

        except Exception as e:
            error_message = str(e)
            self.emit_log("error", error_message)
            context['last_output'] = error_message
            return False, context

    def _execute_ai_analysis(self, node, context):
        self.emit_log("info", "Performing AI Analysis...")
        last_output = context.get('last_output', 'No previous output to analyze.')
        
        if self.dry_run:
            analysis = "[DRY RUN] AI analysis would be performed on the previous step's output."
        else:
            analysis = self._get_gemini_analysis(last_output)
        
        context['ai_summary'] = analysis
        self.emit_log("output", analysis)
        self.emit_log("success", "AI Analysis complete.")
        return True, context

    def _execute_notification(self, node, context):
        self.emit_log("info", f"Sending notification via {node['type']}...")
        if self.dry_run:
            self.emit_log("success", f"[DRY RUN] Notification '{node['name']}' would be sent.")
            return True, context
        
        if node['type'] == 'discord':
            self._send_discord_notification(context)
        elif node['type'] == 'email':
            self._send_email_notification(context)
            
        return True, context

    def _get_github_script_content(self, path):
        g = Github(self.config.get('GITHUB_PAT'))
        repo = g.get_repo(self.config.get('GITHUB_REPO'))
        file_content = repo.get_contents(path)
        return file_content.decoded_content.decode('utf-8')

    def _get_gemini_analysis(self, output):
        api_key = self.config.get('GEMINI_API_KEY')
        if not api_key: return "Gemini API key not configured."
        try:
            prompt = f"As an expert DevOps engineer, analyze the following command line output. Provide a concise summary and potential troubleshooting steps in Markdown.\n\nOutput:\n---\n{output}\n---"
            api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent?key={api_key}"
            response = requests.post(api_url, json={"contents": [{"parts": [{"text": prompt}]}]}, headers={'Content-Type': 'application/json'})
            response.raise_for_status()
            return response.json()['candidates'][0]['content']['parts'][0]['text']
        except Exception as e:
            return f"AI analysis failed: {e}"

    def _send_discord_notification(self, context):
        webhook_url = self.config.get('DISCORD_WEBHOOK_URL')
        if not webhook_url: return
        embed = {"title": f"Pipeline Report: {self.pipeline.name}", "description": f"Report from pipeline run.", "fields": []}
        if context.get('ai_summary'):
            embed['fields'].append({"name": "AI Summary", "value": context['ai_summary'][:1024]})
        if context.get('last_output'):
            embed['fields'].append({"name": "Last Step Output", "value": f"```\n{context['last_output'][:1000]}\n```"})
        try:
            requests.post(webhook_url, json={"embeds": [embed]})
            self.emit_log("success", "Discord notification sent.")
        except Exception as e:
            self.emit_log("error", f"Failed to send Discord notification: {e}")

    def _send_email_notification(self, context):
        smtp_settings = ['EMAIL_TO', 'SMTP_SERVER', 'SMTP_PORT', 'SMTP_USER', 'SMTP_PASSWORD']
        if not all(self.config.get(key) for key in smtp_settings):
            self.emit_log("error", "SMTP settings incomplete. Cannot send email.")
            return
        try:
            msg = MIMEMultipart()
            msg['From'] = self.config['SMTP_USER']
            msg['To'] = self.config['EMAIL_TO']
            msg['Subject'] = f"Pipeline Report: {self.pipeline.name}"
            html_body = f"<html><body><h2>Report for {self.pipeline.name}</h2><p>AI Summary: {context.get('ai_summary', 'N/A')}</p><p>Last Output:</p><pre>{context.get('last_output', 'N/A')}</pre></body></html>"
            msg.attach(MIMEText(html_body, 'html'))
            server = smtplib.SMTP(self.config['SMTP_SERVER'], int(self.config['SMTP_PORT']))
            server.starttls()
            server.login(self.config['SMTP_USER'], self.config['SMTP_PASSWORD'])
            server.send_message(msg)
            server.quit()
            self.emit_log("success", f"Email notification sent to {self.config['EMAIL_TO']}")
        except Exception as e:
            self.emit_log("error", f"Failed to send email: {e}")

    def _load_config(self):
        config_path = os.path.join(self.app.root_path, 'config.json')
        if not os.path.exists(config_path): return {}
        with open(config_path, 'r') as f: return json.load(f)

    def find_start_nodes(self):
        all_to_nodes = {edge['to'] for edge in self.edges}
        return [node_id for node_id in self.nodes if node_id not in all_to_nodes]

    def find_next_edges(self, node_id, outcome_type):
        return [edge for edge in self.edges if edge['from'] == node_id and edge['type'] == outcome_type]

    def find_host_for_script(self, script_node_id):
        processed_nodes = set()
        to_process = [script_node_id]
        while to_process:
            current_id = to_process.pop(0)
            if current_id in processed_nodes: continue
            processed_nodes.add(current_id)
            
            incoming_edges = [e for e in self.edges if e['to'] == current_id]
            for edge in incoming_edges:
                prev_node = self.nodes.get(edge['from'])
                if prev_node:
                    if prev_node['type'] == 'host':
                        return prev_node
                    else:
                        to_process.append(prev_node['id'])
        return None

    def emit_log(self, log_type, message):
        self.socketio.emit('pipeline_log', {'type': log_type, 'message': message})
