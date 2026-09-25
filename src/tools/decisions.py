"""
Decisions tool — evaluates analysis results and produces a DecisionBrief.

The agent calls this tool last. It is the gatekeeper that determines whether
human attention is required. If everything is within policy and there is no
pending contribution, it returns requires_action=False and the UI stays quiet.

All numbers in the brief come from the tool results — the LLM never invents them.
"""

from __future__ import annotations

from src.models.schemas import ConstraintResult, DecisionBrief, RebalanceTrade
from src.tools.constraints import any_failures


def evaluate_decision(
    constraint_results: list[ConstraintResult],
    rebalance_trades: list[RebalanceTrade],
    contribution_usd: float | None,
    contribution_trades: list[RebalanceTrade] | None = None,
) -> DecisionBrief:
    """
    Determine whether a decision brief should be surfaced to the user.

    Rules:
    - No failures AND no pending contribution → requires_action=False, silent.
    - Any constraint failure OR pending contribution → requires_action=True.

    The brief body is built from concrete numbers in the tool results.
    """
    failures = [r for r in constraint_results if not r.passed]
    has_contribution = contribution_usd is not None and contribution_usd > 0

    if not failures and not has_contribution:
        return DecisionBrief(
            requires_action=False,
            title="Portfolio is within policy — no action needed.",
            body=(
                "All holdings are within concentration limits and "
                "all asset classes are within drift thresholds. "
                "No contribution is pending."
            ),
            trades=[],
            constraint_failures=[],
        )

    # --- Build the decision brief ---
    sections: list[str] = []

    # Section 1: constraint violations
    if failures:
        lines = ["**Policy violations detected:**"]
        for f in failures:
            lines.append(f"  • {f.detail}")
        sections.append("\n".join(lines))

    # Section 2: rebalance trades
    actionable_trades = [t for t in rebalance_trades if t.action != "hold"]
    if actionable_trades:
        lines = ["**Recommended rebalance trades:**"]
        for t in actionable_trades:
            verb = "Buy" if t.action == "buy" else "Sell"
            lines.append(f"  • {verb} ${t.amount_usd:,.2f} of {t.ticker} ({t.asset_class})")
        sections.append("\n".join(lines))

    # Section 3: contribution allocation
    if has_contribution and contribution_trades:
        lines = [f"**Allocate ${contribution_usd:,.2f} contribution:**"]
        for t in contribution_trades:
            lines.append(f"  • Buy ${t.amount_usd:,.2f} of {t.ticker} ({t.asset_class})")
        sections.append("\n".join(lines))
    elif has_contribution:
        sections.append(
            f"**Pending contribution:** ${contribution_usd:,.2f} is ready to deploy. "
            "Run a contribution allocation to determine optimal placement."
        )

    body = "\n\n".join(sections)

    # Derive a concise title
    title_parts: list[str] = []
    if failures:
        violation_subjects = ", ".join(f.subject for f in failures[:2])
        title_parts.append(f"Action required: {violation_subjects} out of policy")
    if has_contribution:
        title_parts.append(f"${contribution_usd:,.2f} contribution ready to deploy")

    title = " · ".join(title_parts) if title_parts else "Action required"

    all_trades = actionable_trades + (contribution_trades or [])

    return DecisionBrief(
        requires_action=True,
        title=title,
        body=body,
        trades=all_trades,
        constraint_failures=failures,
    )
