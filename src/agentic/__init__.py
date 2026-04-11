from src.agentic.intent_classifier import UserIntentClassifier
from src.agentic.models import AgenticTurnResult, OrchestratorDecision, UserIntentClassification

__all__ = [
    "AgenticTurnResult",
    "BasicAgenticWorkflow",
    "OrchestratorDecision",
    "UserIntentClassification",
    "UserIntentClassifier",
]


def __getattr__(name: str):
    if name == "BasicAgenticWorkflow":
        from src.agentic.workflow import BasicAgenticWorkflow

        return BasicAgenticWorkflow
    raise AttributeError(name)
