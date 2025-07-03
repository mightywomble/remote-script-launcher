# git_scripts.py
from flask import Blueprint, request, jsonify
from github import Github, UnknownObjectException
import json
import os

# --- Blueprint Setup ---
git_bp = Blueprint('git_bp', __name__)

# --- Helper Functions ---
def _get_github_instance(config):
    """Initializes and returns a PyGithub instance."""
    pat = config.get('GITHUB_PAT')
    if not pat:
        raise Exception("GitHub Personal Access Token not configured.")
    return Github(pat)

def _get_repo(g, config):
    """Gets the repository object."""
    repo_name = config.get('GITHUB_REPO')
    if not repo_name:
        raise Exception("GitHub repository not configured.")
    return g.get_repo(repo_name)

# --- API Routes for GitHub Scripts ---

@git_bp.route('/api/github/scripts', methods=['GET'])
def get_github_scripts():
    """Fetches a list of scripts from the configured GitHub repository."""
    config = git_bp.load_config()
    
    # Gracefully handle missing configuration
    if not config.get('GITHUB_PAT') or not config.get('GITHUB_REPO'):
        # Return an empty list if GitHub is not configured, preventing a server crash.
        return jsonify([])

    try:
        g = _get_github_instance(config)
        repo = _get_repo(g, config)
        
        # Assumes scripts are in a '/scripts' directory in the repo
        contents = repo.get_contents("scripts")
        scripts = []
        for content_file in contents:
            if content_file.type == 'file':
                scripts.append({
                    'name': content_file.name,
                    'path': content_file.path,
                    'sha': content_file.sha
                })
        return jsonify(scripts)
    except UnknownObjectException:
        # Handle case where the '/scripts' directory doesn't exist
        return jsonify([])
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@git_bp.route('/api/github/script-content', methods=['GET'])
def get_script_content():
    """Fetches the content of a single script from GitHub."""
    config = git_bp.load_config()
    path = request.args.get('path')
    if not path:
        return jsonify({'status': 'error', 'message': 'Path parameter is required.'}), 400
    try:
        g = _get_github_instance(config)
        repo = _get_repo(g, config)
        file_content = repo.get_contents(path)
        return jsonify({'content': file_content.decoded_content.decode('utf-8')})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@git_bp.route('/api/github/push-script', methods=['POST'])
def push_script_to_github():
    """Pushes a new or updated script to the dev branch of the repo."""
    config = git_bp.load_config()
    data = request.json
    
    filename = data.get('filename')
    content = data.get('content')
    commit_message = data.get('commit_message')
    dev_branch = config.get('GITHUB_DEV_BRANCH', 'dev')

    if not all([filename, content, commit_message]):
        return jsonify({'status': 'error', 'message': 'Filename, content, and commit message are required.'}), 400

    try:
        g = _get_github_instance(config)
        repo = _get_repo(g, config)
        
        script_path = f"scripts/{filename}"
        
        try:
            repo.get_branch(dev_branch)
        except UnknownObjectException:
            main_branch = repo.get_branch(repo.default_branch)
            repo.create_git_ref(ref=f'refs/heads/{dev_branch}', sha=main_branch.commit.sha)

        try:
            file = repo.get_contents(script_path, ref=dev_branch)
            repo.update_file(file.path, commit_message, content, file.sha, branch=dev_branch)
            message = f"Script '{filename}' updated successfully in '{dev_branch}' branch."
        except UnknownObjectException:
            repo.create_file(script_path, commit_message, content, branch=dev_branch)
            message = f"Script '{filename}' created successfully in '{dev_branch}' branch."
            
        return jsonify({'status': 'success', 'message': message})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500
