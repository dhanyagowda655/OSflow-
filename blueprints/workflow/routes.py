import json
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from extensions import db, roles_required
from models import Workflow, WorkflowStep, Request
from ai.ai_client import generate_workflow_json
from ai.workflow_generator import workflow_generator_service
from agents.orchestrator import WorkflowOrchestrator, orchestrator

workflow_bp = Blueprint('workflow', __name__, url_prefix='/workflow')

@workflow_bp.route('/builder', methods=['GET', 'POST'])
@login_required
@roles_required('hr', 'admin', 'manager')
def builder():
    preview_dag = None
    preview_levels = None
    preview_text = ""
    ai_model = None

    if request.method == 'POST':
        prompt_text = request.form.get('prompt', '').strip()
        preview_text = prompt_text
        if prompt_text:
            try:
                # Preview DAG without persisting yet
                dag_data = generate_workflow_json(prompt_text)
                preview_dag = dag_data
                tasks = dag_data.get("tasks", [])
                ai_model = dag_data.get("ai_model", "Rule-Based Generator")

                # Validate and get topological levels
                preview_levels = WorkflowOrchestrator.validate_and_sort_dag(tasks)
            except Exception as e:
                flash(f"Error generating workflow preview: {str(e)}", 'danger')

    return render_template(
        'workflow/builder.html',
        preview_dag=preview_dag,
        preview_levels=preview_levels,
        preview_text=preview_text,
        ai_model=ai_model
    )

@workflow_bp.route('/create-and-launch', methods=['POST'])
@login_required
@roles_required('hr', 'admin', 'manager')
def create_and_launch():
    prompt_text = request.form.get('prompt', '').strip()
    if not prompt_text:
        flash('Please provide a workflow description.', 'warning')
        return redirect(url_for('workflow.builder'))

    try:
        workflow, tier, meta = workflow_generator_service.create_workflow_from_text(prompt_text, user_id=current_user.id)
        
        # Execute workflow
        status = orchestrator.run_workflow(workflow.id)
        flash(f"Workflow '{workflow.name}' created ({tier}) and launched! Current status: {status}.", 'success')
        return redirect(url_for('workflow.workflow_detail', id=workflow.id))
    except Exception as e:
        flash(f"Failed to generate workflow: {str(e)}", 'danger')
        return redirect(url_for('workflow.builder'))

@workflow_bp.route('/<int:id>')
@login_required
def workflow_detail(id):
    wf = Workflow.query.get_or_404(id)
    steps = wf.steps
    dag = wf.get_dag()
    return render_template('workflow/detail.html', workflow=wf, steps=steps, dag=dag)

@workflow_bp.route('/<int:id>/resume', methods=['POST'])
@login_required
def resume_workflow(id):
    wf = Workflow.query.get_or_404(id)
    status = orchestrator.run_workflow(wf.id)
    flash(f"Workflow execution resumed. Status: {status}", 'info')
    return redirect(url_for('workflow.workflow_detail', id=wf.id))
