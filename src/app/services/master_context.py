from __future__ import annotations

import json
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


_LOCK = threading.Lock()


class MasterContextStore:
    """Memória Mestre do projeto.

    Missão 15:
    - Guarda o mapa operacional atual do projeto.
    - Resume última missão, próxima missão, módulos aprovados e riscos.
    - Lê DecisionFeed e CampaignMemory antes de qualquer nova missão.
    - Não publica campanha.
    - Não chama API externa.
    - Não depende de banco.
    """

    DEFAULT_CONTEXT: dict[str, Any] = {
        "project_name": "Projeto Automação / Radar PDF IA",
        "operational_rule": "Sempre seguir a Bússola: auditar, entender, implementar uma coisa por vez, validar, só então avançar.",
        "last_completed_mission": 14,
        "current_status": "LearningLoop conectado ao DecisionFeed, CampaignMemory e CampaignBrain em modo seguro.",
        "next_recommended_mission": "Auditoria Profunda do ContentOrchestrator",
        "approved_modules": [
            "FastAPI",
            "Swagger",
            "SafeRouter",
            "AdProcessor",
            "MinerEngine",
            "FacebookAdMiner",
            "CampaignBrainAgent",
            "CampaignMemoryStore",
            "DecisionFeedStore",
            "MetaUpdateWatcher",
            "CampaignIntelligenceSafe",
            "MetaCampaignOperator Dry Run",
            "LearningLoopSafe",
            "LearningLoopBrainBridge",
        ],
        "pending_modules": [
            "ContentOrchestrator auditoria profunda",
            "VideoPipeline auditoria profunda",
            "PremiumRender auditoria profunda",
            "SiteBuilder auditoria profunda",
            "OrchestrationPipeline reparo seguro",
            "TikTok Engine futuro",
        ],
        "known_risks": [
            "Não ativar todos os módulos de uma vez.",
            "SiteBuilder possui sinais de legacy.",
            "OrchestrationPipeline é blueprint e está desalinhado com o MinerEngine atual.",
            "VideoPipeline/PremiumRender podem depender de FFmpeg/Pillow.",
            "Rotas pesadas podem exigir autenticação/banco.",
            "Caminho padrão /data pode falhar em ambientes sem permissão; preferir output local seguro.",
        ],
        "mandatory_startup_ritual": [
            "Ler MasterContextStore.snapshot().",
            "Ler últimas decisões do DecisionFeed.",
            "Ler últimas memórias do CampaignMemory.",
            "Confirmar última missão concluída.",
            "Confirmar próxima missão recomendada.",
            "Só então implementar.",
        ],
    }

    def __init__(self, logs_dir: Path | None = None) -> None:
        project_root = Path(__file__).resolve().parents[3]
        self.logs_dir = logs_dir or project_root / "logs"
        self.context_file = self.logs_dir / "master_context.json"
        self.history_file = self.logs_dir / "master_context_history.log"
        self.decision_feed_file = self.logs_dir / "decision_feed.log"
        self.memory_file = self.logs_dir / "campaign_brain_memory.log"

    def health(self) -> dict[str, Any]:
        return {
            "status": "ok",
            "agent": "MasterContextStore",
            "mode": "persistent_architect_memory",
            "context_file": str(self.context_file),
            "history_file": str(self.history_file),
            "database_required": False,
            "external_api": False,
        }

    def ensure_initialized(self) -> dict[str, Any]:
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        if not self.context_file.exists():
            payload = dict(self.DEFAULT_CONTEXT)
            payload["created_at"] = datetime.now(UTC).isoformat()
            payload["updated_at"] = payload["created_at"]
            self._write_context(payload)
            self._append_history({"event": "initialized", "context": payload})
        return self.snapshot()

    def update(self, patch: dict[str, Any]) -> dict[str, Any]:
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        current = self._read_context() or dict(self.DEFAULT_CONTEXT)
        before = dict(current)
        for key, value in (patch or {}).items():
            current[key] = value
        current["updated_at"] = datetime.now(UTC).isoformat()
        self._write_context(current)
        self._append_history({"event": "updated", "patch": patch, "before": before, "after": current})
        return self.snapshot()

    def record_mission(self, mission_number: int, title: str, status: str, summary: str, next_mission: str | None = None) -> dict[str, Any]:
        current = self._read_context() or dict(self.DEFAULT_CONTEXT)
        missions = current.get("missions", [])
        if not isinstance(missions, list):
            missions = []
        entry = {
            "mission_number": mission_number,
            "title": title,
            "status": status,
            "summary": summary,
            "recorded_at": datetime.now(UTC).isoformat(),
        }
        missions.append(entry)
        current["missions"] = missions[-50:]
        current["last_completed_mission"] = mission_number if status.lower() in {"approved", "aprovada", "done", "ok"} else current.get("last_completed_mission")
        current["current_status"] = summary
        if next_mission:
            current["next_recommended_mission"] = next_mission
        current["updated_at"] = datetime.now(UTC).isoformat()
        self._write_context(current)
        self._append_history({"event": "mission_recorded", "entry": entry})
        return self.snapshot()

    def snapshot(self, recent_limit: int = 10) -> dict[str, Any]:
        context = self._read_context() or dict(self.DEFAULT_CONTEXT)
        recent_decisions = self._read_jsonl(self.decision_feed_file, recent_limit)
        recent_memory = self._read_jsonl(self.memory_file, recent_limit)
        return {
            "status": "ok",
            "agent": "MasterContextStore",
            "context": context,
            "recent_decisions_count": len(recent_decisions),
            "recent_memory_count": len(recent_memory),
            "recent_decisions": recent_decisions,
            "recent_memory": recent_memory,
            "startup_summary": self._startup_summary(context, recent_decisions, recent_memory),
        }

    def startup_checklist(self) -> dict[str, Any]:
        snap = self.ensure_initialized()
        context = snap["context"]
        return {
            "status": "ok",
            "agent": "ChiefArchitectMemory",
            "must_read_before_mission": True,
            "last_completed_mission": context.get("last_completed_mission"),
            "next_recommended_mission": context.get("next_recommended_mission"),
            "approved_modules": context.get("approved_modules", []),
            "pending_modules": context.get("pending_modules", []),
            "known_risks": context.get("known_risks", []),
            "startup_summary": snap["startup_summary"],
            "decision_feed_seen": snap["recent_decisions_count"],
            "campaign_memory_seen": snap["recent_memory_count"],
        }

    def _startup_summary(self, context: dict[str, Any], decisions: list[dict[str, Any]], memories: list[dict[str, Any]]) -> str:
        return (
            f"Última missão concluída: {context.get('last_completed_mission')}. "
            f"Próxima missão recomendada: {context.get('next_recommended_mission')}. "
            f"Módulos aprovados: {len(context.get('approved_modules', []))}. "
            f"Pendências: {len(context.get('pending_modules', []))}. "
            f"Decisões recentes lidas: {len(decisions)}. "
            f"Memórias recentes lidas: {len(memories)}."
        )

    def _read_context(self) -> dict[str, Any] | None:
        if not self.context_file.exists():
            return None
        try:
            data = json.loads(self.context_file.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else None
        except json.JSONDecodeError:
            return None

    def _write_context(self, payload: dict[str, Any]) -> None:
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        with _LOCK:
            self.context_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def _append_history(self, payload: dict[str, Any]) -> None:
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        record = dict(payload)
        record.setdefault("recorded_at", datetime.now(UTC).isoformat())
        with _LOCK:
            with self.history_file.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    @staticmethod
    def _read_jsonl(path: Path, limit: int = 10) -> list[dict[str, Any]]:
        if not path.exists():
            return []
        records: list[dict[str, Any]] = []
        with path.open("r", encoding="utf-8") as handle:
            lines = handle.readlines()[-limit:]
        for line in lines:
            try:
                item = json.loads(line.strip())
                if isinstance(item, dict):
                    records.append(item)
            except json.JSONDecodeError:
                continue
        return records
