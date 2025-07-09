# scheduler.py
import os
import shlex
import json
import requests
import paramiko
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from models import db, SSHHost, SavedScript, Schedule

# This setup mirrors app.py to allow database access
basedir = os.path.abspath(os.path.dirname(__file__))
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'app.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

# --- Helper Functions ---
CONFIG_FILE = os.path.join(basedir, 'config.json')

def load_config():
    if not os.path.exists(CONFIG_FILE): return {}
    with open(CONFIG_FILE, 'r') as f: return json.load(f)

def get_gemini_analysis(output, api_key):
    if not api_key: return "Gemini API key not configured."
    try:
        prompt = f"As an expert DevOps engineer, analyze the following command line output. Provide a concise summary and potential troubleshooting steps in Markdown.\n\nOutput:\n---\n{output}\n---"
        api_url = f"[https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent?key=](https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent?key=){api_key}"
        response = requests.post(api_url, json={"contents": [{"parts": [{"text": prompt}]}]}, headers={'Content-Type': 'application/json'})
        response.raise_for_status()
        return response.json()['candidates'][0]['content']['parts'][0]['text']
    except Exception as e:
        return f"AI analysis failed: {e}"

def send_discord_notification(schedule_name, host_name, script_name, output, error, analysis):
    config = load_config()
    webhook_url = config.get('DISCORD_WEBHOOK_URL')
    if not webhook_url: return
    embed = {"title": f"Scheduled Task Report: {schedule_name}", "description": f"Ran **{script_name}** on **{host_name}**", "color": 5814783 if not error else 15158332, "fields": [{"name": "AI Summary", "value": analysis[:1024]}, {"name": "Output", "value": f"```\n{output[:1000]}\n```" if output else "No output."}]}
    if error: embed["fields"].append({"name": "Error", "value": f"```\n{error[:1000]}\n```"})
    try:
        requests.post(webhook_url, json={"embeds": [embed]})
    except Exception as e:
        print(f"Failed to send Discord notification: {e}")

def send_email_notification(schedule_name, host_name, script_name, output, error, analysis):
    config = load_config()
    smtp_settings = ['EMAIL_TO', 'SMTP_SERVER', 'SMTP_PORT', 'SMTP_USER', 'SMTP_PASSWORD']
    if not all(config.get(key) for key in smtp_settings):
        print("SMTP settings are incomplete. Skipping email notification.")
        return
    try:
        msg = MIMEMultipart()
        msg['From'] = config['SMTP_USER']
        msg['To'] = config['EMAIL_TO']
        msg['Subject'] = f"Pipeline Report: {schedule_name}"
        html_body = f"""<html><body style="font-family: sans-serif; color: #333;"><h2>Pipeline Report: {schedule_name}</h2><p>Ran script <strong>{script_name}</strong> on host <strong>{host_name}</strong>.</p><hr><h3>AI Summary</h3><div style="background-color: #f5f5f5; padding: 10px; border-radius: 5px;">{analysis.replace('`', '<code>').replace('\n', '<br>')}</div><h3>Output</h3><pre style="background-color: #222; color: #eee; padding: 10px; border-radius: 5px;">{output or "No output."}</pre>{f'''<h3>Error</h3><pre style="background-color: #fdd; color: #c00; padding: 10px; border-radius: 5px;">{error}</pre>''' if error else ''}</body></html>"""
        msg.attach(MIMEText(html_body, 'html'))
        server = smtplib.SMTP(config['SMTP_SERVER'], int(config['SMTP_PORT']))
        server.starttls()
        server.login(config['SMTP_USER'], config['SMTP_PASSWORD'])
        server.send_message(msg)
        server.quit()
        print(f"Successfully sent email notification to {config['EMAIL_TO']}")
    except Exception as e:
        print(f"Failed to send email notification: {e}")

def run_scheduled_task(schedule_id):
    with app.app_context():
        schedule = db.session.get(Schedule, schedule_id)
        if not schedule: return
        host, script = schedule.host, schedule.script
        print(f"Running scheduled task '{schedule.name}'")
        exec_command = f"python3 -c {shlex.quote(script.content)}" if script.script_type == 'python-script' else script.content
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
        analysis = get_gemini_analysis(output or error, config.get('GEMINI_API_KEY'))
        send_discord_notification(schedule.name, host.friendly_name, script.name, output, error, analysis)
        send_email_notification(schedule.name, host.friendly_name, script.name, output, error, analysis)

# --- Scheduler Setup ---
scheduler = BackgroundScheduler(daemon=True)

def load_schedules_from_db():
    with app.app_context():
        schedules = Schedule.query.all()
        print(f"Loading {len(schedules)} schedules from database...")
        for schedule in schedules:
            job_id = str(schedule.id)
            if not scheduler.get_job(job_id):
                scheduler.add_job(run_scheduled_task, 'cron', hour=schedule.hour, minute=schedule.minute, id=job_id, args=[schedule.id])
        print("Scheduler jobs loaded.")

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    load_schedules_from_db()
    scheduler.start()
    print("Scheduler started. Press Ctrl+C to exit.")
    try:
        while True:
            pass
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
