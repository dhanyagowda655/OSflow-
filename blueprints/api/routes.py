from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from extensions import db
from models import Workflow, WorkflowStep, Notification, Request

api_bp = Blueprint('api', __name__, url_prefix='/api')

@api_bp.route('/workflow/<int:id>/status')
@login_required
def workflow_status(id):
    wf = Workflow.query.get(id)
    if not wf:
        return jsonify({'error': 'Workflow not found'}), 404

    steps_data = [s.to_dict() for s in wf.steps]
    total_steps = len(steps_data)
    done_steps = sum(1 for s in steps_data if s['status'] in ('done', 'skipped'))
    progress_pct = int((done_steps / total_steps) * 100) if total_steps > 0 else 0

    return jsonify({
        'workflow_id': wf.id,
        'name': wf.name,
        'status': wf.status,
        'progress_pct': progress_pct,
        'total_steps': total_steps,
        'done_steps': done_steps,
        'steps': steps_data
    })

@api_bp.route('/notifications')
@login_required
def get_notifications():
    notifs = Notification.query.filter_by(user_id=current_user.id).order_by(Notification.created_at.desc()).limit(15).all()
    unread_count = Notification.query.filter_by(user_id=current_user.id, read_flag=False).count()
    return jsonify({
        'unread_count': unread_count,
        'notifications': [n.to_dict() for n in notifs]
    })

@api_bp.route('/notifications/mark-read', methods=['POST'])
@login_required
def mark_notifications_read():
    notifs = Notification.query.filter_by(user_id=current_user.id, read_flag=False).all()
    for n in notifs:
        n.read_flag = True
    db.session.commit()
    return jsonify({'success': True, 'marked_count': len(notifs)})
