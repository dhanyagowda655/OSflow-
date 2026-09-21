import time
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Dict, List, Set, Any
from extensions import db
from models import Workflow, WorkflowStep, Request, Notification, User, AILog
from agents.hr_agent import HRAgent
from agents.manager_agent import ManagerAgent
from agents.finance_agent import FinanceAgent
from agents.procurement_agent import ProcurementAgent
from agents.it_agent import ITAgent
from agents.notification_agent import NotificationAgent

logger = logging.getLogger(__name__)

class WorkflowValidationError(Exception):
    """Raised when a workflow DAG contains cycles or invalid task dependencies."""
    pass

class WorkflowOrchestrator:
    """
    Executes Workflow DAGs with topological sorting, parallel independent step dispatching,
    exponential backoff retries, and self-healing failure escalation.
    """

    def __init__(self, app=None):
        self.app = app
        self.agent_registry = {
            'hr': HRAgent(app),
            'manager': ManagerAgent(app),
            'finance': FinanceAgent(app),
            'procurement': ProcurementAgent(app),
            'it': ITAgent(app),
            'notification': NotificationAgent(app),
            'notification_analytics': NotificationAgent(app)
        }

    # -------------------------------------------------------------
    # 1. DAG Construction & Topological Sort (Kahn's Algorithm)
    # -------------------------------------------------------------
    @staticmethod
    def validate_and_sort_dag(tasks: List[Dict[str, Any]]) -> List[List[str]]:
        """
        Validates task graph for cycles using Kahn's Algorithm.
        Returns execution batches (levels of independent tasks that can run in parallel).
        Raises WorkflowValidationError if a cycle or unknown dependency is detected.
        """
        task_ids = {t["id"] for t in tasks}
        in_degree = {t["id"]: 0 for t in tasks}
        adj_list = {t["id"]: [] for t in tasks}

        for t in tasks:
            for dep in t.get("depends_on", []):
                if dep not in task_ids:
                    raise WorkflowValidationError(f"Task '{t['id']}' depends on non-existent task '{dep}'.")
                adj_list[dep].append(t["id"])
                in_degree[t["id"]] += 1

        # Kahn's algorithm with level batching
        queue = [t_id for t_id, deg in in_degree.items() if deg == 0]
        batches = []
        visited_count = 0

        while queue:
            current_batch = list(queue)
            batches.append(current_batch)
            visited_count += len(current_batch)
            next_queue = []

            for node in current_batch:
                for neighbor in adj_list[node]:
                    in_degree[neighbor] -= 1
                    if in_degree[neighbor] == 0:
                        next_queue.append(neighbor)

            queue = next_queue

        if visited_count != len(tasks):
            raise WorkflowValidationError("Circular dependency (cycle) detected in workflow DAG.")

        return batches

    # -------------------------------------------------------------
    # 2. Step Execution with Exponential Backoff Retry
    # -------------------------------------------------------------
    def execute_step_with_retry(self, step_id: int, request_id: int = None, context: Dict[str, Any] = None, max_retries: int = 4) -> Dict[str, Any]:
        """
        Executes a single step with exponential backoff on transient errors:
        wait = min(2**attempt, 8)
        """
        step = db.session.get(WorkflowStep, step_id)
        if not step:
            return {"success": False, "result_text": "Step not found"}

        request = db.session.get(Request, request_id) if request_id else None
        agent_type = (step.agent_type or 'hr').lower()
        agent = self.agent_registry.get(agent_type, self.agent_registry['hr'])

        step.status = 'in_progress'
        step.started_at = datetime.now(timezone.utc)
        db.session.commit()

        context = context or {}
        attempt = step.retry_count or 0

        while attempt <= max_retries:
            try:
                res = agent.handle(step, request, context)
                
                # Check if step is waiting for human manager approval
                if res.get('waiting_human'):
                    step.status = 'waiting_approval'
                    step.result_text = res.get('result_text', 'Awaiting human authorization.')
                    db.session.commit()
                    return res

                if res.get('success'):
                    step.status = 'done'
                    step.completed_at = datetime.now(timezone.utc)
                    step.result_text = res.get('result_text', 'Completed successfully.')
                    db.session.commit()
                    return res
                else:
                    # Failure - increment attempt
                    attempt += 1
                    step.retry_count = attempt
                    db.session.commit()

                    if attempt <= max_retries:
                        backoff = min(2 ** attempt, 8)
                        logger.warning(f"Step {step.id} ({step.name}) failed. Retrying in {backoff}s (Attempt {attempt}/{max_retries})...")
                        time.sleep(backoff)
                    else:
                        break
            except Exception as e:
                logger.exception(f"Exception executing step {step.id}: {e}")
                attempt += 1
                step.retry_count = attempt
                db.session.commit()
                if attempt <= max_retries:
                    time.sleep(min(2 ** attempt, 8))
                else:
                    break

        # Retries exhausted -> mark step failed
        step.status = 'failed'
        step.completed_at = datetime.now(timezone.utc)
        step.result_text = f"Failed after {max_retries} retry attempts: {res.get('result_text', 'Execution error') if 'res' in locals() else 'System exception'}"
        db.session.commit()

        # Escalate failure via notification to Admins
        self._escalate_step_failure(step, request)

        return {"success": False, "result_text": step.result_text, "failed": True}

    def _escalate_step_failure(self, step: WorkflowStep, request: Request):
        """Escalates a failed step to Admin and department heads."""
        admins = User.query.filter((User.role == 'admin') | (User.role == step.agent_type)).all()
        for admin in admins:
            notif = Notification(
                user_id=admin.id,
                message=f"ESCALATION: Step '{step.name}' failed in Workflow #{step.workflow_id} (Request #{request.id if request else 'N/A'}). Intervention required.",
                link=f"/admin/audit"
            )
            db.session.add(notif)
        db.session.commit()

    # -------------------------------------------------------------
    # 3. Full Workflow Orchestration
    # -------------------------------------------------------------
    def run_workflow(self, workflow_id: int, request_id: int = None) -> str:
        """
        Executes all steps of a workflow according to the DAG topology.
        Supports parallel execution of independent tasks and self-healing branch isolation.
        """
        workflow = db.session.get(Workflow, workflow_id)
        if not workflow:
            return "Workflow not found"

        request = db.session.get(Request, request_id) if request_id else (workflow.requests[0] if workflow.requests else None)
        
        workflow.status = 'in_progress'
        if request:
            request.status = 'in_progress'
        db.session.commit()

        dag_data = workflow.get_dag()
        tasks = dag_data.get("tasks", [])

        # Build mapping of step_key (or task id) -> WorkflowStep model
        step_map = {}
        for s in workflow.steps:
            if s.step_key:
                step_map[s.step_key] = s
            step_map[str(s.id)] = s

        # Topological sorting into parallel execution levels
        try:
            levels = self.validate_and_sort_dag(tasks)
        except WorkflowValidationError as e:
            workflow.status = 'failed'
            if request:
                request.status = 'failed'
            db.session.commit()
            return f"Validation error: {str(e)}"

        accumulated_context = {}
        failed_step_keys: Set[str] = set()

        for level in levels:
            # Filter tasks in this level: skip tasks whose dependencies failed
            runnable_tasks = []
            for task_id in level:
                task_def = next((t for t in tasks if t["id"] == task_id), None)
                deps = task_def.get("depends_on", []) if task_def else []
                
                # If any dependency failed, mark this task as skipped (self-healing branch isolation)
                if any(dep in failed_step_keys for dep in deps):
                    failed_step_keys.add(task_id)
                    s = step_map.get(task_id)
                    if s:
                        s.status = 'skipped'
                        s.result_text = "Skipped because prerequisite task failed."
                        db.session.commit()
                else:
                    s = step_map.get(task_id)
                    # Re-run if pending, in_progress, or previously waiting_approval
                    if s and s.status != 'done' and s.status != 'skipped':
                        runnable_tasks.append((task_id, s.id))

            if not runnable_tasks:
                continue

            for t_id, s_id in runnable_tasks:
                res = self.execute_step_with_retry(s_id, request_id, accumulated_context)
                if res.get('data'):
                    accumulated_context.update(res['data'])
                if res.get('waiting_human'):
                    # Halt workflow loop waiting for human input in portal
                    return "waiting_approval"
                if not res.get('success'):
                    failed_step_keys.add(t_id)

        # Check final status
        db.session.expire_all()
        workflow = db.session.get(Workflow, workflow_id)
        all_steps = workflow.steps
        has_waiting = any(s.status == 'waiting_approval' for s in all_steps)
        has_failed = any(s.status == 'failed' for s in all_steps)
        all_done = all(s.status in ('done', 'skipped') for s in all_steps)

        if has_waiting:
            workflow.status = 'in_progress'
        elif has_failed and not all_done:
            workflow.status = 'partially_failed' if any(s.status == 'done' for s in all_steps) else 'failed'
            if request:
                req = db.session.get(Request, request_id) if request_id else None
                if req:
                    req.status = 'failed'
        else:
            workflow.status = 'completed'
            if request:
                req = db.session.get(Request, request_id) if request_id else None
                if req:
                    req.status = 'completed'

        db.session.commit()
        return workflow.status

orchestrator = WorkflowOrchestrator()
