"""Motor de escala V4/V5/V6 com protecao da fase de aprendizado do Facebook.

Regra central (por que este motor existe): quando um anuncio esta indo bem e o
orcamento sobe demais ou o conjunto e editado, o algoritmo da Meta reinicia a
fase de aprendizado e a entrega despenca. Este motor NUNCA recomenda aumento
acima de 20% por ajuste, exige intervalo minimo de 24h entre ajustes e prefere
duplicar conjuntos vencedores a mexer neles.

V4 = escala controlada. V5 = otimizacao inteligente (diagnostico de gargalo e
fadiga criativa). V6 = dominacao (expansao geo/publico com portfolio de
criativos vencedores).
"""

from __future__ import annotations

from typing import Any

# Limites de seguranca da entrega
MAX_BUDGET_INCREASE_PCT = 20        # nunca mais de 20% por ajuste
MIN_HOURS_BETWEEN_CHANGES = 24      # 1 ajuste por dia no maximo
LEARNING_PHASE_CONVERSIONS = 50     # ~50 conversoes/semana = aprendizado concluido
FREQUENCY_FATIGUE = 3.0             # frequencia >= 3 = criativo saturando
ROAS_FLOOR_SCALE = 1.5              # abaixo disso nao escala
CPA_TOLERANCE_PCT = 20              # CPA ate 20% acima da meta e tolerado em escala


def _n(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _delivery_guardrails(metrics: dict[str, Any]) -> tuple[list[str], list[str]]:
    """Retorna (avisos, bloqueios) baseado nas metricas — atencao maxima aqui."""
    warnings: list[str] = []
    blocks: list[str] = []

    conversions_week = _n(metrics.get("conversions_last_7d"))
    roas = _n(metrics.get("roas"))
    frequency = _n(metrics.get("frequency"))
    hours_since_change = _n(metrics.get("hours_since_last_change"))
    cpa = _n(metrics.get("cpa"))
    target_cpa = _n(metrics.get("target_cpa"))
    ctr_trend = _n(metrics.get("ctr_change_pct"))  # variacao % do CTR vs semana anterior

    if conversions_week is not None and conversions_week < LEARNING_PHASE_CONVERSIONS:
        blocks.append(
            f"Conjunto ainda em fase de aprendizado ({conversions_week:.0f} conversoes em 7 dias, "
            f"minimo {LEARNING_PHASE_CONVERSIONS}). Escalar agora REINICIA o aprendizado e derruba a entrega."
        )
    if roas is not None and roas < ROAS_FLOOR_SCALE:
        blocks.append(f"ROAS {roas:.2f} abaixo do piso de escala ({ROAS_FLOOR_SCALE}). Nao colocar mais dinheiro.")
    if hours_since_change is not None and hours_since_change < MIN_HOURS_BETWEEN_CHANGES:
        blocks.append(
            f"Ultimo ajuste ha {hours_since_change:.0f}h. Esperar {MIN_HOURS_BETWEEN_CHANGES}h entre ajustes "
            "para nao resetar o aprendizado."
        )
    if cpa is not None and target_cpa is not None and cpa > target_cpa * (1 + CPA_TOLERANCE_PCT / 100):
        blocks.append(f"CPA R$ {cpa:.2f} estourou a meta (R$ {target_cpa:.2f} +{CPA_TOLERANCE_PCT}%). Corrigir antes de escalar.")
    if frequency is not None and frequency >= FREQUENCY_FATIGUE:
        warnings.append(f"Frequencia {frequency:.1f} indica fadiga: publico ja viu demais. Trocar criativo antes de escalar.")
    if ctr_trend is not None and ctr_trend <= -20:
        warnings.append(f"CTR caiu {abs(ctr_trend):.0f}% vs semana anterior: sinal de saturacao do criativo.")

    return warnings, blocks


def v4_scale_plan(payload: dict[str, Any]) -> dict[str, Any]:
    """V4 - Escala controlada: mais dinheiro SEM derrubar a entrega."""
    metrics = payload.get("metrics") or {}
    budget = _n(payload.get("current_budget_brl")) or 100.0
    warnings, blocks = _delivery_guardrails(metrics)

    if blocks:
        return {
            "stage": "V4",
            "action": "NAO_ESCALAR",
            "blocked_reasons": blocks,
            "warnings": warnings,
            "recommendation": "Manter orcamento atual. Resolver os bloqueios acima antes de qualquer aumento.",
        }

    new_budget = round(budget * (1 + MAX_BUDGET_INCREASE_PCT / 100), 2)
    plan = {
        "stage": "V4",
        "action": "ESCALAR_VERTICAL_CONTROLADO",
        "warnings": warnings,
        "steps": [
            f"Aumentar orcamento de R$ {budget:.2f} para R$ {new_budget:.2f} (exatos +{MAX_BUDGET_INCREASE_PCT}%, nunca mais que isso).",
            f"NAO editar mais nada no conjunto (publico, criativo, posicionamento) — qualquer edicao reseta o aprendizado.",
            f"Aguardar {MIN_HOURS_BETWEEN_CHANGES}h e reavaliar CPA/ROAS antes do proximo aumento.",
            "Se quiser escalar mais rapido: DUPLICAR o conjunto vencedor com orcamento novo, mantendo o original intocado (escala horizontal).",
        ],
        "next_budget_brl": new_budget,
        "next_review_in_hours": MIN_HOURS_BETWEEN_CHANGES,
        "next_stage_if_positive": "V5",
    }
    return plan


def v5_optimize_plan(payload: dict[str, Any]) -> dict[str, Any]:
    """V5 - Otimizacao inteligente: achar o gargalo e a fadiga criativa."""
    metrics = payload.get("metrics") or {}
    warnings, blocks = _delivery_guardrails(metrics)

    connect = _n(metrics.get("connect_rate"))
    checkout = _n(metrics.get("checkout_rate"))
    purchase = _n(metrics.get("purchase_rate"))
    frequency = _n(metrics.get("frequency"))

    bottlenecks: list[dict[str, str]] = []
    if connect is not None and connect < 75:
        bottlenecks.append({"onde": "pagina", "problema": f"Connect rate {connect:.0f}% (<75%)",
                            "acao": "Melhorar velocidade da pagina, dominio e rastreamento. Nao mexer no anuncio."})
    if checkout is not None and checkout < 20:
        bottlenecks.append({"onde": "oferta", "problema": f"Checkout rate {checkout:.0f}% (<20%)",
                            "acao": "Revisar preco, promessa, prova social e CTA da pagina."})
    if purchase is not None and purchase < 2:
        bottlenecks.append({"onde": "finalizacao", "problema": f"Purchase rate {purchase:.1f}% (<2%)",
                            "acao": "Revisar checkout, frete, meios de pagamento e confianca."})
    if frequency is not None and frequency >= FREQUENCY_FATIGUE:
        bottlenecks.append({"onde": "criativo", "problema": f"Frequencia {frequency:.1f} (fadiga)",
                            "acao": "Lancar 2-3 criativos novos em conjunto DUPLICADO; nao substituir o criativo vencedor no conjunto original."})

    return {
        "stage": "V5",
        "action": "OTIMIZAR" if bottlenecks else "MANTER",
        "blocked_reasons": blocks,
        "warnings": warnings,
        "bottlenecks": bottlenecks,
        "recommendation": (
            "Corrigir os gargalos SEM editar o conjunto vencedor (toda edicao reseta o aprendizado). "
            "Testes sempre em conjuntos duplicados."
            if bottlenecks
            else "Nenhum gargalo critico. Funil saudavel — apto a avancar para V6."
        ),
        "next_stage_if_positive": "V6",
    }


def v6_dominate_plan(payload: dict[str, Any]) -> dict[str, Any]:
    """V6 - Dominacao: expansao geo/publico com criativos vencedores."""
    metrics = payload.get("metrics") or {}
    budget = _n(payload.get("current_budget_brl")) or 200.0
    current_countries = payload.get("current_countries") or ["BR"]
    warnings, blocks = _delivery_guardrails(metrics)

    if blocks:
        return {
            "stage": "V6",
            "action": "NAO_EXPANDIR",
            "blocked_reasons": blocks,
            "warnings": warnings,
            "recommendation": "Dominacao exige funil comprovado. Resolver bloqueios antes de expandir.",
        }

    expansion = [c for c in ["PT", "US", "ES", "MX", "FR", "DE"] if c not in current_countries][:3]
    return {
        "stage": "V6",
        "action": "EXPANDIR_CONTROLADO",
        "warnings": warnings,
        "steps": [
            "Manter a campanha original intocada — ela e a fonte de lucro; nenhuma edicao nela.",
            f"Criar campanhas NOVAS por pais ({', '.join(expansion)}), cada uma comecando com orcamento de teste "
            f"(R$ {max(25.0, round(budget * 0.25, 2)):.2f}/dia), nunca herdando o orcamento cheio.",
            "Usar somente os criativos vencedores comprovados (CTR e ROAS do historico).",
            "Cada pais novo passa pela escada de novo: V1 -> V2 -> V3 antes de escalar.",
            f"Na campanha original, seguir aumentos de no maximo {MAX_BUDGET_INCREASE_PCT}% a cada {MIN_HOURS_BETWEEN_CHANGES}h.",
        ],
        "geo_expansion": expansion,
        "next_stage_if_positive": "scale_continua",
    }
