"""
Constraints tool — checks portfolio holdings against policy rules.

Two checks are performed:
  1. Concentration check  — no single holding may exceed policy.concentration_limit
  2. Drift check          — no asset class may deviate from its target by more
                            than policy.drift_threshold

This module is independently importable and testable without the agent.
All logic is deterministic Python.
"""

from __future__ import annotations

from src.models.schemas import ConstraintResult, Policy, Portfolio


def check_constraints(portfolio: Portfolio, policy: Policy) -> list[ConstraintResult]:
    """
    Evaluate all policy constraints against the current portfolio.

    Returns a list of ConstraintResult objects — one per rule checked.
    A result with passed=False means the portfolio violates that rule.
    """
    results: list[ConstraintResult] = []
    results.extend(_check_concentration(portfolio, policy))
    results.extend(_check_drift(portfolio, policy))
    return results


def _check_concentration(
    portfolio: Portfolio, policy: Policy
) -> list[ConstraintResult]:
    """
    Check that no single holding exceeds the concentration limit.

    One ConstraintResult is produced per holding.
    """
    results: list[ConstraintResult] = []
    allocations = portfolio.holding_allocations

    for holding in portfolio.holdings:
        actual = allocations.get(holding.ticker, 0.0)
        passed = actual <= policy.concentration_limit
        results.append(
            ConstraintResult(
                rule="Concentration Limit",
                passed=passed,
                actual=actual,
                limit=policy.concentration_limit,
                subject=holding.ticker,
                detail=(
                    f"{holding.ticker} is {actual:.1%} of portfolio "
                    f"(limit: {policy.concentration_limit:.0%})"
                ),
            )
        )

    return results


def _check_drift(portfolio: Portfolio, policy: Policy) -> list[ConstraintResult]:
    """
    Check that each asset class has not drifted beyond the drift threshold.

    One ConstraintResult is produced per target asset class in the policy.
    """
    results: list[ConstraintResult] = []
    actual_ac = portfolio.asset_class_allocations

    for asset_class, target in policy.targets.items():
        actual = actual_ac.get(asset_class, 0.0)
        deviation = round(abs(actual - target), 6)
        passed = deviation <= policy.drift_threshold
        direction = "overweight" if actual > target else "underweight"

        results.append(
            ConstraintResult(
                rule="Drift Threshold",
                passed=passed,
                actual=actual,
                limit=policy.drift_threshold,
                subject=asset_class,
                detail=(
                    f"{asset_class} is {actual:.1%} actual vs "
                    f"{target:.0%} target ({direction} by {deviation:.1%}, "
                    f"threshold: {policy.drift_threshold:.0%})"
                ),
            )
        )

    return results


def any_failures(results: list[ConstraintResult]) -> bool:
    """Convenience helper — True if at least one constraint failed."""
    return any(not r.passed for r in results)
