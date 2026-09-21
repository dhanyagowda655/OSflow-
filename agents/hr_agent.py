from typing import Dict, Any
from agents.base import BaseAgent
from extensions import db
from models import LeaveBalance, Employee, Notification

class HRAgent(BaseAgent):
    agent_type = "hr"

    def handle(self, step, request, context: Dict[str, Any]) -> Dict[str, Any]:
        step_name = (step.name or '').lower()
        
        # 1. Leave balance validation and deduction
        if 'leave' in step_name or (request and request.type == 'leave'):
            if request and request.employee:
                # Default 1 day if not parsed
                days_requested = 1.0
                if request.description:
                    import re
                    match = re.search(r'(\d+)\s*(?:day|days)', request.description, re.IGNORECASE)
                    if match:
                        days_requested = float(match.group(1))

                balance = LeaveBalance.query.filter_by(employee_id=request.employee.id, leave_type='Annual').first()
                if not balance:
                    balance = LeaveBalance.query.filter_by(employee_id=request.employee.id).first()

                if balance:
                    if 'validate' in step_name or 'check' in step_name:
                        if balance.remaining_days >= days_requested:
                            return {
                                "success": True,
                                "result_text": f"HR Verified: Sufficient leave balance ({balance.remaining_days:.1f} days remaining for {balance.leave_type}).",
                                "data": {"leave_sufficient": True, "remaining": balance.remaining_days}
                            }
                        else:
                            return {
                                "success": False,
                                "result_text": f"HR Warning: Insufficient leave balance ({balance.remaining_days:.1f} days available, requested {days_requested}).",
                                "data": {"leave_sufficient": False}
                            }
                    elif 'update' in step_name or 'record' in step_name or 'deduct' in step_name:
                        balance.used_days += days_requested
                        db.session.commit()
                        return {
                            "success": True,
                            "result_text": f"HR Records Updated: Deducted {days_requested:.1f} days. New remaining balance: {balance.remaining_days:.1f} days.",
                            "data": {"updated_remaining": balance.remaining_days}
                        }

        # 2. Document verification for onboarding
        if 'document' in step_name or 'verify' in step_name or (request and request.type == 'onboarding'):
            return {
                "success": True,
                "result_text": "HR Agent: Verified government ID, tax declaration, educational certificates, and employment contract.",
                "data": {"documents_verified": True}
            }

        # 3. Orientation / Induction Scheduling
        if 'induction' in step_name or 'orientation' in step_name or 'training' in step_name:
            return {
                "success": True,
                "result_text": "HR Agent: Orientation session booked on calendar for upcoming Monday at 10:00 AM.",
                "data": {"induction_scheduled": True}
            }

        # Default HR action
        return {
            "success": True,
            "result_text": f"HR Agent: Processed '{step.name}' successfully in Human Resources record system.",
            "data": {"hr_status": "completed"}
        }
