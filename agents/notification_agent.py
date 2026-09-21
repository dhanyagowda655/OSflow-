import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, Any
from agents.base import BaseAgent
from config import Config
from extensions import db
from models import Notification, AILog, User

class NotificationAgent(BaseAgent):
    agent_type = "notification"

    def handle(self, step, request, context: Dict[str, Any]) -> Dict[str, Any]:
        recipients = []
        if request and request.employee and request.employee.user:
            recipients.append(request.employee.user)
            
        # Also include admin or relevant role if requested
        admin_user = User.query.filter_by(role='admin').first()
        if admin_user and admin_user not in recipients:
            recipients.append(admin_user)

        step_name = (step.name or 'Notification Alert')
        message = f"FlowOS Workflow Update: Step '{step_name}' completed for Request #{request.id if request else 'N/A'} ({request.title if request else 'Workflow'})."
        
        # 1. Create In-App Notifications (always reliable)
        created_count = 0
        for user in recipients:
            notif = Notification(
                user_id=user.id,
                message=message,
                link=f"/employee/requests" if user.role == 'employee' else "/admin/audit"
            )
            db.session.add(notif)
            created_count += 1

        # 2. Audit Trail in AILog
        log = AILog(
            workflow_id=step.workflow_id,
            agent_type="notification",
            action=step.name,
            prompt=f"Dispatch notification to {len(recipients)} recipients",
            response=message,
            model_used="system_notifier",
            latency_ms=12.5
        )
        db.session.add(log)
        db.session.commit()

        # 3. Optional SMTP Email (Never crashes if not configured)
        email_status = "In-App Notification Sent"
        if Config.MAIL_ENABLED and Config.MAIL_USERNAME and Config.MAIL_APP_PASSWORD:
            try:
                for user in recipients:
                    if user.email:
                        msg = MIMEMultipart()
                        msg['From'] = Config.MAIL_USERNAME
                        msg['To'] = user.email
                        msg['Subject'] = f"[FlowOS] {request.title if request else 'Workflow Notification'}"
                        msg.attach(MIMEText(message, 'plain'))

                        with smtplib.SMTP(Config.MAIL_SERVER, Config.MAIL_PORT, timeout=5) as server:
                            server.starttls()
                            server.login(Config.MAIL_USERNAME, Config.MAIL_APP_PASSWORD)
                            server.send_message(msg)
                email_status = "In-App + Email Delivered"
            except Exception as e:
                email_status = f"In-App Sent (SMTP Skipped: {str(e)[:40]})"

        return {
            "success": True,
            "result_text": f"Notification Agent: Dispatched alerts to {created_count} user(s). [{email_status}]",
            "data": {"notifications_sent": created_count, "email_status": email_status}
        }
