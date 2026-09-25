"""
Unit tests for src/tools/constraints.py

Tests cover:
  - Concentration check: pass when under limit
  - Concentration check: fail when over limit
  - Drift check: pass when within threshold
  - Drift check: fail when beyond threshold
  - any_failures() helper
"""

import pytest

from src.models.schemas import Holding, Policy, Portfolio
from src.tools.constraints import any_failures, check_constraints


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_policy(
    targets: dict | None = None,
    concentration_limit: float = 0.25,
    drift_threshold: float = 0.05,
) -> Policy:
    if targets is None:
        targets = {"US Equity": 0.60, "International Equity": 0.20, "Bonds": 0.20}
    return Policy(
        targets=targets,
        concentration_limit=concentration_limit,
        drift_threshold=drift_threshold,
    )


def _make_portfolio(holdings: list[dict]) -> Portfolio:
    return Portfolio(
        holdings=[
            Holding(
                ticker=h["ticker"],
                name=h.get("name", h["ticker"]),
                asset_class=h["asset_class"],
                quantity=h["quantity"],
                price=h["price"],
            )
            for h in holdings
        ]
    )


# ---------------------------------------------------------------------------
# Concentration tests
# ---------------------------------------------------------------------------


class TestConcentrationCheck:
    """Tests for the per-holding concentration limit rule."""

    def test_passes_when_all_holdings_under_limit(self):
        """Portfolio with no oversized holding should pass concentration checks."""
        portfolio = _make_portfolio([
            {"ticker": "AAPL", "asset_class": "US Equity", "quantity": 10, "price": 100.0},
            {"ticker": "MSFT", "asset_class": "US Equity", "quantity": 10, "price": 100.0},
            {"ticker": "VTI",  "asset_class": "US Equity", "quantity": 10, "price": 100.0},
            {"ticker": "BND",  "asset_class": "Bonds",     "quantity": 10, "price": 100.0},
            {"ticker": "VXUS", "asset_class": "International Equity", "quantity": 10, "price": 100.0},
        ])
        # Each holding = 20% of 500 total — under the 25% limit
        policy = _make_policy(concentration_limit=0.25)
        results = check_constraints(portfolio, policy)
        conc_results = [r for r in results if r.rule == "Concentration Limit"]

        assert all(r.passed for r in conc_results), (
            f"Expected all concentration checks to pass, but failures: "
            f"{[r.detail for r in conc_results if not r.passed]}"
        )

    def test_fails_when_single_holding_exceeds_limit(self):
        """A holding that exceeds the concentration limit should fail."""
        portfolio = _make_portfolio([
            # AAPL = 300 / 500 = 60% — well over 25% limit
            {"ticker": "AAPL", "asset_class": "US Equity", "quantity": 30, "price": 100.0},
            {"ticker": "BND",  "asset_class": "Bonds",     "quantity": 10, "price": 100.0},
            {"ticker": "VXUS", "asset_class": "International Equity", "quantity": 10, "price": 100.0},
        ])
        policy = _make_policy(concentration_limit=0.25)
        results = check_constraints(portfolio, policy)
        conc_results = [r for r in results if r.rule == "Concentration Limit"]

        aapl_result = next(r for r in conc_results if r.subject == "AAPL")
        assert not aapl_result.passed
        assert aapl_result.actual > aapl_result.limit

    def test_fails_only_oversized_holding(self):
        """Only the oversized holding should fail; others should pass."""
        portfolio = _make_portfolio([
            # AAPL = 400 / 700 ≈ 57% — over 25%
            {"ticker": "AAPL", "asset_class": "US Equity", "quantity": 40, "price": 100.0},
            # BND = 150 / 700 ≈ 21% — under 25%
            {"ticker": "BND",  "asset_class": "Bonds",     "quantity": 15, "price": 100.0},
            # VXUS = 150 / 700 ≈ 21% — under 25%
            {"ticker": "VXUS", "asset_class": "International Equity", "quantity": 15, "price": 100.0},
        ])
        policy = _make_policy(concentration_limit=0.25)
        results = check_constraints(portfolio, policy)
        conc_results = {r.subject: r for r in results if r.rule == "Concentration Limit"}

        assert not conc_results["AAPL"].passed
        assert conc_results["BND"].passed
        assert conc_results["VXUS"].passed

    def test_boundary_exactly_at_limit_passes(self):
        """A holding exactly at the concentration limit should pass (≤ not <)."""
        # Two equal holdings = 50% each. Limit = 0.50
        portfolio = _make_portfolio([
            {"ticker": "A", "asset_class": "US Equity", "quantity": 10, "price": 100.0},
            {"ticker": "B", "asset_class": "Bonds",     "quantity": 10, "price": 100.0},
        ])
        policy = _make_policy(
            targets={"US Equity": 0.50, "Bonds": 0.50},
            concentration_limit=0.50,
        )
        results = check_constraints(portfolio, policy)
        conc_results = [r for r in results if r.rule == "Concentration Limit"]
        assert all(r.passed for r in conc_results)


# ---------------------------------------------------------------------------
# Drift tests
# ---------------------------------------------------------------------------


class TestDriftCheck:
    """Tests for the asset-class drift threshold rule."""

    def test_passes_when_all_classes_within_threshold(self):
        """Portfolio at exact targets should produce no drift failures."""
        # 60% US Eq, 20% Intl Eq, 20% Bonds — matches policy exactly
        portfolio = _make_portfolio([
            {"ticker": "VTI",  "asset_class": "US Equity",             "quantity": 60, "price": 100.0},
            {"ticker": "VXUS", "asset_class": "International Equity",   "quantity": 20, "price": 100.0},
            {"ticker": "BND",  "asset_class": "Bonds",                  "quantity": 20, "price": 100.0},
        ])
        policy = _make_policy(drift_threshold=0.05)
        results = check_constraints(portfolio, policy)
        drift_results = [r for r in results if r.rule == "Drift Threshold"]

        assert all(r.passed for r in drift_results), (
            f"Expected no drift failures but got: "
            f"{[r.detail for r in drift_results if not r.passed]}"
        )

    def test_fails_when_class_drifts_beyond_threshold(self):
        """An asset class drifted more than the threshold should fail."""
        # US Equity = 80 / 100 = 80% (target 60% → drift = 20% >> 5% threshold)
        portfolio = _make_portfolio([
            {"ticker": "VTI",  "asset_class": "US Equity",            "quantity": 80, "price": 100.0},
            {"ticker": "VXUS", "asset_class": "International Equity",  "quantity": 10, "price": 100.0},
            {"ticker": "BND",  "asset_class": "Bonds",                 "quantity": 10, "price": 100.0},
        ])
        policy = _make_policy(drift_threshold=0.05)
        results = check_constraints(portfolio, policy)
        drift_results = {r.subject: r for r in results if r.rule == "Drift Threshold"}

        assert not drift_results["US Equity"].passed
        assert abs(drift_results["US Equity"].actual - 0.80) < 0.001

    def test_passes_when_drift_exactly_at_threshold(self):
        """Drift exactly equal to the threshold should pass (≤ not <)."""
        # US Equity = 65/100 = 65%, target = 60% → drift = 5% = threshold → pass
        # Two holdings in US Equity so neither single holding exceeds the 25% limit
        portfolio = _make_portfolio([
            {"ticker": "VTI",  "asset_class": "US Equity",            "quantity": 35, "price": 100.0},
            {"ticker": "SPY",  "asset_class": "US Equity",            "quantity": 30, "price": 100.0},
            {"ticker": "VXUS", "asset_class": "International Equity",  "quantity": 20, "price": 100.0},
            {"ticker": "BND",  "asset_class": "Bonds",                 "quantity": 15, "price": 100.0},
        ])
        policy = _make_policy(drift_threshold=0.05)
        results = check_constraints(portfolio, policy)
        drift_results = {r.subject: r for r in results if r.rule == "Drift Threshold"}

        assert drift_results["US Equity"].passed

    def test_fails_underweight_as_well_as_overweight(self):
        """Drift should be detected in both directions."""
        # Bonds = 5%, target = 20% → drift = −15% → fail
        portfolio = _make_portfolio([
            {"ticker": "VTI",  "asset_class": "US Equity",            "quantity": 75, "price": 100.0},
            {"ticker": "VXUS", "asset_class": "International Equity",  "quantity": 20, "price": 100.0},
            {"ticker": "BND",  "asset_class": "Bonds",                 "quantity": 5,  "price": 100.0},
        ])
        policy = _make_policy(drift_threshold=0.05)
        results = check_constraints(portfolio, policy)
        drift_results = {r.subject: r for r in results if r.rule == "Drift Threshold"}

        assert not drift_results["Bonds"].passed


# ---------------------------------------------------------------------------
# any_failures helper
# ---------------------------------------------------------------------------


class TestAnyFailures:
    def test_returns_false_when_all_pass(self):
        # Four holdings, each ~15-20% — all under the 25% concentration limit
        # Asset class totals match policy targets exactly
        portfolio = _make_portfolio([
            {"ticker": "VTI",  "asset_class": "US Equity",            "quantity": 30, "price": 100.0},
            {"ticker": "QQQ",  "asset_class": "US Equity",            "quantity": 30, "price": 100.0},
            {"ticker": "VXUS", "asset_class": "International Equity",  "quantity": 20, "price": 100.0},
            {"ticker": "BND",  "asset_class": "Bonds",                 "quantity": 20, "price": 100.0},
        ])
        # Raise concentration limit to 35% so 30% holdings pass
        policy = _make_policy(concentration_limit=0.35)
        results = check_constraints(portfolio, policy)
        assert not any_failures(results)

    def test_returns_true_when_any_fail(self):
        portfolio = _make_portfolio([
            # AAPL = 90% — way over concentration limit
            {"ticker": "AAPL", "asset_class": "US Equity",            "quantity": 90, "price": 100.0},
            {"ticker": "BND",  "asset_class": "Bonds",                "quantity": 5,  "price": 100.0},
            {"ticker": "VXUS", "asset_class": "International Equity", "quantity": 5,  "price": 100.0},
        ])
        policy = _make_policy(concentration_limit=0.25)
        results = check_constraints(portfolio, policy)
        assert any_failures(results)
