# SSH Web Dashboard & Automation Hub

A powerful, self-hosted web interface and API for managing SSH hosts, executing commands, and automating tasks. This project provides a centralized dashboard to manually run or schedule scripts across multiple servers, with AI-powered assistance for script generation and output analysis, now fully accessible via a RESTful API.

## Summary

This tool is designed for DevOps engineers, system administrators, and developers who need to manage multiple remote Linux servers efficiently. It replaces the need for manual SSH sessions by providing:

1.  A clean, web-based UI to run commands, manage a library of saved scripts, and schedule recurring tasks with notifications.
    
2.  A complete REST API to programmatically manage hosts, scripts, and pipelines.
    

The integration with the Gemini API adds a layer of intelligence, helping users generate complex scripts from natural language and understand command outputs without leaving the application.

## Features

### Web Dashboard

-   **Centralized Host Management**: Add, edit, and delete SSH hosts.
    
-   **Advanced Command & Script Execution**: Run commands or scripts on multiple hosts simultaneously with sudo privileges.
    
-   **AI-Powered Script Suggestion**: Generate Bash, Python, or Ansible scripts from natural language prompts.
    
-   **AI-Powered Output Analysis**: Get concise summaries and troubleshooting tips for command outputs.
    
-   **Visual Pipeline Builder**: Drag-and-drop interface to build complex workflows with live YAML generation.
    
-   **Task Scheduling & Automation**: Schedule scripts to run on a recurring basis with Discord notifications.
    
-   **Secure Configuration**: A settings panel to securely store your Gemini API Key and Discord Webhook URL.
    

### REST API

-   **Full CRUD Operations**: Programmatically manage hosts, scripts, and pipelines (Create, Read, Update, Delete).
    
-   **Remote Execution Endpoints**: Trigger script and pipeline runs via API calls.
    
-   **Interactive Documentation**: Access to a Swagger UI (`/docs`) and ReDoc (`/redoc`) for easy testing and integration.
    
-   **Secure Access**: Protected by a bearer token authentication scheme.
    

## Tech Stack

-   **Backend**: Flask, Flask-SocketIO, FastAPI (Python)
    
-   **Scheduling**: APScheduler
    
-   **SSH Operations**: Paramiko
    
-   **Database**: Flask-SQLAlchemy (with SQLite as the default database)
    
-   **Frontend**: Vanilla JavaScript, HTML5, CSS3, Leader-Line-New, js-yaml
    
-   **Icons**: Font Awesome
    

## Setup and Installation

Follow these steps to get the application and API running locally.

### Prerequisites:

-   An Ubuntu/Debian-based system (or similar Linux distribution).
    
-   Python 3.6+
    
-   A configured SSH key pair on the machine running the application.
    

### Step 1: Install System Dependencies (for Ubuntu/Debian)

```
sudo apt update && sudo apt install python3-pip python3-venv -y

```

### Step 2: Clone the Repository

```
git clone <your-repository-url>
cd <repository-folder>

```

### Step 3: Create and Activate a Virtual Environment

```
# Create the virtual environment
python3 -m venv venv

# Activate it
source venv/bin/activate

```

For Windows, the command is `.\venv\Scripts\activate`

### Step 4: Install Python Packages

With the virtual environment active, install all the required Python libraries for both the web app and the API.

```
pip install Flask Flask-SQLAlchemy Paramiko requests APScheduler Flask-SocketIO "fastapi[all]" uvicorn SQLAlchemy

```

## Running the Application

This project now has three components that can be run.

### 1. The Web Server (Flask App)

This process runs the main web dashboard.

```
python3 app.py

```

The web UI will be accessible at: `http://<your ip>:5012`

### 2. The API Server (FastAPI App)

This process runs the REST API.

```
python api.py

```

The API will be accessible at: `http://<your ip>:8000`.

-   **Interactive Docs (Swagger)**: [http://<your ip>:8000/docs](https://www.google.com/search?q=http://<your ip>:8000/docs "null")
    
-   **Alternative Docs (ReDoc)**: [http://<your ip>:8000/redoc](https://www.google.com/search?q=http://<your ip>:8000/redoc "null")
    

### 3. The Scheduler

This process runs in the background to execute your scheduled tasks.

```
python3 scheduler.py

```

**Note**: The scheduler must be restarted to activate new or remove deleted schedules.

## How to Use

### Web Dashboard

1.  **Initial Setup**: Open the web interface and click the settings icon (). Enter your Gemini API Key and Discord Webhook URL.
    
2.  **Add a Host**: Click the `+` icon in the "SSH Hosts" pane to add your first server.
    
3.  **Run a Command**: Select a host, then click `Run` or `Run as Sudo`.
    

### API

1.  **Set Security Token**: Before making requests, set the `API_SECRET_TOKEN` environment variable.
    
    ```
    export API_SECRET_TOKEN="your_secret_token"
    
    ```
    
2.  **Authorize**: In the `/docs` interface, click the "Authorize" button and enter `your_secret_token` to authenticate your requests.
    
3.  **Interact**: Use the interactive UI to test endpoints for adding hosts, running scripts, and managing pipelines.
    

## Security Considerations

-   **SSH Authentication**: This application is built with the assumption that you are using SSH key-based authentication. The user running the application must have their SSH keys configured to connect to the target hosts without a password.
    
-   **API Token**: The API is protected by a simple bearer token. Ensure you set a strong, secret token for `API_SECRET_TOKEN` in a production environment. Do not expose this token publicly.
    

## Running as a Systemd Service (Production / Optional)

For production environments, it is recommended to run the applications as `systemd` services. This ensures they start automatically on boot and are restarted if they crash.

### Service File Templates

You will need to create three separate service files in `/etc/systemd/system/`.

**1. Web App Service (`remote-app.service`)**

```
[Unit]
Description=Remote Script Launcher Web App
After=network.target

[Service]
User=<username>
Group=<username>
WorkingDirectory=/home/<username>/code/remote-script-launcher
ExecStart=/home/<username>/code/remote-script-launcher/venv/bin/python app.py
Restart=always

[Install]
WantedBy=multi-user.target

```

**2. API Service (`remote-api.service`)**

```
[Unit]
Description=Remote Script Launcher API
After=network.target

[Service]
User=<username>
Group=<username>
WorkingDirectory=/home/<username>/code/remote-script-launcher
ExecStart=/home/<username>/code/remote-script-launcher/venv/bin/python api.py
Restart=always

[Install]
WantedBy=multi-user.target

```

**3. Scheduler Service (`remote-scheduler.service`)**

```
[Unit]
Description=Remote Script Launcher Scheduler
After=network.target

[Service]
User=<username>
Group=<username>
WorkingDirectory=/home/<username>/code/remote-script-launcher
ExecStart=/home/<username>/code/remote-script-launcher/venv/bin/python scheduler.py
Restart=always

[Install]
WantedBy=multi-user.target

```

### Installation & Usage

1.  **Create the Service Files**: Use a text editor like `nano` to create the files.
    
    ```
    sudo nano /etc/systemd/system/remote-app.service
    sudo nano /etc/systemd/system/remote-api.service
    sudo nano /etc/systemd/system/remote-scheduler.service
    
    ```
    
    Paste the corresponding content into each file, then save and exit.
    
2.  **Reload the systemd Daemon**: This makes `systemd` aware of your new services.
    
    ```
    sudo systemctl daemon-reload
    
    ```
    
3.  **Start the Services**:
    
    ```
    sudo systemctl start remote-app.service
    sudo systemctl start remote-api.service
    sudo systemctl start remote-scheduler.service
    
    ```
    
4.  **Enable Services to Start on Boot**:
    
    ```
    sudo systemctl enable remote-app.service
    sudo systemctl enable remote-api.service
    sudo systemctl enable remote-scheduler.service
    
    ```
    
5.  **Check Status and Logs**: You can check the status or view logs for any service.
    
    ```
    # Check status
    sudo systemctl status remote-api.service
    
    # View live logs
    journalctl -u remote-api.service -f
    
    ```