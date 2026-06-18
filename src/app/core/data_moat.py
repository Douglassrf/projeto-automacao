from __future__ import annotations

import hashlib
from collections import Counter
from typing import Any

from app.core.global_miner_hub import global_miner_hub_local
from app.services.campaign_brain import CampaignBrainAgent


def _fingerprint(signal: dict[str, Any]) -> str:
    raw = "|".join(
        [
            str(signal.get("platform", "")),
            str(signal.get("country", "")),
            str(signal.get("creative", {}).get("headline", "")),
            str(signal.get("creative", {}).get("body", "")),
            str(signal.get("landing", {}).get("url", "")),
            str(signal.get("offer", {}).get("niche", "")),
        ]
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def data_moat_local_snapshot(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    miner = global_miner_hub_local(payload)
    signals = miner["normalized_preview"]
    fingerprints = [_fingerprint(signal) for signal in signals]
    niche_counts = Counter(signal["offer"]["niche"] for signal in signals)
    platform_counts = Counter(signal["platform"] for signal in signals)
    country_counts = Counter(signal["country"] for signal in signals)
    duplicate_count = len(fingerprints) - len(set(fingerprints))
    moat_score = min(
        100,
        miner["signals_accepted"] * 12
        + len(platform_counts) * 8
        + len(country_counts) * 6
        + len(niche_counts) * 6
        - duplicate_count * 10,
    )

    brain = CampaignBrainAgent()
    learning = brain.learn_after_campaign(
        {
            "product_name": "Data Moat Local",
            "niche": next(iter(niche_counts), "sem sinal"),
            "campaign_stage": "37L",
            "outcome": "moat_snapshot_ready" if signals else "insufficient_data",
            "lesson": "Data Moat deve criar fingerprints e estatisticas proprietarias antes de banco vetorial ou coleta externa.",
            "metrics": {
                "moat_score": moat_score,
                "fingerprints": len(set(fingerprints)),
                "duplicates": duplicate_count,
            },
        }
    )

    return {
        "mission": "37L",
        "status": "moat_snapshot_ready" if signals else "insufficient_data",
        "will_execute_real_action": False,
        "will_activate_spend": False,
        "network_access_used": False,
        "database_write_used": False,
        "moat_score": moat_score,
        "fingerprints": fingerprints,
        "unique_fingerprints": len(set(fingerprints)),
        "duplicate_count": duplicate_count,
        "platform_counts": dict(platform_counts),
        "country_counts": dict(country_counts),
        "niche_counts": dict(niche_counts),
        "miner_summary": {
            "signals_received": miner["signals_received"],
            "signals_accepted": miner["signals_accepted"],
            "signals_blocked": miner["signals_blocked"],
        },
        "brian_learning": {
            "stored": learning["stored"],
            "message": learning["message"],
        },
    }
