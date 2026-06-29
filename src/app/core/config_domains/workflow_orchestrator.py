"""Domínio: Workflow Orchestrator (Missão 77)."""

from pydantic import BaseModel


class WorkflowOrchestratorConfig(BaseModel):
    # Missao 77 - Workflow Orchestrator
    workflow_orchestrator_track_progress: bool = True
    workflow_orchestrator_allow_parallel: bool = True
