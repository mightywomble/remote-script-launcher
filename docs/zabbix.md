
# Zabbix 7.x Integration Guide

This guide provides detailed instructions on how to integrate the SSH Web Dashboard with your Zabbix 7.x monitoring system. This integration allows Zabbix to automatically trigger remediation scripts in your dashboard in response to alerts, turning your monitoring setup into a proactive, self-healing system.

## How It Works

The integration works by using a Zabbix **webhook**. The process is as follows:

1.  **Zabbix Trigger Fires**: An issue is detected on a monitored host (e.g., "High CPU usage," "Disk space critical").
    
2.  **Zabbix Action Runs**: The trigger firing initiates a pre-configured action.
    
3.  **Action Calls Webhook**: The action makes a secure API call (a webhook) to a special endpoint on the SSH Web Dashboard application. It passes information like the hostname and the name of the script to run.
    
4.  **Dashboard Executes Script**: The application receives the API call, validates it, finds the correct host and remediation script from its database, and runs it on the target server.
    

----------

## Prerequisites

1.  A fully working **SSH Web Dashboard** application with the `/api/zabbix-trigger` endpoint enabled.
    
2.  A running **Zabbix 7.x Server** and **Zabbix Agent** on the hosts you want to manage.
    
3.  Network connectivity from your Zabbix Server to the machine running the SSH Web Dashboard application (e.g., ensure firewalls allow traffic on port 5012).
    
4.  The host names in Zabbix must **exactly match** the "Friendly Name" you have given your hosts in the SSH Web Dashboard.
    

----------

## Step 1: Configure the SSH Web Dashboard

First, we need to add a dedicated, secure API key to the application that Zabbix will use to authenticate its requests.

### 1.1. Generate a Secure API Key

Create a strong, random key. You can use a password generator or run the following command on a Linux terminal:

Bash

```
openssl rand -hex 32

```

Copy the generated key. You will use this in the next steps.

### 1.2. Add the API Key to the Application

1.  Open the SSH Web Dashboard in your browser.
    
2.  Click the **Settings** icon () in the top right.
    
3.  We need to add a field for the Zabbix API Key. For now, you can add this key to your `config.json` file manually. Open `config.json` and add a new line:
    
    JSON
    
    ```
    {
        "GEMINI_API_KEY": "your_gemini_key_here",
        "DISCORD_WEBHOOK_URL": "your_discord_url_here",
        "ZABBIX_API_KEY": "paste_your_generated_zabbix_api_key_here"
    }
    
    ```
    
4.  Save the `config.json` file and restart your `app.py` process to load the new key.
    

----------

## Step 2: Configure Zabbix 7.x

Now, we will set up the webhook and action within the Zabbix UI.

### 2.1. Create a Webhook Media Type

1.  In Zabbix, navigate to **Administration > Media types**.
    
2.  Click the **Create media type** button.
    
3.  Fill in the form with the following details:
    
    -   **Name**: `SSH Dashboard Webhook`
        
    -   **Type**: `Webhook`
        
    -   **URL**: `http://<YOUR_FLASK_APP_IP>:5012/api/zabbix-trigger`
        
    -   **HTTP headers**:
        
        -   `Content-Type`: `application/json`
            
        -   `X-API-Key`: `paste_your_generated_zabbix_api_key_here`
            
4.  Click **Add** to save the media type.
    

### 2.2. Create a User and Assign Media

It's best practice to have a dedicated user for sending notifications.

1.  Navigate to **Administration > Users**.
    
2.  Create a new user (e.g., `AutomationUser`) or use an existing one.
    
3.  Go to the **Media** tab for that user.
    
4.  Click **Add** and configure the media:
    
    -   **Type**: `SSH Dashboard Webhook` (the one you just created).
        
    -   **Send to**: `1` (this field is required but not used by our webhook).
        
    -   **Enabled**: Make sure it is checked.
        
5.  Click **Add**.
    

### 2.3. Create a Trigger Action

This is where you define which problem will trigger which script.

1.  Navigate to **Configuration > Actions > Trigger actions**.
    
2.  Click **Create action**.
    
3.  **Action Tab**:
    
    -   **Name**: `Remediate: High CPU Load` (or similar).
        
    -   **Conditions**: Define when this action should run. For example:
        
        -   `Trigger severity` `>=` `High`
            
        -   `Host` `=` `Your Target Server`
            
4.  **Operations Tab**:
    
    -   Click **Add** under "Operations".
        
    -   **Operation**: `Send message`
        
    -   **Send to Users**: Select your `AutomationUser`.
        
    -   **Send only to**: `SSH Dashboard Webhook`
        
    -   **Message**: This is the most important part. Paste the following JSON into the message body:
        
        JSON
        
        ```
        {
            "host_name": "{HOST.NAME}",
            "script_name": "Clear High CPU Load Script"
        }
        
        ```
        
        -   `{HOST.NAME}` is a Zabbix macro that will be replaced with the name of the host that triggered the alert.
            
        -   `"Clear High CPU Load Script"` is the **exact name** of the remediation script you have saved in the SSH Web Dashboard.
            
5.  Click **Add** to save the operation, and then **Add** again to save the action.
    

----------

## Step 3: Test the Integration

1.  Cause the trigger condition on your monitored host (e.g., run a CPU stress test).
    
2.  When the Zabbix trigger fires, the action should execute.
    
3.  Check the Zabbix UI under **Monitoring > Problems** to see the action log. It should show that the webhook was called successfully.
    
4.  Check the terminal where your `app.py` is running. You should see a `POST /api/zabbix-trigger` request logged.
    
5.  Verify that the remediation script actually ran on the target host.
    

You have now successfully integrated Zabbix with your SSH Web Dashboard for automated remediation!