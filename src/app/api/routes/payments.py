"""Pagamentos: integracao de checkout (Hotmart/Kiwify/Stripe link) + webhook de vendas.

Modelo da metodologia Renda em Dolar: o produto e cadastrado na plataforma de
pagamento (Hotmart recomendada — checkout com order bumps nativos), e o site
gerado pela ferramenta aponta o botao de compra para o link do checkout.

Este modulo entrega:
- GET  /payments/status            -> configuracao atual
- POST /payments/hotmart/webhook   -> recebe postback de venda (compra aprovada,
  reembolso etc.) e registra para alimentar as metricas do funil
- GET  /payments/sales             -> vendas registradas (resumo + ultimas)
"""

from __future__ import annotations

import os
from collections import Counter
from datetime import datetime, timezone

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

router = APIRouter(prefix="/payments", tags=["Pagamentos e Vendas"])

# Registro em memoria (serverless: por instancia). O evento tambem e logado,
# e o resumo alimenta o diagnostico de funil.
_SALES: list[dict] = []


@router.get("/status")
def status():
    return {
        "status": "ok",
        "modelo": "checkout externo (Hotmart recomendada) + webhook de vendas",
        "hottok_configurado": os.getenv("HOTMART_HOTTOK") is not None,
        "como_configurar": [
            "1. Cadastre o produto na Hotmart com preco US$ 6,90 e 3-4 order bumps",
            "2. Copie o link do checkout e passe no campo checkout_url do pipeline/site",
            "3. Na Hotmart: Ferramentas > Webhook > URL: https://projeto-automacao-ten.vercel.app/api/v1/payments/hotmart/webhook",
            "4. (Opcional) defina HOTMART_HOTTOK na Vercel para validar a origem dos eventos",
        ],
    }


@router.post("/hotmart/webhook")
async def hotmart_webhook(request: Request):
    """Recebe eventos da Hotmart (PURCHASE_APPROVED, PURCHASE_REFUNDED, etc.)."""
    hottok_esperado = os.getenv("HOTMART_HOTTOK")
    hottok_recebido = request.headers.get("X-Hotmart-Hottok") or request.headers.get("x-hotmart-hottok")
    if hottok_esperado and hottok_recebido != hottok_esperado:
        return {"status": "rejected", "reason": "hottok invalido"}

    try:
        body = await request.json()
    except Exception:
        body = {}

    data = body.get("data") or {}
    purchase = data.get("purchase") or {}
    product = data.get("product") or {}
    evento = {
        "event": body.get("event") or "unknown",
        "product": product.get("name"),
        "price": (purchase.get("price") or {}).get("value"),
        "currency": (purchase.get("price") or {}).get("currency_value"),
        "transaction": purchase.get("transaction"),
        "received_at": datetime.now(timezone.utc).isoformat(),
    }
    _SALES.append(evento)
    if len(_SALES) > 500:
        del _SALES[:-500]
    return {"status": "ok", "registered": evento["event"]}


@router.get("/sales")
def sales():
    aprovadas = [s for s in _SALES if s["event"] == "PURCHASE_APPROVED"]
    por_produto = Counter(s["product"] for s in aprovadas if s.get("product"))
    receita = sum(float(s["price"] or 0) for s in aprovadas)
    return {
        "status": "ok",
        "total_eventos": len(_SALES),
        "vendas_aprovadas": len(aprovadas),
        "receita_registrada": round(receita, 2),
        "por_produto": dict(por_produto),
        "ultimos_eventos": _SALES[-20:],
        "nota": "Registro em memoria por instancia serverless; a fonte oficial e o painel da Hotmart.",
    }


class CheckoutLinkRequest(BaseModel):
    product_name: str = Field(..., min_length=2)
    checkout_url: str = Field(..., min_length=8, description="Link do checkout (Hotmart/Kiwify/Stripe)")
    order_bump_urls: list[str] = Field(default_factory=list)


@router.post("/validate-checkout")
def validate_checkout(payload: CheckoutLinkRequest):
    """Confere se o link de checkout responde antes de colocar no site/anuncio."""
    import httpx

    try:
        with httpx.Client(timeout=15, follow_redirects=True) as client:
            r = client.get(payload.checkout_url)
        ok = r.status_code < 400
        return {
            "status": "ok" if ok else "error",
            "http_status": r.status_code,
            "final_url": str(r.url),
            "message": "Checkout acessivel" if ok else "Checkout retornou erro — confira o link na plataforma de pagamento",
        }
    except Exception as exc:
        return {"status": "error", "message": f"Nao consegui acessar o checkout: {exc}"}
