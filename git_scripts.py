# git_scripts.py
from flask import Blueprint, request, jsonify
from github import Github, UnknownObjectException
import json
import os

# --- Blueprint Setup ---
# This blueprint will be registered with the main Flask app.
# The `load_config` function will be attached to this blueprint from app.py
# to avoid circular import issues.
git_bp = Blueprint('git_bp', __name__)

# --- Helper Functions ---
def _get_github_instance(config):
    """Initializes and returns a PyGithub instance using a Personal Access Token."""
    pat = config.get('GITHUB_PAT')
    if not pat:
        raise Exception("GitHub Personal Access Token not configured in settings.")
    return Github(pat)

def _get_repo(g, config):
    """Gets the repository object from the GitHub instance."""
    repo_name = config.get('GITHUB_REPO')
    if not repo_name:
        raise Exception("GitHub repository not configured in settings.")
    return g.get_repo(repo_name)

# --- API Routes for GitHub Integration ---

@git_bp.route('/api/github/scripts', methods=['GET'])
def get_github_scripts():
    """
    Fetches scripts from predefined directories in the GitHub repository.
    """
    config = git_bp.load_config()
    
    # Gracefully handle missing configuration to prevent server errors on page load.
    if not config.get('GITHUB_PAT') or not config.get('GITHUB_REPO'):
        return jsonify([])

    try:
        g = _get_github_instance(config)
        repo = _get_repo(g, config)
        
        # Define the directories to scan for scripts.
        script_dirs = ['bash_scripts', 'python_scripts', 'ansible_playbooks', 'pipelines']
        all_scripts = []

        for directory in script_dirs:
            try:
                contents = repo.get_contents(directory)
                for content_file in contents:
                    if content_file.type == 'file':
                        all_scripts.append({
                            'name': content_file.name,
                            'path': content_file.path,
                            'type': directory, # Store the directory as the type
                            'sha': content_file.sha
                        })
            except UnknownObjectException:
                # This is normal if a directory doesn't exist, so we just skip it.
                print(f"Info: Directory '{directory}' not found in repo, skipping.")
                continue

        return jsonify(all_scripts)
    except Exception as e:
        # Return a proper error response to the client.
        return jsonify({'status': 'error', 'message': str(e)}), 500

@git_bp.route('/api/github/script-content', methods=['GET'])
def get_script_content():
    """Fetches the content of a single script from GitHub using its path."""
    config = git_bp.load_config()
    path = request.args.get('path')
    if not path:
        return jsonify({'status': 'error', 'message': 'Path parameter is required.'}), 400
    try:
        g = _get_github_instance(config)
        repo = _get_repo(g, config)
        file_content = repo.get_contents(path)
        # Decode the content from base64 to a UTF-8 string.
        return jsonify({'content': file_content.decoded_content.decode('utf-8')})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@git_bp.route('/api/github/push-script', methods=['POST'])
def push_script_to_github():
    """Pushes a local script to the correct subdirectory in the dev branch."""
    config = git_bp.load_config()
    data = request.json
    
    filename = data.get('filename')
    content = data.get('content')
    script_type = data.get('type') # e.g., 'python-script'
    commit_message = data.get('commit_message', f"Add/update script: {filename}")
    dev_branch = config.get('GITHUB_DEV_BRANCH', 'dev')

    # Map script type from UI to directory name.
    dir_map = {
        'bash-command': 'bash_scripts',
        'bash-script': 'bash_scripts',
        'python-script': 'python_scripts',
        'ansible-playbook': 'ansible_playbooks'
    }
    target_dir = dir_map.get(script_type)

    if not all([filename, content, target_dir]):
        return jsonify({'status': 'error', 'message': 'Filename, content, and valid script type are required.'}), 400

    try:
        g = _get_github_instance(config)
        repo = _get_repo(g, config)
        script_path = f"{target_dir}/{filename}"
        
        # Ensure dev branch exists.
        try:
            repo.get_branch(dev_branch)
        except UnknownObjectException:
            main_sha = repo.get_branch(repo.default_branch).commit.sha
            repo.create_git_ref(ref=f'refs/heads/{dev_branch}', sha=main_sha)

        # Create or update the file.
        try:
            file = repo.get_contents(script_path, ref=dev_branch)
            repo.update_file(file.path, commit_message, content, file.sha, branch=dev_branch)
            message = f"Script '{filename}' updated in '{dev_branch}' branch."
        except UnknownObjectException:
            repo.create_file(script_path, commit_message, content, branch=dev_branch)
            message = f"Script '{filename}' created in '{dev_branch}' branch."
            
        return jsonify({'status': 'success', 'message': message})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@git_bp.route('/api/github/push-pipeline', methods=['POST'])
def push_pipeline_to_github():
    """Pushes a pipeline YAML file to the dev branch."""
    config = git_bp.load_config()
    data = request.json
    
    pipeline_name = data.get('name')
    yaml_content = data.get('yaml')
    dev_branch = config.get('GITHUB_DEV_BRANCH', 'dev')

    if not all([pipeline_name, yaml_content]):
        return jsonify({'status': 'error', 'message': 'Pipeline name and YAML content are required.'}), 400

    try:
        g = _get_github_instance(config)
        repo = _get_repo(g, config)
        
        filename = f"{pipeline_name.replace(' ', '_').lower()}.yml"
        pipeline_path = f"pipelines/{filename}"
        commit_message = f"Add/update pipeline: {pipeline_name}"

        # Ensure dev branch exists.
        try: repo.get_branch(dev_branch)
        except UnknownObjectException:
            main_sha = repo.get_branch(repo.default_branch).commit.sha
            repo.create_git_ref(ref=f'refs/heads/{dev_branch}', sha=main_sha)

        try:
            file = repo.get_contents(pipeline_path, ref=dev_branch)
            repo.update_file(file.path, commit_message, yaml_content, file.sha, branch=dev_branch)
            message = f"Pipeline '{pipeline_name}' updated in '{dev_branch}' branch."
        except UnknownObjectException:
            repo.create_file(pipeline_path, commit_message, yaml_content, branch=dev_branch)
            message = f"Pipeline '{pipeline_name}' created in '{dev_branch}' branch."
            
        return jsonify({'status': 'success', 'message': message})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500
