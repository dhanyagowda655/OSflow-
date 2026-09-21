import uuid
from datetime import datetime, timezone
from typing import Dict, Any
from agents.base import BaseAgent
from extensions import db
from models import Asset

class ProcurementAgent(BaseAgent):
    agent_type = "procurement"

    def handle(self, step, request, context: Dict[str, Any]) -> Dict[str, Any]:
        step_name = (step.name or '').lower()
        po_number = f"PO-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"

        # 1. Purchase Order / Equipment Procurement
        if any(k in step_name for k in ['order', 'purchase', 'procurement', 'vendor', 'fulfill', 'equipment', 'laptop']):
            # Look for available in_stock asset or create a new inventory batch entry
            available_asset = Asset.query.filter_by(status='in_stock', type='Laptop').first()
            if not available_asset:
                # Provision new inventory stock
                available_asset = Asset(
                    type='Laptop',
                    model_name='MacBook Pro 14" M3' if 'mac' in (request.description if request else '').lower() else 'Dell XPS 15 Enterprise',
                    serial_number=f"SN-{uuid.uuid4().hex[:8].upper()}",
                    status='in_stock'
                )
                db.session.add(available_asset)
                db.session.commit()

            return {
                "success": True,
                "result_text": f"Procurement Agent: Created Purchase Order {po_number}. Allocated Asset [{available_asset.model_name}, Serial: {available_asset.serial_number}] from certified vendor inventory.",
                "data": {
                    "po_number": po_number,
                    "asset_id": available_asset.id,
                    "serial_number": available_asset.serial_number,
                    "model_name": available_asset.model_name
                }
            }

        return {
            "success": True,
            "result_text": f"Procurement Agent: Step '{step.name}' fulfilled through enterprise supply chain.",
            "data": {"po_number": po_number}
        }
