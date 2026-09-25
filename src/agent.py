"""
FinSignal agent — orchestrates the four tools using the Strands Agents SDK.

The agent's only job is to:
  1. Call the tools in the correct order.
  2. Pass results through.
  3. Return a DecisionBrief.

All financial logic lives in the tool layer. The LLM handles language only.

Usage:
    from src.agent import run_agent
    brief = run_agent(scenario="tech_rally", contribution_usd=None)
"""

from __future__ import annotations

import json
import logging

from strands import Agent, tool

from src.models.schemas import DecisionBrief, Policy, Portfolio
from src.prompts import build_system_prompt
from src.tools.allocation import allocate_contribution, simulate_rebalance
from src.tools.constraints import check_constraints
from src.tools.decisions import evaluate_decision
from src.tools.portfolio import load_policy, load_portfolio

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level state shared between tool wrappers and run_agent.
# Each call to run_agent() updates these before invoking the agent.
# This keeps the tool wrappers free of extra parameters (Strands tools must
# have a clean signature with only the params the LLM should supply).
# ---------------------------------------------------------------------------
_current_scenario: str = "baseline"
_current_contribution: float | None = None


# ---------------------------------------------------------------------------
# Strands @tool wrappers
# The LLM calls these. They delegate immediately to the pure-Python functions.
# ---------------------------------------------------------------------------


@tool
def portfolio_tool() -> str:
    """Load the current portfolio and policy for the active scenario.

    Returns a JSON summary of the portfolio's total value and
    per-asset-class allocations. No arguments needed.
    """
    portfolio, _ = load_portfolio(_current_scenario)
    policy = load_policy()
    summary = {
        "total_value": portfolio.total_value,
        "asset_class_allocations": {
            ac: f"{pct:.1%}"
            for ac, pct in portfolio.asset_class_allocations.items()
        },
        "policy_targets": {
            ac: f"{pct:.0%}"
            for ac, pct in policy.targets.items()
        },
        "holdings_count": len(portfolio.holdings),
    }
    return json.dumps(summary, indent=2)


@tool
def constraints_tool() -> str:
    """Check the portfolio against policy rules (concentration and drift).

    Returns a JSON list of constraint results showing pass/fail per rule.
    No arguments needed.
    """
    portfolio, _ = load_portfolio(_current_scenario)
    policy = load_policy()
    results = check_constraints(portfolio, policy)
    return json.dumps(
        [
            {
                "rule": r.rule,
                "subject": r.subject,
                "passed": r.passed,
                "actual": f"{r.actual:.1%}",
                "limit": f"{r.limit:.0%}",
                "detail": r.detail,
            }
            for r in results
        ],
        indent=2,
    )


@tool
def rebalance_tool() -> str:
    """Simulate the trades needed to rebalance the portfolio to target allocations.

    Returns a JSON list of recommended trades (buy/sell/hold per holding).
    No arguments needed.
    """
    portfolio, _ = load_portfolio(_current_scenario)
    policy = load_policy()
    trades = simulate_rebalance(portfolio, policy)
    return json.dumps(
        [
            {
                "ticker": t.ticker,
                "asset_class": t.asset_class,
                "action": t.action,
                "amount_usd": t.amount_usd,
                "current_pct": f"{t.current_pct:.1%}",
                "target_pct": f"{t.target_pct:.1%}",
            }
            for t in trades
        ],
        indent=2,
    )


@tool
def contribution_tool() -> str:
    """Allocate any pending cash contribution across holdings to close allocation gaps.

    Returns a JSON list of buy orders. Returns an empty list if no contribution
    is pending. No arguments needed.
    """
    if _current_contribution is None or _current_contribution <= 0:
        return json.dumps([])

    portfolio, _ = load_portfolio(_current_scenario)
    policy = load_policy()
    trades = allocate_contribution(portfolio, policy, _current_contribution)
    return json.dumps(
        [
            {
                "ticker": t.ticker,
                "asset_class": t.asset_class,
                "action": t.action,
                "amount_usd": t.amount_usd,
            }
            for t in trades
        ],
        indent=2,
    )


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def run_agent(
    scenario: str = "baseline",
    contribution_usd: float | None = None,
) -> DecisionBrief:
    """
    Run the FinSignal agent for the given scenario and optional contribution.

    This function:
    1. Sets module-level context for the tool wrappers.
    2. Runs the Python analysis directly (deterministic path).
    3. Calls the Strands agent to generate the human-readable brief language.
    4. Returns a fully populated DecisionBrief.

    The LLM is never given raw numbers to compute — it only receives the
    pre-computed DecisionBrief structure to render as natural language.
    """
    global _current_scenario, _current_contribution
    _current_scenario = scenario
    _current_contribution = contribution_usd

    # --- Step 1: Run the deterministic engine directly ---
    portfolio, pending = load_portfolio(scenario)

    # Use passed contribution_usd; fall back to scenario's pending contribution
    effective_contribution = contribution_usd if contribution_usd is not None else pending

    policy: Policy = load_policy()
    constraint_results = check_constraints(portfolio, policy)
    rebalance_trades = simulate_rebalance(portfolio, policy)

    contribution_trades = []
    if effective_contribution and effective_contribution > 0:
        contribution_trades = allocate_contribution(portfolio, policy, effective_contribution)

    brief = evaluate_decision(
        constraint_results=constraint_results,
        rebalance_trades=rebalance_trades,
        contribution_usd=effective_contribution,
        contribution_trades=contribution_trades,
    )

    # --- Step 2: Use the agent to polish the language in the brief body ---
    # The agent receives the pre-computed brief and refines the wording.
    # It cannot change numbers — it only improves readability.
    if brief.requires_action:
        try:
            agent = Agent(
                system_prompt=build_system_prompt(),
                tools=[portfolio_tool, constraints_tool, rebalance_tool, contribution_tool],
            )

            prompt = (
                f"Scenario: {scenario}\n"
                f"Pending contribution: "
                f"{'$' + f'{effective_contribution:,.2f}' if effective_contribution else 'None'}\n\n"
                f"The deterministic engine has already run. Here is the decision brief "
                f"it produced:\n\n"
                f"Title: {brief.title}\n\n"
                f"Body:\n{brief.body}\n\n"
                "Please rewrite the body in plain, clear English for the investor "
                "without changing any numbers. Keep it under 150 words. "
                "Do not add new information."
            )

            result = agent(prompt)
            polished_body = str(result)

            # Return a brief with LLM-polished body but all original data intact
            return DecisionBrief(
                requires_action=brief.requires_action,
                title=brief.title,
                body=polished_body,
                trades=brief.trades,
                constraint_failures=brief.constraint_failures,
            )
        except Exception as exc:
            # If the agent call fails for any reason, return the raw brief.
            # The app is still fully functional — the body just won't be polished.
            logger.warning("Agent polish step failed, returning raw brief: %s", exc)

    return brief
