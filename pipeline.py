# pipeline.py
import json
from flask import request
from flask_restx import Namespace, Resource
from flask_login import login_required, current_user
from models import db, Pipeline
from run_pipeline import PipelineRunner

# --- Namespace and Dependency Setup ---
# This namespace will be imported by app.py and added to the main Api object.
pipelines_ns = Namespace('pipelines', description='Pipeline management and execution')

# These will be populated by the setup_pipeline_dependencies function in app.py
# This avoids circular import issues.
_app = None
_socketio = None

def setup_pipeline_dependencies(app, socketio):
    """
    Sets up dependencies for the pipeline module.
    This function is called from app.py to provide the app and socketio instances.
    """
    global _app, _socketio
    _app = app
    _socketio = socketio

# --- API Resources for Pipelines ---

@pipelines_ns.route('/')
class PipelineList(Resource):
    """Handles listing and creation of pipelines."""
    
    @login_required
    def get(self):
        """List all pipelines for the current user's group."""
        # Filter pipelines by the user's group for security and relevance.
        pipelines = Pipeline.query.filter_by(group_id=current_user.group_id).order_by(Pipeline.name).all()
        return [{'id': p.id, 'name': p.name} for p in pipelines]

    @login_required
    def post(self):
        """Create a new pipeline."""
        data = request.json
        if not data.get('name'):
            return {'status': 'error', 'message': 'Pipeline name is required.'}, 400
        
        # Create a new pipeline instance, ensuring it's associated with the current user's group.
        new_pipeline = Pipeline(
            name=data['name'],
            nodes=json.dumps(data.get('nodes', [])),
            edges=json.dumps(data.get('edges', [])),
            group_id=current_user.group_id
        )
        db.session.add(new_pipeline)
        db.session.commit()
        return {'status': 'success', 'message': 'Pipeline saved successfully!', 'id': new_pipeline.id}, 201

@pipelines_ns.route('/<int:pipeline_id>')
class PipelineResource(Resource):
    """Handles operations on a single pipeline (get, update, delete)."""

    @login_required
    def get(self, pipeline_id):
        """Retrieve a specific pipeline's details."""
        pipeline = db.session.get(Pipeline, pipeline_id)
        # Security check: Ensure the user can only access pipelines within their own group.
        if not pipeline or pipeline.group_id != current_user.group_id:
            return {'status': 'error', 'message': 'Pipeline not found or access denied.'}, 404

        return {
            'id': pipeline.id,
            'name': pipeline.name,
            'nodes': json.loads(pipeline.nodes),
            'edges': json.loads(pipeline.edges)
        }
    
    @login_required
    def put(self, pipeline_id):
        """Update an existing pipeline."""
        pipeline = db.session.get(Pipeline, pipeline_id)
        if not pipeline or pipeline.group_id != current_user.group_id:
            return {'status': 'error', 'message': 'Pipeline not found or access denied.'}, 404

        data = request.json
        pipeline.name = data.get('name', pipeline.name)
        # Ensure that nodes and edges are stored as JSON strings.
        pipeline.nodes = json.dumps(data.get('nodes', json.loads(pipeline.nodes)))
        pipeline.edges = json.dumps(data.get('edges', json.loads(pipeline.edges)))
        db.session.commit()
        return {'status': 'success', 'message': 'Pipeline updated successfully!'}

    @login_required
    def delete(self, pipeline_id):
        """Delete a pipeline."""
        pipeline = db.session.get(Pipeline, pipeline_id)
        if not pipeline or pipeline.group_id != current_user.group_id:
            return {'status': 'error', 'message': 'Pipeline not found or access denied.'}, 404
        
        db.session.delete(pipeline)
        db.session.commit()
        return {'status': 'success', 'message': 'Pipeline deleted.'}

@pipelines_ns.route('/<int:pipeline_id>/run')
class PipelineRun(Resource):
    """Triggers the execution of a pipeline."""

    @login_required
    def post(self, pipeline_id):
        """Start a pipeline run (can be a dry run or a full execution)."""
        pipeline = db.session.get(Pipeline, pipeline_id)
        if not pipeline or pipeline.group_id != current_user.group_id:
            return {'status': 'error', 'message': 'Pipeline not found or access denied.'}, 404

        data = request.json
        dry_run = data.get('dry_run', False)
        
        # Instantiate the runner with the required dependencies.
        runner = PipelineRunner(pipeline_id, _app, _socketio, dry_run)
        # Use socketio to run the pipeline in a background thread to avoid blocking the request.
        _socketio.start_background_task(runner.run)
        
        return {'status': 'success', 'message': 'Pipeline execution started.'}
