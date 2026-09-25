"""
Allocation tool — rebalance simulation and contribution allocation.

Two pure functions:
  simulate_rebalance      — computes trades to return to target allocations
  allocate_contribution   — allocates new cash to close allocation gaps

Both functions are deterministic, have no side effects, and never
connect to any external system. No real trades are executed.

This module is independently importable and testable without the agent.
"""

from __future__ import annotations

from src.models.schemas import Policy, Portfolio, RebalanceTrade

# Minimum trade size — ignore trivially small adjustments (< $1)
_MIN_TRADE_USD = 1.0


def simulate_rebalance(portfolio: Portfolio, policy: Policy) -> list[RebalanceTrade]:
    """
    Compute the trades required to bring the portfolio back to target allocations.

    For each asset class:
        trade_usd = (target_pct - actual_pct) * total_value

    Positive delta  → buy
    Negative delta  → sell
    Near-zero delta → hold (below _MIN_TRADE_USD threshold)

    Trades are expressed at the asset-class level and distributed across
    holdings within that class proportionally to their current weights.

    Returns a list of RebalanceTrade objects (one per holding, may include holds).
    """
    total = portfolio.total_value
    if total == 0:
        return []

    actual_ac = portfolio.asset_class_allocations

    # Build per-asset-class trade amounts
    ac_trade_usd: dict[str, float] = {}
    for asset_class, target in policy.targets.items():
        actual = actual_ac.get(asset_class, 0.0)
        delta = target - actual          # positive = buy, negative = sell
        ac_trade_usd[asset_class] = round(delta * total, 2)

    # Distribute each asset-class trade across its holdings proportionally
    trades: list[RebalanceTrade] = []

    # Group holdings by asset class
    ac_holdings: dict[str, list] = {}
    for h in portfolio.holdings:
        ac_holdings.setdefault(h.asset_class, []).append(h)

    holding_allocs = portfolio.holding_allocations

    for asset_class, holdings in ac_holdings.items():
        class_trade = ac_trade_usd.get(asset_class, 0.0)
        target_pct = policy.targets.get(asset_class, 0.0)
        actual_ac_pct = actual_ac.get(asset_class, 0.0)

        # Total market value of this asset class (used for proportional split)
        class_value = sum(h.market_value for h in holdings)

        for h in holdings:
            current_pct = holding_allocs.get(h.ticker, 0.0)

            if class_value > 0 and abs(class_trade) >= _MIN_TRADE_USD:
                # Distribute proportionally to each holding's share of the class
                weight = h.market_value / class_value
                holding_trade = round(class_trade * weight, 2)
            else:
                holding_trade = 0.0

            if holding_trade > _MIN_TRADE_USD:
                action = "buy"
            elif holding_trade < -_MIN_TRADE_USD:
                action = "sell"
            else:
                action = "hold"
                holding_trade = 0.0

            trades.append(
                RebalanceTrade(
                    ticker=h.ticker,
                    asset_class=asset_class,
                    action=action,
                    amount_usd=abs(holding_trade),
                    current_pct=current_pct,
                    target_pct=target_pct / max(len(holdings), 1),  # indicative per-holding target
                )
            )

    return trades


def allocate_contribution(
    portfolio: Portfolio, policy: Policy, contribution_usd: float
) -> list[RebalanceTrade]:
    """
    Allocate a new cash contribution to move the portfolio toward target allocations.

    Strategy: invest more in underweight asset classes.

    For each asset class:
        new_total = total_value + contribution_usd
        desired_value = target_pct * new_total
        current_value = actual_pct * total_value
        allocation = max(0, desired_value - current_value)

    The allocations are then normalized to sum to exactly contribution_usd.

    Returns a list of RebalanceTrade objects (buy actions only).
    """
    if contribution_usd <= 0:
        return []

    total = portfolio.total_value
    new_total = total + contribution_usd
    actual_ac = portfolio.asset_class_allocations

    # Compute raw allocation per asset class
    raw_allocs: dict[str, float] = {}
    for asset_class, target in policy.targets.items():
        desired = target * new_total
        current = actual_ac.get(asset_class, 0.0) * total
        raw_allocs[asset_class] = max(0.0, desired - current)

    raw_total = sum(raw_allocs.values())

    # Normalize to contribution_usd
    if raw_total == 0:
        # Portfolio is perfectly balanced — distribute pro-rata to targets
        normalized: dict[str, float] = {
            ac: round(target * contribution_usd, 2)
            for ac, target in policy.targets.items()
        }
    else:
        normalized = {
            ac: round((raw / raw_total) * contribution_usd, 2)
            for ac, raw in raw_allocs.items()
        }

    # Build trades — one per holding, distributed within asset class proportionally
    trades: list[RebalanceTrade] = []
    ac_holdings: dict[str, list] = {}
    for h in portfolio.holdings:
        ac_holdings.setdefault(h.asset_class, []).append(h)

    holding_allocs = portfolio.holding_allocations

    for asset_class, holdings in ac_holdings.items():
        class_amount = normalized.get(asset_class, 0.0)
        target_pct = policy.targets.get(asset_class, 0.0)
        class_value = sum(h.market_value for h in holdings)

        for h in holdings:
            current_pct = holding_allocs.get(h.ticker, 0.0)

            if class_value > 0 and class_amount >= _MIN_TRADE_USD:
                weight = h.market_value / class_value
                holding_amount = round(class_amount * weight, 2)
            elif len(holdings) > 0 and class_amount >= _MIN_TRADE_USD:
                holding_amount = round(class_amount / len(holdings), 2)
            else:
                holding_amount = 0.0

            if holding_amount >= _MIN_TRADE_USD:
                trades.append(
                    RebalanceTrade(
                        ticker=h.ticker,
                        asset_class=asset_class,
                        action="buy",
                        amount_usd=holding_amount,
                        current_pct=current_pct,
                        target_pct=target_pct / max(len(holdings), 1),
                    )
                )

    return trades
