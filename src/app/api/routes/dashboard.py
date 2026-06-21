from __future__ import annotations

from html import escape
from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.operational_dashboard import operational_dashboard_snapshot
from app.db.session import get_db
from app.domain.models import User

router = APIRouter(prefix="/dashboard", tags=["Operational Dashboard"])

QUICK_ACTIONS = [
    ("◇", "Criar Campanha", "Crie uma nova campanha do zero", "purple"),
    ("▧", "Gerar Criativos", "Imagens e textos que vendem", "green"),
    ("▶", "Gerar Vídeo", "Vídeos prontos para anúncios", "orange"),
    ("▤", "Criar Site", "Landing pages que convertem", "blue"),
    ("♪", "TikTok Pack", "Pacote completo para TikTok Ads", "slate"),
    ("◌", "Brain de Anúncios", "Ideias inteligentes para vender mais", "lime"),
]

PROCESS_STEPS = [
    ("▣", "Envie seu produto ou ideia"),
    ("⌕", "Nós pesquisamos e analisamos tudo"),
    ("◌", "Geramos estratégias inteligentes"),
    ("✦", "Criamos tudo para você"),
    ("⌁", "Publicamos e monitoramos"),
    ("$", "Você vende mais!"),
]


def _health_percent(snapshot: dict[str, Any]) -> int:
    alerts = snapshot["alerts"]
    tasks = snapshot["tasks"]
    deductions = (
        len(alerts["active_blockers"]) * 12
        + int(tasks["failed_routes"]) * 15
        + min(int(alerts["pending_human_approvals"]), 5) * 4
        + min(int(alerts["queue_running"]), 5) * 2
    )
    return max(0, min(100, 100 - deductions))


def _status_label(value: bool, enabled_label: str, disabled_label: str) -> str:
    return enabled_label if value else disabled_label


def _quick_action(icon: str, title: str, description: str, accent: str) -> str:
    return f"""
    <article class="quick-card {escape(accent)}">
      <div class="quick-icon">{escape(icon)}</div>
      <div>
        <h3>{escape(title)}</h3>
        <p>{escape(description)}</p>
      </div>
      <button type="button" aria-label="Abrir {escape(title)}">→</button>
    </article>
    """


def _metric_card(title: str, number: Any, variation: str, href: str = "#visao-geral") -> str:
    return f"""
    <article class="metric-card">
      <span>{escape(title)}</span>
      <strong>{escape(str(number))}</strong>
      <small>{escape(variation)}</small>
      <a href="{escape(href)}">Ver detalhes</a>
    </article>
    """


def _activity_list(snapshot: dict[str, Any]) -> str:
    alerts = snapshot["alerts"]
    tasks = snapshot["tasks"]
    queues = snapshot["queues"]["summary"]
    activities = [
        ("atual", f"{alerts['pending_human_approvals']} aprovações humanas pendentes"),
        ("atual", f"{alerts['open_performance_tickets']} tickets de performance abertos"),
        ("atual", f"{alerts['queue_pending']} jobs aguardando fila"),
        ("atual", f"{tasks['failed_routes']} rotas com falha de carregamento"),
        ("atual", f"{queues['running']} jobs em execução"),
    ]
    return "".join(
        f"<li><span>{escape(time_label)}</span><p>{escape(message)}</p></li>" for time_label, message in activities
    )


def _automation_list(snapshot: dict[str, Any]) -> str:
    controls = snapshot["security"]["controls"]
    enabled_controls = [(name, enabled) for name, enabled in sorted(controls.items()) if enabled]
    if not enabled_controls:
        return "<li><b>!</b><p>Nenhum controle ativo reportado</p><em>Inativo</em></li>"
    return "".join(
        f"<li><b>✓</b><p>{escape(name.replace('_', ' ').title())}</p><em>Ativo</em></li>"
        for name, _enabled in enabled_controls[:6]
    )


def _blocker_list(snapshot: dict[str, Any]) -> str:
    blockers = snapshot["alerts"]["active_blockers"]
    if not blockers:
        return "<li><span>Bloqueios ativos</span><strong>0</strong></li>"
    return "".join(f"<li><span>{escape(item)}</span><strong>!</strong></li>" for item in blockers[:5])


def _render_operational_dashboard_html(snapshot: dict[str, Any], current_user: User) -> str:
    user_name = escape(getattr(current_user, "name", "Douglas") or "Douglas")
    mode = snapshot["mode"]
    queue = snapshot["queues"]["summary"]
    audit = snapshot["audit"]
    connectors = snapshot["connectors"]
    campaigns = snapshot["campaigns"]
    alerts = snapshot["alerts"]
    tasks = snapshot["tasks"]
    health_percent = _health_percent(snapshot)
    system_label = f"Sistema {health_percent}%"

    quick_actions = "".join(_quick_action(*item) for item in QUICK_ACTIONS)
    process_steps = "".join(
        f"<div class='process-step'><span>{index}</span><i>{escape(icon)}</i><p>{escape(label)}</p></div>"
        for index, (icon, label) in enumerate(PROCESS_STEPS, start=1)
    )
    metrics = "".join(
        [
            _metric_card("Campanhas", campaigns["total"], f"{campaigns['open_tickets']} tickets abertos"),
            _metric_card("Fila", queue["queued"], f"{queue['running']} em execução"),
            _metric_card("Aprovações", alerts["pending_human_approvals"], "pendências humanas"),
            _metric_card("Conectores", len(connectors["items"]), connectors["status"]),
        ]
    )
    mode_summary = [
        ("Dry-run", _status_label(bool(mode["dry_run"]), "Ativo", "Inativo")),
        ("Real-mode", _status_label(bool(mode["real_mode_enabled"]), "Ativo", "Bloqueado")),
        ("Auth", _status_label(bool(mode["auth_required"]), "Obrigatório", "Desativado")),
        ("Auditoria", _status_label(bool(audit["hash_chain_ok"]), "Íntegra", "Atenção")),
    ]
    mode_pills = "".join(f"<span>{escape(label)}: <b>{escape(value)}</b></span>" for label, value in mode_summary)

    return f"""
<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Dashboard Operacional — Automação</title>
  <style>
    :root {{
      --bg: #070710;
      --surface: #0e1020;
      --surface-2: #15182b;
      --border: rgba(255,255,255,.08);
      --text: #f7f7ff;
      --muted: #8d93aa;
      --purple: #8b5cf6;
      --blue: #2f80ff;
      --green: #22c55e;
      --orange: #f97316;
      --pink: #ec4899;
      --lime: #a3e635;
      --slate: #64748b;
    }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; min-height: 100vh; background: radial-gradient(circle at 28% 0%, rgba(139,92,246,.24), transparent 34%), var(--bg); color: var(--text); font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
    .dashboard-shell {{ display: grid; grid-template-columns: 282px minmax(0, 1fr) 390px; min-height: 100vh; }}
    .sidebar {{ position: sticky; top: 0; height: 100vh; padding: 26px 18px; background: rgba(7,7,16,.98); border-right: 1px solid var(--border); display: flex; flex-direction: column; gap: 20px; }}
    .brand {{ display: flex; align-items: center; gap: 12px; font-weight: 950; letter-spacing: -.02em; }}
    .brand-mark {{ width: 40px; height: 40px; display: grid; place-items: center; border-radius: 14px; background: linear-gradient(135deg, var(--purple), var(--blue)); box-shadow: 0 18px 46px rgba(47,128,255,.32); }}
    .brand small {{ color: var(--muted); display: block; font-size: 12px; font-weight: 800; }}
    .nav-group {{ display: grid; gap: 8px; }}
    .nav-group small {{ color: #626980; font-size: 11px; font-weight: 950; letter-spacing: .18em; }}
    .nav-item {{ width: 100%; border: 0; border-radius: 16px; padding: 12px 14px; color: #c8cde0; background: transparent; text-align: left; font-weight: 800; }}
    .nav-item.active {{ color: white; background: linear-gradient(135deg, var(--purple), var(--blue)); box-shadow: 0 16px 42px rgba(139,92,246,.32); }}
    .assistant-card {{ margin-top: auto; padding: 16px; border-radius: 22px; background: linear-gradient(145deg, rgba(139,92,246,.24), rgba(47,128,255,.13)); border: 1px solid var(--border); }}
    .assistant-card p {{ color: var(--muted); margin: 6px 0 14px; }}
    .profile {{ display: flex; align-items: center; gap: 12px; padding-top: 14px; border-top: 1px solid var(--border); }}
    .avatar {{ width: 38px; height: 38px; display: grid; place-items: center; border-radius: 50%; background: linear-gradient(135deg, var(--purple), var(--pink)); font-weight: 950; }}
    .profile span {{ color: var(--muted); font-size: 13px; }}
    .main {{ padding: 30px; min-width: 0; }}
    .rightbar {{ padding: 30px 26px 30px 0; display: grid; align-content: start; gap: 18px; }}
    .topbar {{ display: flex; align-items: center; justify-content: space-between; gap: 20px; margin-bottom: 28px; }}
    .hello {{ color: var(--muted); margin: 0 0 8px; font-weight: 800; }}
    h1 {{ margin: 0; font-size: clamp(38px, 5vw, 68px); line-height: .94; letter-spacing: -.06em; }}
    .gradient-word {{ background: linear-gradient(135deg, var(--purple), var(--blue)); -webkit-background-clip: text; background-clip: text; color: transparent; }}
    .top-actions {{ display: flex; align-items: center; gap: 12px; }}
    .search {{ width: min(360px, 32vw); border: 1px solid var(--border); border-radius: 18px; padding: 14px 16px; color: var(--text); background: var(--surface); outline: none; }}
    .icon-button, .system-card {{ border: 1px solid var(--border); border-radius: 18px; background: var(--surface); color: var(--text); padding: 13px 15px; font-weight: 900; }}
    .system-card {{ color: #bbf7d0; background: rgba(34,197,94,.13); box-shadow: 0 0 34px rgba(34,197,94,.13); }}
    .section {{ margin-bottom: 22px; }}
    .section-head {{ display: flex; align-items: end; justify-content: space-between; gap: 12px; margin-bottom: 14px; }}
    .section h2, .panel h2 {{ margin: 0; font-size: 22px; letter-spacing: -.02em; }}
    .mode-pills {{ display: flex; flex-wrap: wrap; gap: 8px; }}
    .mode-pills span {{ border: 1px solid var(--border); border-radius: 999px; padding: 7px 10px; color: var(--muted); background: rgba(255,255,255,.03); font-size: 12px; }}
    .quick-grid {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 16px; }}
    .quick-card {{ min-height: 176px; display: flex; flex-direction: column; justify-content: space-between; position: relative; overflow: hidden; padding: 20px; border-radius: 24px; background: linear-gradient(180deg, rgba(255,255,255,.045), rgba(255,255,255,.02)), var(--surface); border: 1px solid var(--border); box-shadow: 0 24px 70px rgba(0,0,0,.22); }}
    .quick-card::after {{ content: ""; position: absolute; inset: auto -28px -42px auto; width: 130px; height: 130px; border-radius: 50%; background: var(--accent); opacity: .11; filter: blur(2px); }}
    .quick-card.purple {{ --accent: var(--purple); }} .quick-card.green {{ --accent: var(--green); }} .quick-card.orange {{ --accent: var(--orange); }} .quick-card.blue {{ --accent: var(--blue); }} .quick-card.slate {{ --accent: var(--slate); }} .quick-card.lime {{ --accent: var(--lime); }}
    .quick-icon {{ width: 50px; height: 50px; display: grid; place-items: center; border-radius: 18px; background: color-mix(in srgb, var(--accent) 22%, transparent); color: var(--accent); font-size: 24px; box-shadow: 0 0 28px color-mix(in srgb, var(--accent) 22%, transparent); }}
    .quick-card h3 {{ margin: 16px 0 6px; font-size: 18px; }} .quick-card p {{ margin: 0; color: var(--muted); line-height: 1.4; }}
    .quick-card button {{ position: absolute; right: 18px; bottom: 18px; width: 40px; height: 40px; border: 0; border-radius: 14px; background: rgba(255,255,255,.07); color: white; font-size: 20px; }}
    .process-card, .overview-card, .panel {{ border: 1px solid var(--border); border-radius: 26px; padding: 22px; background: rgba(14,16,32,.86); box-shadow: 0 24px 80px rgba(0,0,0,.24); }}
    .process-flow {{ position: relative; display: grid; grid-template-columns: repeat(6, minmax(0, 1fr)); gap: 10px; }}
    .process-flow::before {{ content: ""; position: absolute; top: 43px; left: 8%; right: 8%; height: 2px; background: linear-gradient(90deg, transparent, rgba(139,92,246,.55), rgba(47,128,255,.55), transparent); }}
    .process-step {{ position: relative; z-index: 1; display: grid; justify-items: center; gap: 8px; text-align: center; color: #d7dcf0; font-size: 13px; }}
    .process-step span {{ width: 24px; height: 24px; display: grid; place-items: center; border-radius: 999px; background: var(--surface-2); border: 1px solid var(--border); color: var(--muted); font-size: 12px; }}
    .process-step i {{ width: 54px; height: 54px; display: grid; place-items: center; border-radius: 19px; background: linear-gradient(135deg, rgba(139,92,246,.22), rgba(47,128,255,.18)); color: var(--blue); font-style: normal; font-size: 22px; }}
    .metrics-grid {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 14px; }}
    .metric-card {{ padding: 18px; border-radius: 22px; background: var(--surface-2); border: 1px solid var(--border); }}
    .metric-card span {{ color: var(--muted); font-size: 13px; font-weight: 850; }} .metric-card strong {{ display: block; margin: 10px 0 4px; font-size: 40px; letter-spacing: -.04em; }} .metric-card small {{ color: #86efac; }} .metric-card a {{ display: inline-block; margin-top: 12px; color: var(--blue); text-decoration: none; font-weight: 900; }}
    .tools-grid {{ display: flex; flex-wrap: wrap; gap: 10px; }}
    .tool {{ border: 1px solid var(--border); border-radius: 16px; background: rgba(255,255,255,.045); color: white; padding: 12px 14px; font-weight: 900; }}
    .panel ul {{ list-style: none; padding: 0; margin: 14px 0 0; display: grid; gap: 10px; }}
    .panel li {{ display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 13px; border-radius: 18px; background: rgba(255,255,255,.04); border: 1px solid rgba(255,255,255,.04); }}
    .panel li p {{ margin: 0; color: #d9def0; }} .panel li span {{ color: var(--muted); font-size: 12px; }} .panel li b {{ color: var(--green); }} .panel li em {{ color: #bbf7d0; background: rgba(34,197,94,.14); border-radius: 999px; padding: 4px 9px; font-style: normal; font-size: 12px; font-weight: 900; }}
    .health-ring {{ width: 174px; height: 174px; margin: 18px auto 12px; border-radius: 50%; background: conic-gradient(var(--green) {health_percent}%, rgba(255,255,255,.08) 0); display: grid; place-items: center; box-shadow: 0 0 52px rgba(34,197,94,.13); }}
    .health-ring span {{ width: 122px; height: 122px; display: grid; place-items: center; border-radius: 50%; background: var(--surface); font-size: 36px; font-weight: 950; }}
    .muted {{ color: var(--muted); }}
    @media (max-width: 1260px) {{ .dashboard-shell {{ grid-template-columns: 282px 1fr; }} .rightbar {{ grid-column: 2; padding: 0 30px 30px; grid-template-columns: repeat(2, minmax(0,1fr)); }} }}
    @media (max-width: 900px) {{ .dashboard-shell {{ display: block; }} .sidebar {{ position: static; height: auto; }} .main, .rightbar {{ padding: 22px; }} .topbar, .top-actions {{ align-items: stretch; flex-direction: column; }} .search {{ width: 100%; }} .quick-grid, .metrics-grid, .process-flow, .rightbar {{ grid-template-columns: 1fr; }} .process-flow::before {{ display: none; }} }}
  </style>
</head>
<body>
  <div class="dashboard-shell">
    <aside class="sidebar" aria-label="Navegação principal">
      <div class="brand"><div class="brand-mark">A</div><div>AUTOMAÇÃO<small>v1.0</small></div></div>
      <nav class="nav-group"><button class="nav-item active">Início</button></nav>
      <nav class="nav-group"><small>CRIAR</small><button class="nav-item">Campanha</button><button class="nav-item">Criativos</button><button class="nav-item">Vídeos</button><button class="nav-item">Sites/Landing Pages</button><button class="nav-item">TikTok Pack</button><button class="nav-item">Brain de Anúncios</button></nav>
      <nav class="nav-group"><small>GERENCIAR</small><button class="nav-item">Campanhas</button><button class="nav-item">Uploads</button><button class="nav-item">Relatórios</button><button class="nav-item">Automações</button></nav>
      <nav class="nav-group"><small>INTELIGÊNCIA</small><button class="nav-item">Mineração</button><button class="nav-item">Análises</button><button class="nav-item">Insights</button></nav>
      <nav class="nav-group"><small>CONFIGURAÇÕES</small><button class="nav-item">Integrações</button><button class="nav-item">Configurações</button></nav>
      <footer class="assistant-card"><strong>DOUGLAS PRIME</strong><p>Assistente Executivo</p><div class="profile"><div class="avatar">D</div><div>Douglas<br><span>Administrador</span></div></div></footer>
    </aside>
    <main class="main">
      <header class="topbar">
        <div><p class="hello">Olá, {user_name}!</p><h1>O que vamos <span class="gradient-word">criar</span> hoje?</h1></div>
        <div class="top-actions"><input class="search" aria-label="Buscar" placeholder="Buscar campanhas, alertas e tarefas"><button class="icon-button">🔔</button><button class="icon-button">?</button><div class="system-card">{escape(system_label)}</div></div>
      </header>
      <section class="section"><div class="section-head"><h2>Ações rápidas</h2><div class="mode-pills">{mode_pills}</div></div><div class="quick-grid">{quick_actions}</div></section>
      <section class="section process-card"><div class="section-head"><h2>Como funciona?</h2><span class="muted">fluxo operacional seguro</span></div><div class="process-flow">{process_steps}</div></section>
      <section class="section overview-card" id="visao-geral"><div class="section-head"><h2>Visão geral</h2><span class="muted">dados do snapshot operacional</span></div><div class="metrics-grid">{metrics}</div></section>
      <section class="section"><div class="section-head"><h2>Ferramentas rápidas</h2></div><div class="tools-grid"><button class="tool">🔐 Segurança</button><button class="tool">📋 Auditoria</button><button class="tool">⚙️ Filas</button><button class="tool">📡 Conectores</button><button class="tool">🧠 Insights</button></div></section>
    </main>
    <aside class="rightbar" aria-label="Painéis operacionais">
      <section class="panel"><h2>Atividades recentes</h2><ul>{_activity_list(snapshot)}</ul></section>
      <section class="panel"><h2>Automações ativas</h2><ul>{_automation_list(snapshot)}</ul></section>
      <section class="panel"><h2>Saúde do sistema</h2><div class="health-ring"><span>{health_percent}%</span></div><p class="muted">Status: {escape(snapshot['status'])} · Audit log: {escape(str(audit['hash_chain_ok']))}</p></section>
      <section class="panel"><h2>Alertas e bloqueios</h2><ul>{_blocker_list(snapshot)}<li><span>Credenciais carregadas</span><strong>{escape(str(connectors['credentials_loaded']))}</strong></li><li><span>Rede usada</span><strong>{escape(str(connectors['network_access_used']))}</strong></li></ul></section>
    </aside>
  </div>
</body>
</html>
"""


@router.get("/operational")
def get_operational_dashboard(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return operational_dashboard_snapshot(db)


@router.get("/operational/ui", response_class=HTMLResponse)
def get_operational_dashboard_ui(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    snapshot = operational_dashboard_snapshot(db)
    return HTMLResponse(_render_operational_dashboard_html(snapshot, current_user))
