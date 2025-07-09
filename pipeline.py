# pipeline.py
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from models import db, Pipeline, SavedScript, SSHHost # Import from models.py
from run_pipeline import PipelineRunner
import json

# --- Blueprint Setup ---
pipeline_bp = Blueprint('pipeline_bp', __name__)
# The app and socketio instances will be attached to this blueprint by app.py

# --- API Routes for Pipelines ---
@pipeline_bp.route('/api/pipelines', methods=['GET', 'POST'])
@login_required
def handle_pipelines():
    if request.method == 'POST':
        data = request.json
        if not data.get('name'):
            return jsonify({'status': 'error', 'message': 'Pipeline name is required.'}), 400
        
        # Correctly associate the new pipeline with the user's group
        new_pipeline = Pipeline(
            name=data['name'],
            nodes=json.dumps(data.get('nodes', [])),
            edges=json.dumps(data.get('edges', [])),
            group_id=current_user.group_id
        )
        db.session.add(new_pipeline)
        db.session.commit()
        return jsonify({'status': 'success', 'message': 'Pipeline saved successfully!', 'id': new_pipeline.id}), 201
    
    # Filter pipelines by the user's group
    pipelines = Pipeline.query.filter_by(group_id=current_user.group_id).order_by(Pipeline.name).all()
    return jsonify([{'id': p.id, 'name': p.name} for p in pipelines])

@pipeline_bp.route('/api/pipelines/<int:pipeline_id>', methods=['GET', 'PUT', 'DELETE'])
@login_required
def handle_pipeline(pipeline_id):
    pipeline = db.session.get(Pipeline, pipeline_id)
    # Security check: ensure the user can only access pipelines in their own group
    if not pipeline or pipeline.group_id != current_user.group_id:
        return jsonify({'status': 'error', 'message': 'Pipeline not found or access denied.'}), 404

    if request.method == 'GET':
        return jsonify({
            'id': pipeline.id,
            'name': pipeline.name,
            'nodes': json.loads(pipeline.nodes),
            'edges': json.loads(pipeline.edges)
        })
    
    if request.method == 'PUT':
        data = request.json
        pipeline.name = data.get('name', pipeline.name)
        pipeline.nodes = json.dumps(data.get('nodes', json.loads(pipeline.nodes)))
        pipeline.edges = json.dumps(data.get('edges', json.loads(pipeline.edges)))
        db.session.commit()
        return jsonify({'status': 'success', 'message': 'Pipeline updated successfully!'})

    if request.method == 'DELETE':
        db.session.delete(pipeline)
        db.session.commit()
        return jsonify({'status': 'success', 'message': 'Pipeline deleted.'})

@pipeline_bp.route('/api/pipelines/<int:pipeline_id>/run', methods=['POST'])
@login_required
def run_pipeline_route(pipeline_id):
    """Triggers a pipeline run."""
    pipeline = db.session.get(Pipeline, pipeline_id)
    if not pipeline or pipeline.group_id != current_user.group_id:
        return jsonify({'status': 'error', 'message': 'Pipeline not found or access denied.'}), 404

    data = request.json
    dry_run = data.get('dry_run', False)
    
    # Run the pipeline in a background thread
    runner = PipelineRunner(pipeline_id, pipeline_bp.app, pipeline_bp.socketio, dry_run)
    pipeline_bp.socketio.start_background_task(runner.run)
    
    return jsonify({'status': 'success', 'message': 'Pipeline execution started.'})
