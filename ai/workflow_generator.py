import json
from extensions import db
from models import Workflow, WorkflowStep, WorkflowTemplate, User
from ai.ai_client import generate_workflow_json
from ai.embeddings import find_best_template_match
from agents.orchestrator import WorkflowOrchestrator, WorkflowValidationError

class WorkflowGeneratorService:
    """
    Orchestrates NL workflow parsing, template reuse, DAG cycle validation,
    and database persistence of Workflows and Steps.
    """

    @staticmethod
    def create_workflow_from_text(instruction: str, user_id: int = None, use_template_matching: bool = True) -> tuple:
        """
        Creates a new Workflow from natural language text.
        Returns: (workflow_instance, source_tier_str, metadata_dict)
        """
        instruction = (instruction or '').strip()
        if not instruction:
            raise WorkflowValidationError("Workflow description cannot be empty.")

        dag_data = None
        source_tier = "Rule-based Engine"
        match_score = 0.0

        # 1. Check for high-similarity existing WorkflowTemplate
        if use_template_matching:
            templates = WorkflowTemplate.query.all()
            best_tmpl, score = find_best_template_match(instruction, templates, threshold=0.82)
            if best_tmpl and score >= 0.82:
                dag_data = best_tmpl.get_dag()
                source_tier = f"Template Library (Similarity: {int(score*100)}%)"
                match_score = score

        # 2. If no template matched, invoke AI Cascade (Gemini -> Mistral -> Rule Engine)
        if not dag_data:
            dag_data = generate_workflow_json(instruction)
            source_tier = dag_data.get("ai_model", "AI Workflow Generator")

        tasks = dag_data.get("tasks", [])
        if not tasks or not isinstance(tasks, list):
            raise WorkflowValidationError("Generated workflow contained no executable tasks.")

        # 3. Validate DAG for cycles and validity
        WorkflowOrchestrator.validate_and_sort_dag(tasks)

        # 4. Persist Workflow & WorkflowSteps
        workflow_name = dag_data.get("workflow_name") or "Generated Enterprise Workflow"
        workflow = Workflow(
            name=workflow_name,
            created_by=user_id,
            dag_json=json.dumps(dag_data),
            source_text=instruction,
            status='pending'
        )
        db.session.add(workflow)
        db.session.flush() # obtain workflow.id

        # Insert Steps
        for t in tasks:
            step = WorkflowStep(
                workflow_id=workflow.id,
                step_key=t.get("id"),
                name=t.get("name", "Unnamed Step"),
                agent_type=t.get("agent_type", "hr"),
                depends_on_json=json.dumps(t.get("depends_on", [])),
                status='pending'
            )
            db.session.add(step)

        db.session.commit()

        metadata = {
            "source_tier": source_tier,
            "match_score": match_score,
            "tasks_count": len(tasks),
            "workflow_name": workflow_name
        }

        return workflow, source_tier, metadata

workflow_generator_service = WorkflowGeneratorService()
