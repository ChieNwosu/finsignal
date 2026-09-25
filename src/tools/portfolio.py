"""
Portfolio tool — loads and computes the synthetic portfolio.

This module is independently importable and runnable without the agent.
All arithmetic is deterministic Python; the LLM never touches these values.
"""

from __future__ import annotations

import json
from pathlib import Path

from src.models.schemas import Holding, Policy, Portfolio

# Resolve data directory relative to this file so imports work regardless
# of the working directory the caller uses.
_DATA_DIR = Path(__file__).resolve().parents[2] / "data"


def _load_raw_portfolio() -> dict:
    path = _DATA_DIR / "portfolio.json"
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _load_raw_scenarios() -> dict:
    path = _DATA_DIR / "scenarios.json"
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_policy() -> Policy:
    """Load the portfolio policy from data/policy.json."""
    path = _DATA_DIR / "policy.json"
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    return Policy(
        targets=raw["targets"],
        concentration_limit=raw["concentration_limit"],
        drift_threshold=raw["drift_threshold"],
    )


def load_portfolio(scenario: str = "baseline") -> tuple[Portfolio, float | None]:
    """
    Load the synthetic portfolio and apply any scenario overrides.

    Returns:
        (Portfolio, pending_contribution_usd | None)

    The Portfolio object has computed market values and allocation percentages.
    Scenario price overrides are applied before any calculations.
    """
    raw = _load_raw_portfolio()
    scenarios = _load_raw_scenarios()

    if scenario not in scenarios["scenarios"]:
        raise ValueError(
            f"Unknown scenario '{scenario}'. "
            f"Available: {list(scenarios['scenarios'].keys())}"
        )

    scene = scenarios["scenarios"][scenario]
    price_overrides: dict[str, float] = scene.get("price_overrides", {})
    pending_contribution: float | None = scene.get("pending_contribution")

    holdings: list[Holding] = []
    for h in raw["holdings"]:
        price = price_overrides.get(h["ticker"], h["price"])
        holdings.append(
            Holding(
                ticker=h["ticker"],
                name=h["name"],
                asset_class=h["asset_class"],
                quantity=float(h["quantity"]),
                price=float(price),
            )
        )

    return Portfolio(holdings=holdings), pending_contribution
