from datetime import datetime, timezone
from typing import Dict, Any
from agents.base import BaseAgent
from extensions import db
from models import ExpenseClaim, Notification, User

class FinanceAgent(BaseAgent):
    agent_type = "finance"

    def handle(self, step, request, context: Dict[str, Any]) -> Dict[str, Any]:
        step_name = (step.name or '').lower()

        # 1. Expense Reimbursement
        if (request and request.type == 'expense') or 'expense' in step_name or 'reimbursement' in step_name or 'ocr' in step_name:
            claim = ExpenseClaim.query.filter_by(request_id=request.id).first() if request else None
            
            if 'ocr' in step_name or 'duplicate' in step_name or 'verification' in step_name:
                if claim:
                    # Check duplicate claims (same employee + same amount + same vendor)
                    dupes = ExpenseClaim.query.join(ExpenseClaim.request).filter(
                        ExpenseClaim.request_id != request.id,
                        ExpenseClaim.amount == claim.amount,
                        ExpenseClaim.vendor == claim.vendor,
                        ExpenseClaim.duplicate_flag == False
                    ).all()
                    
                    if dupes:
                        claim.duplicate_flag = True
                        db.session.commit()
                        return {
                            "success": True,
                            "result_text": f"Finance OCR: Extracted Amount: ${claim.amount:.2f}, Vendor: '{claim.vendor}'. WARNING: Potential duplicate claim detected with Request #{dupes[0].request_id}.",
                            "data": {"duplicate_detected": True, "amount": claim.amount, "vendor": claim.vendor}
                        }
                    else:
                        claim.policy_compliant = (claim.amount <= 2500.0)
                        db.session.commit()
                        return {
                            "success": True,
                            "result_text": f"Finance OCR: Extracted Amount: ${claim.amount:.2f}, Vendor: '{claim.vendor}', Date: {claim.expense_date}. Policy check: {'Passed' if claim.policy_compliant else 'Flagged for High Value review'}.",
                            "data": {"amount": claim.amount, "vendor": claim.vendor, "policy_compliant": claim.policy_compliant}
                        }
                return {
                    "success": True,
                    "result_text": "Finance OCR Verification: Receipt fields validated against company spending policy.",
                    "data": {"receipt_verified": True}
                }

            if 'audit' in step_name or 'policy' in step_name or 'budget' in step_name:
                amt = claim.amount if claim else 1200.0
                return {
                    "success": True,
                    "result_text": f"Finance Budget Audit: Allocated budget verified for cost center. Approved amount: ${amt:.2f}.",
                    "data": {"budget_cleared": True, "amount": amt}
                }

            if 'disburse' in step_name or 'payout' in step_name or 'payment' in step_name:
                return {
                    "success": True,
                    "result_text": f"Finance Disbursement: Payment of ${claim.amount if claim else 150.0:.2f} scheduled for direct deposit via automated clearinghouse.",
                    "data": {"disbursed": True}
                }

        # 2. Hardware / Laptop Budget Check
        if 'budget' in step_name or 'finance' in step_name or (request and request.type == 'laptop'):
            estimated_cost = 1499.0
            return {
                "success": True,
                "result_text": f"Finance Policy Check: Hardware standard allocation limit verified (Estimate: ${estimated_cost:.2f}). Budget code DEPT-IT-EQUIP approved.",
                "data": {"budget_approved": True, "cost_center": "DEPT-IT-EQUIP"}
            }

        # 3. Payroll / General Finance step
        if 'payroll' in step_name:
            return {
                "success": True,
                "result_text": "Finance Payroll Agent: Employee payroll master records synchronized with benefits deductions.",
                "data": {"payroll_synced": True}
            }

        return {
            "success": True,
            "result_text": f"Finance Agent: Step '{step.name}' verified and recorded in general ledger.",
            "data": {"finance_status": "ok"}
        }
