# SSH Web Dashboard & Automation Hub

A powerful, self-hosted web interface for managing SSH hosts, executing commands, and automating complex workflows. This Flask application provides a centralized, multi-user dashboard to manually run or schedule scripts across multiple servers, with AI-powered assistance for script generation and output analysis.

## Summary

This tool is designed for DevOps engineers, system administrators, and developers who need to manage multiple remote Linux servers efficiently. It replaces the need for manual SSH sessions by providing a clean, web-based UI to run commands, manage a library of version-controlled scripts, and build, run, and schedule complex automation pipelines. The integration with the Gemini API adds a layer of intelligence, helping users generate complex scripts from natural language and understand command outputs without leaving the application.

## Key Features

-   **User Authentication & Group Permissions**:
    
    -   Secure login system with password hashing.
        
    -   A default `admin` user is created on first run.
        
    -   Create and manage users and groups from a dedicated UI page.
        
    -   All resources (hosts, scripts, pipelines) are scoped to groups, ensuring teams only see their own assets.
        
-   **Centralized Host Management**:
    
    -   Add, edit, delete, and test connectivity to all your SSH hosts from a single, clean UI.
        
    -   Visually manage all your servers from a single pane.
        
-   **Advanced Command & Script Execution**:
    
    -   A central editor for writing and running commands.
        
    -   **Run as Sudo**: Execute commands with elevated privileges.
        
    -   Select multiple hosts to run commands or scripts on simultaneously.
        
    -   View real-time results and error outputs from each host.
        
-   **AI-Powered Assistance**:
    
    -   **Script Suggester**: Describe a task in natural language and get functional code snippets in multiple languages.
        
    -   **Output Analyzer**: Get a clear, AI-generated summary and troubleshooting tips for any command output.
        
-   **Visual Pipeline Builder**:
    
    -   A drag-and-drop interface to build complex automation workflows.
        
    -   Visually connect hosts, scripts, AI actions, and notifications with success/failure paths.
        
    -   **Live YAML Generation**: See a GitHub Actions-style YAML representation of your pipeline as you build it.
        
    -   **Live Run/Dry Run**: Execute pipelines and see the output for each step in real-time, complete with progress bars.
        
-   **Version-Controlled Script Library**:
    
    -   **Local & GitHub Sources**: Manage scripts stored locally in the app's database or pull them directly from a connected GitHub repository.
        
    -   **Push to GitHub**: Push local scripts and pipelines to a development branch in your repository with a commit message, right from the UI.
        
    -   **Directory-Based Organization**: The GitHub integration scans for scripts in predefined folders (`bash_scripts`, `python_scripts`, etc.) for better organization.
        
-   **Automation & Alerting**:
    
    -   **Scheduling**: Schedule any saved script to run on a specific host at a recurring time.
        
    -   **Notifications**: Automatically sends reports to Discord and/or by email after a scheduled task runs.
        
    -   **Zabbix Integration**: A dedicated, secure API endpoint allows Zabbix to trigger remediation scripts automatically in response to alerts.
        
-   **Secure Configuration**:
    
    -   A collapsible settings panel to securely store your Gemini API Key, Discord Webhook URL, SMTP credentials, and GitHub details. Keys and passwords are never exposed in the browser.
        

## Tech Stack

-   **Backend**: Flask, Flask-Login, Flask-SocketIO (Python)
    
-   **Scheduling**: APScheduler
    
-   **Configuration Management**: Ansible
    
-   **SSH Operations**: Paramiko
    
-   **API Calls**: Requests
    
-   **Database**: Flask-SQLAlchemy (with SQLite as the default database)
    
-   **Frontend**: Vanilla JavaScript, HTML5, CSS3, Leader-Line-New, js-yaml
    
-   **Icons**: Font Awesome
    

## Project Structure

```
.
├── static/
│   ├── style.css
│   ├── app.js
│   ├── pipeline.js
│   └── users.js
├── templates/
│   ├── index.html
│   ├── login.html
│   ├── pipeline.html
│   └── users.html
├── app.py
├── auth.py
├── scheduler.py
├── pipeline.py
├── git_scripts.py
├── run_pipeline.py
├── models.py
├── config.json         # (auto-generated)
└── app.db              # (auto-generated)

```

## Setup and Installation

Follow these steps to get the application running locally.

**Prerequisites**:

-   An Ubuntu/Debian-based system (or similar Linux distribution).
    
-   Python 3.6+
    
-   Ansible must be installed and available in the system's PATH.
    
-   A configured SSH key pair on the machine running the application.
    

**Step 1: Install System Dependencies (for Ubuntu/Debian)**

```
sudo apt update && sudo apt install python3-pip python3-venv ansible -y

```

**Step 2: Clone the Repository**

```
git clone <your-repository-url>
cd <repository-folder>

```

**Step 3: Create and Activate a Virtual Environment**

It's highly recommended to use a virtual environment to manage project-specific dependencies.

```
# Create the virtual environment
python3 -m venv venv

# Activate it
source venv/bin/activate

```

**Step 4: Install Python Packages**

With the virtual environment active, install all the required Python libraries.

```
pip install Flask Flask-Login Flask-SQLAlchemy Flask-SocketIO Paramiko requests APScheduler PyGithub

```

## Running the Application

This application requires **two separate processes** to be running in two different terminals for all features to work.

**Terminal 1: Start the Web Server**

This process runs the main Flask application and serves the web interface. On the first run, it will create the database and a default user.

```
python3 app.py

```

The web UI will be accessible at: **`http://127.0.0.1:5012`**

**Terminal 2: Start the Scheduler**

This process runs in the background to execute your scheduled tasks.

```
python3 scheduler.py

```

_Note: The scheduler must be restarted to activate new or remove deleted schedules._

## Default Login

On the first run, a default user is created with the following credentials:

-   **Username:**  `admin`
    
-   **Password:**  `admin`
    

It is highly recommended to log in, go to the **User Management** page, create a new user with a strong password, and then delete the default admin user.

## Security Considerations

-   **SSH Authentication**: This application is built with the assumption that you are using **SSH** key-based **authentication**. The user running the Flask app must have their SSH keys configured to connect to the target hosts without a password.
    
-   **Sudo Privileges**: The "Run as Sudo" feature assumes the connecting user has **passwordless sudo** configured on the target hosts.
    
-   **Network Exposure**: The application runs on `0.0.0.0` by default, meaning it's accessible from your local network. For production, run it behind a reverse proxy (like Nginx) and implement proper authentication and firewall rules.