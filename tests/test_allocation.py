"""
Unit tests for src/tools/allocation.py

Tests cover:
  - simulate_rebalance: trades sum to zero (no cash created or destroyed)
  - simulate_rebalance: after rebalancing, allocations move toward targets
  - simulate_rebalance: balanced portfolio produces only holds
  - allocate_contribution: total buys sum to contribution amount (±rounding)
  - allocate_contribution: money flows to underweight classes
  - allocate_contribution: zero contribution returns empty list
"""

import pytest

from src.models.schemas import Holding, Policy, Portfolio
from src.tools.allocation import allocate_contribution, simulate_rebalance


# ---------------------------------------------------------------------------
# Helpers
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
# simulate_rebalance tests
# ---------------------------------------------------------------------------


class TestSimulateRebalance:
    """Tests for simulate_rebalance() pure function."""

    def _net_flow(self, trades) -> float:
        """Sum of buys minus sum of sells. Should be ~0 for a rebalance."""
        total = 0.0
        for t in trades:
            if t.action == "buy":
                total += t.amount_usd
            elif t.action == "sell":
                total -= t.amount_usd
        return total

    def test_rebalance_net_flow_is_zero(self):
        """Buys and sells in a rebalance must net to zero — no cash is created."""
        portfolio = _make_portfolio([
            # US Equity overweight: 80% vs 60% target
            {"ticker": "VTI",  "asset_class": "US Equity",            "quantity": 80, "price": 100.0},
            {"ticker": "VXUS", "asset_class": "International Equity",  "quantity": 10, "price": 100.0},
            {"ticker": "BND",  "asset_class": "Bonds",                 "quantity": 10, "price": 100.0},
        ])
        policy = _make_policy()
        trades = simulate_rebalance(portfolio, policy)

        net = self._net_flow(trades)
        assert abs(net) < 1.0, f"Expected net flow ≈ 0, got {net:.2f}"

    def test_balanced_portfolio_produces_no_actionable_trades(self):
        """A portfolio exactly at target allocations needs no trades."""
        portfolio = _make_portfolio([
            {"ticker": "VTI",  "asset_class": "US Equity",            "quantity": 60, "price": 100.0},
            {"ticker": "VXUS", "asset_class": "International Equity",  "quantity": 20, "price": 100.0},
            {"ticker": "BND",  "asset_class": "Bonds",                 "quantity": 20, "price": 100.0},
        ])
        policy = _make_policy()
        trades = simulate_rebalance(portfolio, policy)
        actionable = [t for t in trades if t.action != "hold"]
        assert len(actionable) == 0, (
            f"Expected no actionable trades for balanced portfolio, got: {actionable}"
        )

    def test_overweight_class_gets_sell_trades(self):
        """Asset class above target should produce sell trades."""
        # US Equity = 80%, target = 60% → should sell
        portfolio = _make_portfolio([
            {"ticker": "VTI",  "asset_class": "US Equity",            "quantity": 80, "price": 100.0},
            {"ticker": "VXUS", "asset_class": "International Equity",  "quantity": 10, "price": 100.0},
            {"ticker": "BND",  "asset_class": "Bonds",                 "quantity": 10, "price": 100.0},
        ])
        policy = _make_policy()
        trades = simulate_rebalance(portfolio, policy)
        us_trades = [t for t in trades if t.asset_class == "US Equity" and t.action == "sell"]
        assert len(us_trades) > 0

    def test_underweight_class_gets_buy_trades(self):
        """Asset class below target should produce buy trades."""
        # Bonds = 5%, target = 20% → should buy
        portfolio = _make_portfolio([
            {"ticker": "VTI",  "asset_class": "US Equity",            "quantity": 75, "price": 100.0},
            {"ticker": "VXUS", "asset_class": "International Equity",  "quantity": 20, "price": 100.0},
            {"ticker": "BND",  "asset_class": "Bonds",                 "quantity": 5,  "price": 100.0},
        ])
        policy = _make_policy()
        trades = simulate_rebalance(portfolio, policy)
        bond_buys = [t for t in trades if t.asset_class == "Bonds" and t.action == "buy"]
        assert len(bond_buys) > 0

    def test_rebalance_moves_allocations_toward_target(self):
        """After applying rebalance trades, allocations should be closer to targets."""
        portfolio = _make_portfolio([
            {"ticker": "VTI",  "asset_class": "US Equity",            "quantity": 80, "price": 100.0},
            {"ticker": "VXUS", "asset_class": "International Equity",  "quantity": 10, "price": 100.0},
            {"ticker": "BND",  "asset_class": "Bonds",                 "quantity": 10, "price": 100.0},
        ])
        policy = _make_policy()
        trades = simulate_rebalance(portfolio, policy)

        # Compute post-rebalance values by applying trades
        values = {h.ticker: h.market_value for h in portfolio.holdings}
        ac_map = {h.ticker: h.asset_class for h in portfolio.holdings}
        for t in trades:
            if t.action == "buy":
                values[t.ticker] = values.get(t.ticker, 0) + t.amount_usd
            elif t.action == "sell":
                values[t.ticker] = max(0, values.get(t.ticker, 0) - t.amount_usd)

        total = sum(values.values())
        ac_totals: dict[str, float] = {}
        for ticker, val in values.items():
            ac = ac_map[ticker]
            ac_totals[ac] = ac_totals.get(ac, 0) + val

        for ac, target in policy.targets.items():
            actual_before = portfolio.asset_class_allocations.get(ac, 0)
            actual_after = ac_totals.get(ac, 0) / total if total > 0 else 0
            drift_before = abs(actual_before - target)
            drift_after = abs(actual_after - target)
            assert drift_after <= drift_before + 0.01, (
                f"{ac}: drift did not improve after rebalance "
                f"(before={drift_before:.1%}, after={drift_after:.1%})"
            )

    def test_empty_portfolio_returns_empty_list(self):
        """Empty portfolio should return an empty trades list."""
        portfolio = Portfolio(holdings=[])
        policy = _make_policy()
        trades = simulate_rebalance(portfolio, policy)
        assert trades == []


# ---------------------------------------------------------------------------
# allocate_contribution tests
# ---------------------------------------------------------------------------


class TestAllocateContribution:
    """Tests for allocate_contribution() pure function."""

    def test_total_buys_sum_to_contribution(self):
        """All buy amounts must sum to the contribution (within rounding tolerance)."""
        portfolio = _make_portfolio([
            {"ticker": "VTI",  "asset_class": "US Equity",            "quantity": 60, "price": 100.0},
            {"ticker": "VXUS", "asset_class": "International Equity",  "quantity": 20, "price": 100.0},
            {"ticker": "BND",  "asset_class": "Bonds",                 "quantity": 20, "price": 100.0},
        ])
        policy = _make_policy()
        contribution = 5000.0

        trades = allocate_contribution(portfolio, policy, contribution)
        total_buys = sum(t.amount_usd for t in trades if t.action == "buy")
        assert abs(total_buys - contribution) < 5.0, (
            f"Expected buys to sum to {contribution:.2f}, got {total_buys:.2f}"
        )

    def test_contribution_favors_underweight_classes(self):
        """More money should flow to underweight asset classes."""
        # Bonds = 5% vs 20% target — severely underweight
        portfolio = _make_portfolio([
            {"ticker": "VTI",  "asset_class": "US Equity",            "quantity": 75, "price": 100.0},
            {"ticker": "VXUS", "asset_class": "International Equity",  "quantity": 20, "price": 100.0},
            {"ticker": "BND",  "asset_class": "Bonds",                 "quantity": 5,  "price": 100.0},
        ])
        policy = _make_policy()
        contribution = 5000.0

        trades = allocate_contribution(portfolio, policy, contribution)
        bond_buys = sum(t.amount_usd for t in trades if t.asset_class == "Bonds")
        us_buys = sum(t.amount_usd for t in trades if t.asset_class == "US Equity")

        assert bond_buys >= us_buys, (
            f"Expected bonds (underweight) to receive >= US Equity allocation, "
            f"bonds={bond_buys:.2f}, US={us_buys:.2f}"
        )

    def test_zero_contribution_returns_empty_list(self):
        """Zero contribution should produce no trades."""
        portfolio = _make_portfolio([
            {"ticker": "VTI",  "asset_class": "US Equity",            "quantity": 60, "price": 100.0},
            {"ticker": "VXUS", "asset_class": "International Equity",  "quantity": 20, "price": 100.0},
            {"ticker": "BND",  "asset_class": "Bonds",                 "quantity": 20, "price": 100.0},
        ])
        policy = _make_policy()
        trades = allocate_contribution(portfolio, policy, 0.0)
        assert trades == []

    def test_negative_contribution_returns_empty_list(self):
        """Negative contribution should produce no trades (guard against bad input)."""
        portfolio = _make_portfolio([
            {"ticker": "VTI", "asset_class": "US Equity", "quantity": 60, "price": 100.0},
            {"ticker": "BND", "asset_class": "Bonds",     "quantity": 40, "price": 100.0},
        ])
        policy = _make_policy(targets={"US Equity": 0.60, "Bonds": 0.40})
        trades = allocate_contribution(portfolio, policy, -500.0)
        assert trades == []

    def test_all_trades_are_buy_actions(self):
        """Contribution allocation should only produce buy trades, never sells."""
        portfolio = _make_portfolio([
            {"ticker": "VTI",  "asset_class": "US Equity",            "quantity": 60, "price": 100.0},
            {"ticker": "VXUS", "asset_class": "International Equity",  "quantity": 20, "price": 100.0},
            {"ticker": "BND",  "asset_class": "Bonds",                 "quantity": 20, "price": 100.0},
        ])
        policy = _make_policy()
        trades = allocate_contribution(portfolio, policy, 3000.0)
        non_buys = [t for t in trades if t.action != "buy"]
        assert len(non_buys) == 0, f"Expected only buy trades, got: {non_buys}"
