"""
Pydantic models for FinSignal.

All data crossing tool boundaries is validated here.
The LLM never touches these values — they are computed deterministically
in the tool layer and passed through as structured objects.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, computed_field, model_validator


# ---------------------------------------------------------------------------
# Portfolio models
# ---------------------------------------------------------------------------


class Holding(BaseModel):
    """A single security position in the portfolio."""

    ticker: str
    name: str
    asset_class: str
    quantity: float
    price: float  # current price per share (synthetic / scenario-adjusted)

    @computed_field  # type: ignore[misc]
    @property
    def market_value(self) -> float:
        return round(self.quantity * self.price, 2)


class Portfolio(BaseModel):
    """The full portfolio with computed allocation percentages."""

    holdings: list[Holding]

    @computed_field  # type: ignore[misc]
    @property
    def total_value(self) -> float:
        return round(sum(h.market_value for h in self.holdings), 2)

    @computed_field  # type: ignore[misc]
    @property
    def holding_allocations(self) -> dict[str, float]:
        """Per-ticker allocation as a fraction of total portfolio value."""
        if self.total_value == 0:
            return {}
        return {
            h.ticker: round(h.market_value / self.total_value, 6)
            for h in self.holdings
        }

    @computed_field  # type: ignore[misc]
    @property
    def asset_class_allocations(self) -> dict[str, float]:
        """Per-asset-class allocation as a fraction of total portfolio value."""
        if self.total_value == 0:
            return {}
        totals: dict[str, float] = {}
        for h in self.holdings:
            totals[h.asset_class] = totals.get(h.asset_class, 0.0) + h.market_value
        return {ac: round(val / self.total_value, 6) for ac, val in totals.items()}


# ---------------------------------------------------------------------------
# Policy model
# ---------------------------------------------------------------------------


class Policy(BaseModel):
    """User-defined portfolio policy rules."""

    targets: dict[str, float]      # asset_class -> target fraction (0–1)
    concentration_limit: float     # max fraction for any single holding (0–1)
    drift_threshold: float         # max allowed deviation from target before action (0–1)

    @model_validator(mode="after")
    def validate_targets_sum(self) -> "Policy":
        total = sum(self.targets.values())
        if not (0.9999 <= total <= 1.0001):
            raise ValueError(
                f"Policy targets must sum to 1.0, got {total:.4f}"
            )
        return self


# ---------------------------------------------------------------------------
# Constraint results
# ---------------------------------------------------------------------------


class ConstraintResult(BaseModel):
    """Outcome of a single policy constraint check."""

    rule: str               # human-readable rule name
    passed: bool
    actual: float           # the measured value (fraction)
    limit: float            # the policy limit (fraction)
    subject: str            # ticker or asset class that was checked
    detail: str             # one-line explanation


# ---------------------------------------------------------------------------
# Rebalance / allocation
# ---------------------------------------------------------------------------


class RebalanceTrade(BaseModel):
    """A simulated trade needed to move toward target allocation."""

    ticker: str
    asset_class: str
    action: Literal["buy", "sell", "hold"]
    amount_usd: float       # absolute dollar amount (always positive)
    current_pct: float      # actual allocation before trade (fraction)
    target_pct: float       # target allocation (fraction)


# ---------------------------------------------------------------------------
# Decision brief
# ---------------------------------------------------------------------------


class DecisionBrief(BaseModel):
    """The agent's output — surfaced only when human judgment is required."""

    requires_action: bool
    title: str
    body: str
    trades: list[RebalanceTrade] = []
    constraint_failures: list[ConstraintResult] = []
