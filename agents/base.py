import logging
from abc import ABC, abstractmethod
from typing import Dict, Any

logger = logging.getLogger(__name__)

class BaseAgent(ABC):
    """
    Base class for all FlowOS simulated department AI agents.
    Every agent implements handle(step, request, context) -> Dict[str, Any]
    """
    agent_type: str = "base"

    def __init__(self, app=None):
        self.app = app

    @abstractmethod
    def handle(self, step, request, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute deterministic domain logic for this step.
        Returns dict with:
        - success (bool): True if completed, False if failed/retriable
        - result_text (str): Readable audit outcome
        - waiting_human (bool): True if requires human-in-the-loop action
        - data (dict): Arbitrary state data to propagate to downstream steps
        """
        pass
