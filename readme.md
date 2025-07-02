
# SSH Web Dashboard

A simple, self-hosted web-based interface for managing and running commands on multiple SSH hosts. This Flask application provides a three-pane dashboard to add, manage, and execute scripts (Bash, Python) across your servers, all from a clean web UI.

## Features

-   **Host Management**:
    
    -   Add SSH hosts with a friendly name, hostname, and username.
        
    -   List all configured hosts in a dedicated pane.
        
    -   Test SSH connectivity to any host with a single click.
        
-   **Command & Script Execution**:
    
    -   A central editor to write Bash or Python scripts.
        
    -   Select multiple hosts to run commands on simultaneously.
        
    -   View real-time results and error outputs from each host.
        
-   **Script Library**:
    
    -   Save frequently used commands and scripts for later use.
        
    -   List, search, and sort saved scripts.
        
    -   (Future) Load saved scripts directly into the editor.
        
-   **Modern UI**:
    
    -   A clean, dark-themed, three-pane layout for efficient workflow.
        
    -   Responsive design for use on different screen sizes.
        
    -   Real-time feedback with loading indicators and toast notifications.
        

## Tech Stack

-   **Backend**: Flask (Python)
    
-   **SSH Operations**: Paramiko
    
-   **Database**: Flask-SQLAlchemy (with SQLite as the default database)
    
-   **Frontend**: Vanilla JavaScript, HTML5, CSS3
    
-   **Icons**: Font Awesome
    

## Project Structure

```
.
├── static/
│   ├── style.css       # Main stylesheet
│   └── app.js          # Frontend JavaScript logic
├── templates/
│   └── index.html      # Main HTML template
├── app.py              # Core Flask application logic
└── app.db              # SQLite database file (auto-generated)

```

## Setup and Installation

Follow these steps to get the application running locally.

**Prerequisites**:

-   An Ubuntu/Debian-based system (or similar Linux distribution).
    
-   Python 3.6+
    
-   A configured SSH key pair on the machine running the application. The application uses key-based authentication by default.
    

**Step 1: Install System Dependencies (for Ubuntu/Debian)**

Before setting up the Python environment, ensure you have the necessary system packages installed. `python3-venv` is crucial for creating isolated Python environments.

```
sudo apt update && sudo apt install python3-pip python3-venv -y

```

**Step 2: Clone the Repository**

```
git clone <your-repository-url>
cd ssh-web-interface

```

**Step 3: Create and Activate a Virtual Environment**

It's highly recommended to use a virtual environment to manage project-specific dependencies.

```
# Create the virtual environment
python3 -m venv venv

# Activate it
source venv/bin/activate

```

_For Windows, the command is `.\venv\Scripts\activate`_

**Step 4: Install Python Packages**

With the virtual environment active, install the required Python libraries.

```
pip install Flask Flask-SQLAlchemy Paramiko

```

## Running the Application

**1.** Start **the Flask Server** Once the dependencies are installed, run the `app.py` file:

```
python3 app.py

```

The application will start in debug mode and be accessible at: [**http://127.0.0.1:5001**](https://www.google.com/search?q=http://127.0.0.1:5001 "null")

**2. Using the Dashboard**

-   Open the URL in your web browser.
    
-   Click the `+` icon in the "SSH Hosts" pane to add your first server.
    
-   Select one or more hosts using the checkboxes.
    
-   Write a command in the editor, select its type (e.g., Bash), and click "Run on Selected".
    
-   View the output in the "Results" pane.
    

## Security Considerations

-   **SSH Authentication**: This application is built with the assumption that you are using **SSH key-based authentication**. The user running the Flask app must have their SSH keys configured to connect to the target hosts without a password.