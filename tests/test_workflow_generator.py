import pytest
from app import create_app
from extensions import db
from models import Workflow, WorkflowStep
from agents.orchestrator import WorkflowOrchestrator, WorkflowValidationError, orchestrator
from ai.ai_client import generate_workflow_json, classify_ticket
from ai.workflow_generator import workflow_generator_service
from seed import seed_database

@pytest.fixture
def app():
    app = create_app()
    app.config.update({
        'TESTING': True,
        'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
        'WTF_CSRF_ENABLED': False
    })
    with app.app_context():
        db.create_all()
        seed_database(app)
        yield app
        db.session.remove()
        db.drop_all()

def test_dag_topological_sort_and_parallel_batches():
    # Independent tasks t1 & t2 running in parallel, followed by t3
    tasks = [
        {"id": "t1", "name": "Task 1", "agent_type": "hr", "depends_on": []},
        {"id": "t2", "name": "Task 2", "agent_type": "it", "depends_on": []},
        {"id": "t3", "name": "Task 3", "agent_type": "notification", "depends_on": ["t1", "t2"]}
    ]
    batches = WorkflowOrchestrator.validate_and_sort_dag(tasks)
    assert len(batches) == 2
    assert set(batches[0]) == {"t1", "t2"}
    assert batches[1] == ["t3"]

def test_dag_cycle_detection_error():
    # Circular dependency: t1 -> t2 -> t3 -> t1
    tasks = [
        {"id": "t1", "name": "Task 1", "agent_type": "hr", "depends_on": ["t3"]},
        {"id": "t2", "name": "Task 2", "agent_type": "it", "depends_on": ["t1"]},
        {"id": "t3", "name": "Task 3", "agent_type": "notification", "depends_on": ["t2"]}
    ]
    with pytest.raises(WorkflowValidationError):
        WorkflowOrchestrator.validate_and_sort_dag(tasks)

def test_ai_workflow_generation_resilient_fallbacks(app):
    # Test 5 distinct sample instructions including unusual/nonsense input
    sample_instructions = [
        "When an employee relocates: HR verifies address, IT updates VPN permissions, Finance adjusts payroll.",
        "Security incident response: isolate device, reset passwords, notify manager.",
        "New employee onboarding: verify documents, setup email, assign laptop, orientation.",
        "Expense claim reimbursement for travel flight $500",
        "xyz random unparseable 1239847192847192837 nonsense words request"
    ]

    with app.app_context():
        for instruction in sample_instructions:
            wf, tier, meta = workflow_generator_service.create_workflow_from_text(instruction)
            assert wf is not None
            assert len(wf.steps) >= 2
            # Check DAG validity
            dag = wf.get_dag()
            assert "tasks" in dag
            batches = WorkflowOrchestrator.validate_and_sort_dag(dag["tasks"])
            assert len(batches) >= 1

def test_ticket_classification_fallback():
    assert classify_ticket("My laptop screen is cracked and flickering") == "hardware"
    assert classify_ticket("Cannot connect to corporate VPN from home network") in ("access", "network")
    assert classify_ticket("Need SSO access to GitHub organization") == "access"
    assert classify_ticket("PyCharm crashes when opening large workspace") == "software"
