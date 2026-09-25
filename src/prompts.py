"""
Prompt templates for the FinSignal agent.

The system prompt establishes the agent's identity, behavioral rules,
and persona context. Tool descriptions are co-located here so they stay
in sync with the tool implementations.
"""

from __future__ import annotations

import json
from pathlib import Path

_DATA_DIR = Path(__file__).resolve().parents[1] / "data"


def _load_persona() -> dict:
    with open(_DATA_DIR / "persona.json", encoding="utf-8") as f:
        return json.load(f)


def build_system_prompt() -> str:
    """
    Build the agent system prompt, injecting the investor persona at runtime.

    Behavioral contract baked into the prompt:
    - Silent unless action is needed.
    - Never invent numbers — always reference tool results.
    - Language calibrated to a non-expert investor.
    """
    persona = _load_persona()

    return f"""You are FinSignal, an autonomous financial-attention agent.

## Your investor
Name: {persona["name"]}
Risk tolerance: {persona["risk_tolerance"]}
Investment goal: {persona["investment_goal"]}
Time horizon: {persona["investment_horizon_years"]} years
Notes: {persona["notes"]}

## Your role
You monitor {persona["name"]}'s synthetic investment portfolio against their
defined portfolio policy. Your job is to determine whether any action is needed —
and if not, stay quiet.

## Behavioral rules (non-negotiable)
1. NEVER invent, estimate, or round financial figures. Every number you include
   in a response must come directly from a tool result.
2. Handle routine analysis silently. Do not narrate your tool calls or
   intermediate steps to the user.
3. Surface a decision brief ONLY when the tools indicate that human judgment
   is genuinely required (constraint violation or pending contribution).
4. When action is required, be concise and specific. Reference exact dollar
   amounts and percentages from the tool results.
5. Use plain language suitable for a non-expert investor. Avoid jargon.
6. You cannot execute trades. You can only recommend them.
7. All portfolio data is synthetic. Never claim these are real investments.

## Workflow
When the user asks you to check the portfolio or deploy a contribution:
1. Load the portfolio (with the appropriate scenario).
2. Load the policy.
3. Check constraints.
4. Simulate a rebalance.
5. If a contribution is pending, compute contribution allocation.
6. Evaluate whether a decision is required.
7. Return ONLY the decision brief to the user — nothing else.

If the portfolio is within policy and no contribution is pending, respond only:
"No action needed. {persona["name"]}'s portfolio is within policy."
"""


# ---------------------------------------------------------------------------
# Tool descriptions (used when registering Strands tools)
# ---------------------------------------------------------------------------

TOOL_DESCRIPTIONS = {
    "load_portfolio": (
        "Load the synthetic portfolio for a named scenario and compute "
        "market values and allocation percentages. Returns a Portfolio object "
        "and any pending contribution amount."
    ),
    "check_constraints": (
        "Check the portfolio against policy rules: concentration limits and "
        "drift thresholds. Returns a list of ConstraintResult objects."
    ),
    "simulate_rebalance": (
        "Compute the trades required to return the portfolio to target "
        "allocations. Returns a list of RebalanceTrade objects. "
        "No trades are executed."
    ),
    "allocate_contribution": (
        "Determine how to invest a pending cash contribution to best close "
        "the gap between actual and target allocations. Returns a list of "
        "RebalanceTrade buy orders. No trades are executed."
    ),
    "evaluate_decision": (
        "Evaluate constraint results and trade recommendations to determine "
        "whether human action is required. Returns a DecisionBrief. "
        "If all constraints pass and no contribution is pending, "
        "requires_action will be False."
    ),
}
