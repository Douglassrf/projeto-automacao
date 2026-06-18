# src/app/services/orchestration_pipeline.py
from __future__ import annotations

from app.services.orchestration_pipeline_safe import OrchestrationPipelineSafe


class MasterOrchestrator(OrchestrationPipelineSafe):
    """Compatibilidade com chamadas antigas, agora roteadas para a camada safe."""
    def run_empire_cycle(self):
        return self.run_mock_cycle()


class FreeStackOrchestrator(OrchestrationPipelineSafe):
    """Compatibilidade com a rota /orchestration/run."""
    pass
