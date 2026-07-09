"""Missao 125 - Predictive Maintenance Center (Fase v2.1).

Quarta missao da Fase v2.1. Objetivo literal do briefing: "planejar
manutencao antes que ocorram problemas" - ou seja, diferente da Missao
124 (observatorio que ACOMPANHA o estado atual das seis dimensoes de
qualidade), esta missao olha para a DIRECAO real dos dados ao longo do
tempo e tenta antecipar onde a proxima falha provavelmente vai
aparecer, antes que ela vire um alerta ativo. Quatro entregas exigidas
pelo briefing, cada uma com fonte real, nunca reimplementada (regra 7
do CLAUDE.md):

1. Tendencias -> reuso direto de `ArchitectureEvolutionTimelineService`
   (Missao 123): `module_evolution()`, `api_evolution()` e
   `service_evolution()` ja expoem, por arquivo real do repositorio,
   `total_commits`, `first_commit` e `last_commit` (datas reais
   extraidas de `git log`). Esta missao nao mina o git de novo - so
   calcula, a partir desses tres campos ja prontos, duas metricas
   derivadas e honestas: `age_days` (dias desde o primeiro commit) e
   `days_since_last_change` (dias desde o ultimo commit) - e classifica
   cada arquivo em um rotulo de atividade (ver heuristica abaixo).
   Importante: como a API publica da Missao 123 nao expoe a lista
   completa de commits por arquivo (so primeiro/ultimo), "tendencia"
   aqui significa classificacao real de recencia/frequencia de
   mudanca, nao uma curva de inclinacao sintetica - isso esta
   documentado para nenhum leitor interpretar como algo mais preciso
   do que de fato e.
2. Alertas preventivos -> reuso direto de `AlertService.history()`
   (Missao 46, via instancia propria, mesmo padrao de
   `EngineeringMemoryCoreService.incident_history()` da Missao 122).
   Conta quantas vezes cada `check_name` ja apareceu no historico
   (open+resolved) - um check que reabriu repetidamente no passado e
   candidato real a preventive watch, mesmo que esteja "ok" agora.
   Exclui explicitamente qualquer `check_name` que JA esta em
   `AlertService.active_alerts()` - isso e reativo, nao preventivo, e
   ja e responsabilidade da Missao 46/124.
3. Componentes envelhecendo -> reuso do mesmo inventario calculado no
   item 1, filtrado e ordenado por `days_since_last_change`
   descendente - sem recalcular nada, so reordenar/filtrar dados reais
   ja derivados.
4. Sugestao de substituicao -> cruzamento de dois sinais reais e
   independentes sobre o MESMO arquivo: (a) esta envelhecendo (item 3)
   e (b) acumulou divida tecnica real via
   `TechDebtManagerService.debt_report()` (Missao 58, reuso direto,
   nunca recalculado). Um arquivo antigo SEM divida conhecida nao entra
   aqui (pode ser apenas estavel, nao problematico); um arquivo com
   divida mas recente tambem nao (esta sendo trabalhado ativamente,
   nao abandonado). So a combinacao real de "envelhecido" + "com divida
   conhecida" gera uma sugestao.

Heuristicas documentadas (regra 7 do CLAUDE.md exige isso sempre que o
julgamento for qualitativo - nenhum destes numeros e fato calculado,
sao limiares de julgamento explicitos, nunca escondidos numa formula):

- `_STALE_AFTER_DAYS = 90`: sem nenhum commit ha mais de ~3 meses ->
  rotulo "aging". Tres meses e usado como proxy de "ainda dentro do
  ciclo normal de manutencao" vs "comecando a ficar fora do radar" -
  nao existe um limiar oficial anterior no projeto para isto.
- `_DORMANT_AFTER_DAYS = 365`: sem nenhum commit ha mais de 1 ano ->
  rotulo "dormant" (severidade maior que "aging"). Arquivos no codigo
  de producao sem nenhum toque em 1 ano sao um sinal de risco mais
  forte do que apenas "aging".
- `_RECURRING_INCIDENT_THRESHOLD = 2`: um `check_name` que ja apareceu
  2+ vezes no historico de alertas (Missao 46) e tratado como "padrao
  recorrente" para fins de alerta preventivo. Uma unica ocorrencia
  passada nao basta para inferir recorrencia.

Nenhum desses tres numeros decide sozinho um veredito binario de
"aprovado/reprovado" - cada um so adiciona um arquivo/check a uma
lista observavel, com o numero real (idade em dias, contagem de
ocorrencias) sempre visivel ao lado do rotulo, para o leitor humano
formar o proprio julgamento sobre o limiar."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.services.alert_service import AlertService
from app.services.architecture_evolution_timeline_service import (
    ArchitectureEvolutionTimelineService,
)
from app.services.tech_debt_manager_service import TechDebtManagerService

UTC = timezone.utc

_STALE_AFTER_DAYS = 90
_DORMANT_AFTER_DAYS = 365
_RECURRING_INCIDENT_THRESHOLD = 2

_GROUP_TO_DIRECTORY_PREFIX = {
    "module": "src/app/core/",
    "api": "src/app/api/routes/",
    "service": "src/app/services/",
}


def _activity_label(days_since_last_change: int) -> str:
    """Classificacao de atividade a partir de dados reais (dias desde o
    ultimo commit) - heuristica documentada no docstring do modulo."""
    if days_since_last_change >= _DORMANT_AFTER_DAYS:
        return "dormant"
    if days_since_last_change >= _STALE_AFTER_DAYS:
        return "aging"
    return "active"


class PredictiveMaintenanceService:
    """Missao 125. Depende de `db` porque `AlertService` (Missao 46) e
    `ArchitectureEvolutionTimelineService` (Missao 123, que por sua vez
    depende de `EngineeringMemoryCoreService`/Missao 122) precisam de
    banco. `TechDebtManagerService` (Missao 58) nao depende - le so
    arquivo via AST e `git`, mesmo motivo ja documentado em
    `get_tech_debt_manager_service()` no container."""

    def __init__(
        self,
        db: Session,
        evolution_timeline: ArchitectureEvolutionTimelineService | None = None,
        tech_debt_manager: TechDebtManagerService | None = None,
        alert_service: AlertService | None = None,
    ) -> None:
        self.db = db
        self.evolution_timeline = evolution_timeline or ArchitectureEvolutionTimelineService(db)
        self.tech_debt_manager = tech_debt_manager or TechDebtManagerService()
        self.alert_service = alert_service or AlertService(db)

    # --- inventario base (reuso unico da Missao 123, nunca remina o git) ---

    def component_inventory(self) -> list[dict[str, Any]]:
        """Lista plana de todo arquivo real rastreado por
        `ArchitectureEvolutionTimelineService` (Missao 123) nos tres
        grupos (`module`/`api`/`service`), com idade e atividade
        derivadas dos campos reais `first_commit`/`last_commit`/
        `total_commits` que a Missao 123 ja calcula - sem nenhuma
        chamada adicional ao `git`."""
        now = datetime.now(UTC)
        groups: dict[str, dict[str, Any]] = {
            "module": self.evolution_timeline.module_evolution(),
            "api": self.evolution_timeline.api_evolution(),
            "service": self.evolution_timeline.service_evolution(),
        }
        inventory: list[dict[str, Any]] = []
        for group_name, evolution in groups.items():
            for entry in evolution["files"]:
                first_at = entry["first_commit"]["committed_at"]
                last_at = entry["last_commit"]["committed_at"]
                age_days = max(0, (now - first_at).days)
                days_since_last_change = max(0, (now - last_at).days)
                inventory.append(
                    {
                        "component_group": group_name,
                        "file": entry["file"],
                        "total_commits": entry["total_commits"],
                        "first_commit_at": first_at,
                        "last_commit_at": last_at,
                        "age_days": age_days,
                        "days_since_last_change": days_since_last_change,
                        "commits_per_day_since_creation": round(
                            entry["total_commits"] / max(age_days, 1), 4
                        ),
                        "activity": _activity_label(days_since_last_change),
                    }
                )
        inventory.sort(key=lambda item: item["days_since_last_change"], reverse=True)
        return inventory

    @staticmethod
    def _debt_file_set() -> tuple[set[str], dict[str, int]]:
        """Conjunto de arquivos com divida real conhecida (Missao 58),
        normalizado para o mesmo formato de caminho usado pela Missao
        123 (`src/app/<resto>`, em vez do `<resto>` relativo a
        `src/app/` que a Missao 58 usa internamente) - so para permitir
        o cruzamento no item 4, nunca recalcula a divida em si."""
        manager = TechDebtManagerService()
        debt_report = manager.debt_report()
        score_by_file: dict[str, int] = {}
        for hotspot in debt_report["hotspots"]:
            normalized = f"src/app/{hotspot['file']}"
            score_by_file[normalized] = hotspot["total_score"]
        for item in debt_report["backlog"]:
            normalized = f"src/app/{item['file']}"
            score_by_file[normalized] = score_by_file.get(normalized, 0) + item["priority_score"]
        return set(score_by_file), score_by_file

    # --- entrega 1: tendencias --------------------------------------------

    def change_trends(self) -> dict[str, Any]:
        """Tendencia real de mudanca por grupo (`module`/`api`/
        `service`): quantos arquivos estao em cada rotulo de atividade
        e a media de `commits_per_day_since_creation` por grupo - tudo
        derivado do inventario do item anterior, sem nenhum numero
        inventado."""
        inventory = self.component_inventory()
        by_group: dict[str, dict[str, Any]] = {}
        for group_name in _GROUP_TO_DIRECTORY_PREFIX:
            files = [item for item in inventory if item["component_group"] == group_name]
            activity_counts: dict[str, int] = {"active": 0, "aging": 0, "dormant": 0}
            for item in files:
                activity_counts[item["activity"]] += 1
            avg_rate = (
                round(sum(item["commits_per_day_since_creation"] for item in files) / len(files), 4)
                if files
                else 0.0
            )
            by_group[group_name] = {
                "tracked_files": len(files),
                "activity_counts": activity_counts,
                "average_commits_per_day": avg_rate,
            }
        return {
            "generated_at": datetime.now(UTC),
            "by_group": by_group,
            "total_tracked_files": len(inventory),
        }

    # --- entrega 2: alertas preventivos -----------------------------------

    def preventive_alerts(self) -> dict[str, Any]:
        """Padroes recorrentes reais no historico de alertas (Missao
        46) que ainda NAO estao ativos agora - preventivo por
        definicao: se ja estivesse ativo, seria responsabilidade da
        Missao 46/124, nao desta. Heuristica de limiar documentada no
        docstring do modulo (`_RECURRING_INCIDENT_THRESHOLD`)."""
        history = self.alert_service.history(limit=None)
        active_names = {alert["check_name"] for alert in self.alert_service.active_alerts()}

        episode_counts: dict[str, int] = {}
        latest_message: dict[str, str] = {}
        latest_seen: dict[str, Any] = {}
        for event in history:
            name = event["check_name"]
            episode_counts[name] = episode_counts.get(name, 0) + 1
            if name not in latest_seen or event["first_seen_at"] > latest_seen[name]:
                latest_seen[name] = event["first_seen_at"]
                latest_message[name] = event["message"]

        watchlist = sorted(
            (
                {
                    "check_name": name,
                    "historical_episode_count": count,
                    "last_message": latest_message[name],
                    "last_seen_at": latest_seen[name],
                }
                for name, count in episode_counts.items()
                if count >= _RECURRING_INCIDENT_THRESHOLD and name not in active_names
            ),
            key=lambda entry: entry["historical_episode_count"],
            reverse=True,
        )
        return {
            "generated_at": datetime.now(UTC),
            "recurring_incident_threshold": _RECURRING_INCIDENT_THRESHOLD,
            "checks_with_history": len(episode_counts),
            "currently_active_check_count": len(active_names),
            "preventive_watchlist": watchlist,
        }

    # --- entrega 3: componentes envelhecendo ------------------------------

    def aging_components(self, top_n: int | None = 10) -> dict[str, Any]:
        """Arquivos reais com `activity` em `aging`/`dormant`, ordenados
        pelo maior `days_since_last_change` - mesmo inventario do item
        1, so filtrado/recortado, nunca recalculado de novo."""
        inventory = self.component_inventory()
        aging = [item for item in inventory if item["activity"] in ("aging", "dormant")]
        top = aging if top_n is None else aging[:top_n]
        return {
            "generated_at": datetime.now(UTC),
            "stale_after_days": _STALE_AFTER_DAYS,
            "dormant_after_days": _DORMANT_AFTER_DAYS,
            "aging_component_count": len(aging),
            "top": top,
        }

    # --- entrega 4: sugestao de substituicao ------------------------------

    def replacement_suggestions(self, top_n: int | None = 10) -> dict[str, Any]:
        """Cruzamento real de dois sinais independentes sobre o MESMO
        arquivo: envelhecido (item 3) + divida tecnica conhecida
        (Missao 58). So entra na lista quem tem os dois sinais ao mesmo
        tempo - ver justificativa completa no docstring do modulo."""
        aging_all = self.aging_components(top_n=None)["top"]
        debt_files, debt_scores = self._debt_file_set()

        suggestions = [
            {
                **item,
                "known_debt_score": debt_scores[item["file"]],
                "reason": (
                    f"sem alteracao ha {item['days_since_last_change']} dia(s) "
                    f"({item['activity']}) e com divida tecnica acumulada conhecida "
                    f"(pontuacao {debt_scores[item['file']]}, Missao 58)"
                ),
            }
            for item in aging_all
            if item["file"] in debt_files
        ]
        suggestions.sort(key=lambda entry: entry["known_debt_score"], reverse=True)
        return {
            "generated_at": datetime.now(UTC),
            "criteria": (
                "arquivo precisa estar envelhecido (aging/dormant, "
                f">= {_STALE_AFTER_DAYS} dias sem alteracao) E ter divida tecnica "
                "conhecida (Missao 58) ao mesmo tempo - um sinal isolado nao basta"
            ),
            "suggestion_count": len(suggestions),
            "top": suggestions if top_n is None else suggestions[:top_n],
        }

    # --- agregacao ---------------------------------------------------------

    def maintenance_report(self) -> dict[str, Any]:
        return {
            "generated_at": datetime.now(UTC),
            "trends": self.change_trends(),
            "preventive_alerts": self.preventive_alerts(),
            "aging_components": self.aging_components(),
            "replacement_suggestions": self.replacement_suggestions(),
        }

    def render_markdown(self, report: dict[str, Any] | None = None) -> str:
        report = report if report is not None else self.maintenance_report()
        trends = report["trends"]
        preventive = report["preventive_alerts"]
        aging = report["aging_components"]
        suggestions = report["replacement_suggestions"]

        lines: list[str] = [
            "# Centro de Manutencao Preditiva (Missao 125)",
            "",
            f"- Gerado em: {report['generated_at']}",
            f"- Arquivos rastreados (Missao 123): {trends['total_tracked_files']}",
            "",
            "## Tendencias por grupo",
            "",
        ]
        for group_name, data in trends["by_group"].items():
            counts = data["activity_counts"]
            lines.append(
                f"- `{group_name}`: {data['tracked_files']} arquivo(s) - "
                f"active={counts['active']}, aging={counts['aging']}, "
                f"dormant={counts['dormant']}, media de commits/dia="
                f"{data['average_commits_per_day']}"
            )

        lines.append("")
        lines.append("## Alertas preventivos")
        lines.append("")
        lines.append(
            f"- Checks com historico: {preventive['checks_with_history']} "
            f"(limiar de recorrencia: {preventive['recurring_incident_threshold']}+ episodios)"
        )
        if preventive["preventive_watchlist"]:
            for entry in preventive["preventive_watchlist"]:
                lines.append(
                    f"  - `{entry['check_name']}`: {entry['historical_episode_count']} "
                    f"episodio(s) no historico, ultima mensagem: {entry['last_message']}"
                )
        else:
            lines.append("  - Nenhum check recorrente fora dos ja ativos agora.")

        lines.append("")
        lines.append(
            f"## Componentes envelhecendo (>= {aging['stale_after_days']} dias sem alteracao)"
        )
        lines.append("")
        lines.append(f"- Total: {aging['aging_component_count']}")
        for item in aging["top"]:
            lines.append(
                f"  - [{item['activity']}] {item['file']}: "
                f"{item['days_since_last_change']} dia(s) sem alteracao, "
                f"{item['total_commits']} commit(s) na historia"
            )

        lines.append("")
        lines.append("## Sugestoes de substituicao/refatoracao")
        lines.append("")
        lines.append(f"- {suggestions['criteria']}")
        if suggestions["top"]:
            for entry in suggestions["top"]:
                lines.append(f"  - {entry['file']}: {entry['reason']}")
        else:
            lines.append("  - Nenhum arquivo atende aos dois criterios ao mesmo tempo hoje.")

        lines.append("")
        lines.append(
            "**IMPORTANTE**: esta missao planeja manutencao a partir de evidencia real "
            "(git + divida tecnica + historico de alertas) - os limiares de dias e de "
            "recorrencia sao heuristicas documentadas (regra 7 do CLAUDE.md), nunca um "
            "veredito automatico de 'precisa ser reescrito'. Decisao final cabe a um "
            "humano."
        )

        return "\n".join(lines)
