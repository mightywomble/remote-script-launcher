# scheduler.py
import os
import shlex
import json
import requests
import paramiko
from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask
from flask_sqlalchemy import SQLAlchemy

# This setup mirrors app.py to allow database access from the scheduler script
basedir = os.path.abspath(os.path.dirname(__file__))
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'app.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# --- Database Models (must match app.py) ---
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
CONFIG_FILE = os.path.join(basedir, 'config.json')

def load_config():
    if not os.path.exists(CONFIG_FILE): return {}
    with open(CONFIG_FILE, 'r') as f: return json.load(f)

def get_gemini_analysis(output, api_key):
    """Gets analysis from Gemini API."""
    if not api_key: return "Gemini API key not configured."
    try:
        prompt = f"As an expert DevOps engineer, analyze the following command line output. Provide a concise summary and potential troubleshooting steps in Markdown.\n\nOutput:\n---\n{output}\n---"
        api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent?key={api_key}"
        response = requests.post(api_url, json={"contents": [{"parts": [{"text": prompt}]}]}, headers={'Content-Type': 'application/json'})
        response.raise_for_status()
        return response.json()['candidates'][0]['content']['parts'][0]['text']
    except Exception as e:
        return f"AI analysis failed: {e}"

def send_discord_notification(schedule_name, host_name, script_name, output, error, analysis):
    """Sends a notification to the configured Discord webhook."""
    config = load_config()
    webhook_url = config.get('DISCORD_WEBHOOK_URL')
    if not webhook_url:
        print("Discord webhook URL not configured. Skipping notification.")
        return

    embed = {
        "title": f"Scheduled Task Report: {schedule_name}",
        "description": f"Ran **{script_name}** on **{host_name}**",
        "color": 5814783 if not error else 15158332, # Blue for success, Red for error
        "fields": [
            {"name": "AI Summary", "value": analysis[:1024]}, # Truncate to fit Discord limits
            {"name": "Output", "value": f"```\n{output[:1000]}\n```" if output else "No output."},
        ]
    }
    if error:
        embed["fields"].append({"name": "Error", "value": f"```\n{error[:1000]}\n```"})

    payload = {"embeds": [embed]}
    try:
        requests.post(webhook_url, json=payload)
    except Exception as e:
        print(f"Failed to send Discord notification: {e}")

def run_scheduled_task(schedule_id):
    """The function that is executed by the scheduler for each job."""
    with app.app_context():
        schedule = db.session.get(Schedule, schedule_id)
        if not schedule:
            print(f"Schedule {schedule_id} not found, removing job.")
            scheduler.remove_job(str(schedule_id))
            return

        host, script = schedule.host, schedule.script
        print(f"Running scheduled task '{schedule.name}': script '{script.name}' on host '{host.friendly_name}'")

        exec_command = script.content
        if script.script_type == 'python-script':
            exec_command = f"python3 -c {shlex.quote(script.content)}"

        output, error = "", ""
        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(host.hostname, username=host.username, timeout=10)
            _, stdout, stderr = ssh.exec_command(exec_command)
            output, error = stdout.read().decode(), stderr.read().decode()
            ssh.close()
        except Exception as e:
            error = f"Execution failed: {e}"

        config = load_config()
        api_key = config.get('GEMINI_API_KEY')
        analysis = get_gemini_analysis(output or error, api_key)
        
        send_discord_notification(schedule.name, host.friendly_name, script.name, output, error, analysis)

# --- Scheduler Setup ---
scheduler = BackgroundScheduler(daemon=True)

def load_schedules_from_db():
    """Loads all schedules from the database and adds them to the scheduler."""
    with app.app_context():
        schedules = Schedule.query.all()
        print(f"Loading {len(schedules)} schedules from database...")
        for schedule in schedules:
            job_id = str(schedule.id)
            if not scheduler.get_job(job_id):
                scheduler.add_job(
                    run_scheduled_task,
                    'cron',
                    hour=schedule.hour,
                    minute=schedule.minute,
                    id=job_id,
                    args=[schedule.id]
                )
        print("Scheduler jobs loaded.")

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    load_schedules_from_db()
    scheduler.start()
    print("Scheduler started. Press Ctrl+C to exit.")
    # Keep the script running
    try:
        while True:
            pass
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
