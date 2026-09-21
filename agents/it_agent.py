import random
import uuid
from datetime import datetime, timezone
from typing import Dict, Any
from agents.base import BaseAgent
from extensions import db
from models import Asset, User, Employee
from ai.ai_client import classify_ticket

class ITAgent(BaseAgent):
    agent_type = "it"

    # Set by tests or config to simulate transient failures for backoff retry testing
    simulate_transient_failure_rate: float = 0.0

    def handle(self, step, request, context: Dict[str, Any]) -> Dict[str, Any]:
        step_name = (step.name or '').lower()

        # Check for simulated transient network/API fault
        if self.simulate_transient_failure_rate > 0.0:
            if random.random() < self.simulate_transient_failure_rate and (step.retry_count or 0) < 2:
                return {
                    "success": False,
                    "result_text": "IT Agent Network Fault (Simulated): LDAP / ActiveDirectory timeout. Will trigger exponential backoff retry.",
                    "data": {"transient_error": True}
                }

        # 1. Email Account Creation
        if 'email' in step_name or 'account' in step_name or 'active directory' in step_name:
            username = "employee"
            if request and request.employee and request.employee.user:
                cleaned = "".join(c for c in request.employee.user.name.lower() if c.isalnum())
                username = cleaned or "employee"
            email_addr = f"{username}@flowos.enterprise"
            return {
                "success": True,
                "result_text": f"IT Agent: Provisioned Active Directory corporate email '{email_addr}' with SSO & MFA enabled.",
                "data": {"email_provisioned": email_addr, "sso_enabled": True}
            }

        # 2. Laptop Provisioning & Asset Assignment
        if 'laptop' in step_name or 'workstation' in step_name or 'hardware' in step_name:
            target_emp = request.employee if request else None
            # Fetch or assign asset
            asset = None
            if context and "asset_id" in context:
                asset = db.session.get(Asset, context["asset_id"])
            if not asset:
                asset = Asset.query.filter_by(status='in_stock', type='Laptop').first()
            if not asset:
                asset = Asset(
                    type='Laptop',
                    model_name='MacBook Pro 14" M3',
                    serial_number=f"SN-{uuid.uuid4().hex[:8].upper()}",
                    status='in_stock'
                )
                db.session.add(asset)

            if target_emp:
                asset.assigned_to = target_emp.id
                asset.status = 'assigned'
                asset.allocated_at = datetime.now(timezone.utc)
                db.session.commit()

            return {
                "success": True,
                "result_text": f"IT Agent: Configured OS, VPN & security certificates on [{asset.model_name} (S/N: {asset.serial_number})]. Assigned to {target_emp.user.name if target_emp and target_emp.user else 'Employee'}.",
                "data": {"asset_id": asset.id, "serial_number": asset.serial_number, "assigned": True}
            }

        # 3. GitHub & Cloud Permissions Provisioning
        if 'github' in step_name or 'cloud' in step_name or 'access' in step_name:
            return {
                "success": True,
                "result_text": "IT Agent: Granted GitHub Org membership, AWS Developer Role, and Slack team channel invitations.",
                "data": {"github_granted": True, "aws_role": "dev-engineer"}
            }

        # 4. IT Support Ticket Resolution
        if (request and request.type == 'it_ticket') or 'ticket' in step_name or 'investigation' in step_name:
            cat = classify_ticket(request.description if request else step_name)
            # Find an IT engineer user
            it_user = User.query.filter_by(role='it').first()
            return {
                "success": True,
                "result_text": f"IT Support Agent: Classified ticket as [{cat.upper()}]. Assigned to IT Engineer ({it_user.name if it_user else 'IT Desk'}). Automated diagnostics ran and resolved.",
                "data": {"category": cat, "assigned_engineer": it_user.name if it_user else "IT Support"}
            }

        return {
            "success": True,
            "result_text": f"IT Agent: Step '{step.name}' configured and verified in IT Infrastructure management console.",
            "data": {"it_status": "done"}
        }
