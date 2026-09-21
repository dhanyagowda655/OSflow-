from datetime import datetime, timezone
from typing import Dict, Any
from agents.base import BaseAgent
from extensions import db
from models import Approval, User, Employee, Notification

class ManagerAgent(BaseAgent):
    agent_type = "manager"

    def handle(self, step, request, context: Dict[str, Any]) -> Dict[str, Any]:
        if not request:
            return {
                "success": True,
                "result_text": f"Manager Agent: System auto-authorized standalone step '{step.name}'.",
                "data": {"manager_approved": True}
            }

        # Check existing approval record for this step & request
        approval = Approval.query.filter_by(request_id=request.id, step_id=step.id).first()
        if not approval:
            # Also check by request_id
            approval = Approval.query.filter_by(request_id=request.id).first()

        # Find designated approver (Manager of the employee, or first Manager/Admin user)
        approver = None
        if request.employee and request.employee.manager and request.employee.manager.user:
            approver = request.employee.manager.user
        else:
            approver = User.query.filter_by(role='manager').first() or User.query.filter_by(role='admin').first()

        if not approval:
            # Create a pending Approval row for human-in-the-loop interaction
            approval = Approval(
                request_id=request.id,
                approver_id=approver.id if approver else 1,
                step_id=step.id,
                decision='pending',
                comment='Awaiting review by reporting manager'
            )
            db.session.add(approval)
            
            # Send Notification to the manager
            if approver:
                notif = Notification(
                    user_id=approver.id,
                    message=f"Action Required: Pending approval for request #{request.id} ({request.title}) by {request.employee.user.name if request.employee and request.employee.user else 'Employee'}",
                    link=f"/manager/approvals"
                )
                db.session.add(notif)
                
            db.session.commit()

            return {
                "success": False,
                "waiting_human": True,
                "result_text": f"Awaiting Manager Approval (Assigned to {approver.name if approver else 'Manager'}).",
                "data": {"approval_id": approval.id, "approver_id": approver.id if approver else None}
            }

        # If approval exists, check human decision
        if approval.decision == 'approved':
            return {
                "success": True,
                "waiting_human": False,
                "result_text": f"Manager Approved by {approval.approver.name if approval.approver else 'Manager'}: {approval.comment or 'Approved without comments'}",
                "data": {"manager_decision": "approved", "comment": approval.comment}
            }
        elif approval.decision == 'rejected':
            return {
                "success": False,
                "waiting_human": False,
                "result_text": f"Manager Rejected by {approval.approver.name if approval.approver else 'Manager'}: {approval.comment or 'Request denied'}",
                "data": {"manager_decision": "rejected", "comment": approval.comment}
            }
        else:
            # Still pending human click
            return {
                "success": False,
                "waiting_human": True,
                "result_text": f"Awaiting Manager Approval (Action pending in Manager Portal).",
                "data": {"approval_id": approval.id}
            }
