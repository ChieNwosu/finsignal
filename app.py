"""
FinSignal v0.1 — Streamlit UI

Three-panel layout:
  Sidebar   : scenario selector, contribution input, Analyze button
  Main top  : portfolio summary table (ticker, value, actual vs target, drift)
  Main mid  : policy status (pass/fail per constraint)
  Main bot  : decision brief or "No action needed"

Run with:
    streamlit run app.py
"""

from __future__ import annotations

import streamlit as st

from src.agent import run_agent
from src.tools.constraints import check_constraints
from src.tools.portfolio import load_policy, load_portfolio

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="FinSignal",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    st.title("📊 FinSignal")
    st.caption("Autonomous portfolio-attention agent · v0.1")
    st.divider()

    st.subheader("Scenario")
    scenario_options = {
        "baseline": "Baseline — portfolio at market prices",
        "tech_rally": "Tech Rally — AAPL & MSFT +20%",
        "bond_selloff": "Bond Selloff — BND & VCIT −15%",
        "contribution_due": "Contribution Due — $5,000 to deploy",
        "contribution_with_drift": "Tech Rally + $5,000 Contribution",
    }
    selected_scenario = st.selectbox(
        "Select a scenario",
        options=list(scenario_options.keys()),
        format_func=lambda k: scenario_options[k],
        index=0,
    )

    st.subheader("Manual Contribution")
    contribution_input = st.number_input(
        "Override contribution amount ($)",
        min_value=0.0,
        max_value=1_000_000.0,
        value=0.0,
        step=500.0,
        help="Enter an amount to deploy. Overrides any scenario-defined contribution.",
    )
    contribution_usd: float | None = contribution_input if contribution_input > 0 else None

    st.divider()
    analyze_clicked = st.button("🔍 Analyze Portfolio", use_container_width=True, type="primary")

    st.divider()
    st.caption(
        "FinSignal uses **synthetic data only**. "
        "No real trades are executed. "
        "Not financial advice."
    )

# ---------------------------------------------------------------------------
# Main area header
# ---------------------------------------------------------------------------
st.title("FinSignal Portfolio Monitor")

if not analyze_clicked:
    st.info("Select a scenario in the sidebar and click **Analyze Portfolio** to begin.")
    st.stop()

# ---------------------------------------------------------------------------
# Run analysis
# ---------------------------------------------------------------------------
with st.spinner("Analyzing portfolio…"):
    # Load raw data for display (independent of agent call)
    portfolio, scenario_contribution = load_portfolio(selected_scenario)
    policy = load_policy()
    constraint_results = check_constraints(portfolio, policy)

    # Effective contribution for display
    effective_contribution = contribution_usd if contribution_usd is not None else scenario_contribution

    # Run agent (deterministic engine + optional LLM polish)
    brief = run_agent(
        scenario=selected_scenario,
        contribution_usd=effective_contribution,
    )

# ---------------------------------------------------------------------------
# Section 1: Portfolio Summary
# ---------------------------------------------------------------------------
st.subheader("Portfolio Summary")

col_meta1, col_meta2, col_meta3 = st.columns(3)
col_meta1.metric("Total Value", f"${portfolio.total_value:,.2f}")
col_meta2.metric("Holdings", len(portfolio.holdings))
col_meta3.metric(
    "Pending Contribution",
    f"${effective_contribution:,.2f}" if effective_contribution else "None",
)

st.divider()

# Build holdings table
holding_allocs = portfolio.holding_allocations
ac_allocs = portfolio.asset_class_allocations

table_rows = []
for h in portfolio.holdings:
    actual_pct = holding_allocs.get(h.ticker, 0.0)
    target_pct_ac = policy.targets.get(h.asset_class, 0.0)
    # Distribute asset-class target evenly across holdings in that class
    holdings_in_class = [x for x in portfolio.holdings if x.asset_class == h.asset_class]
    target_pct = target_pct_ac / len(holdings_in_class) if holdings_in_class else 0.0
    drift = actual_pct - target_pct

    table_rows.append({
        "Ticker": h.ticker,
        "Name": h.name,
        "Asset Class": h.asset_class,
        "Value ($)": f"{h.market_value:,.2f}",
        "Actual %": f"{actual_pct:.1%}",
        "Target %": f"{target_pct:.1%}",
        "Drift": f"{drift:+.1%}",
    })

st.dataframe(
    table_rows,
    use_container_width=True,
    hide_index=True,
    column_config={
        "Value ($)": st.column_config.TextColumn("Value ($)", width="medium"),
        "Actual %": st.column_config.TextColumn("Actual %", width="small"),
        "Target %": st.column_config.TextColumn("Target %", width="small"),
        "Drift": st.column_config.TextColumn("Drift", width="small"),
    },
)

# Asset-class allocation bar chart
st.subheader("Asset Class Allocation")

import json  # noqa: E402 — late import for chart data only

ac_data = {
    "Asset Class": list(ac_allocs.keys()),
    "Actual %": [round(v * 100, 1) for v in ac_allocs.values()],
    "Target %": [round(policy.targets.get(ac, 0) * 100, 1) for ac in ac_allocs.keys()],
}

col_chart1, col_chart2 = st.columns(2)
with col_chart1:
    st.caption("Actual allocation")
    actual_chart_data = {ac: round(pct * 100, 1) for ac, pct in ac_allocs.items()}
    st.bar_chart(actual_chart_data)

with col_chart2:
    st.caption("Target allocation")
    target_chart_data = {ac: round(policy.targets.get(ac, 0) * 100, 1) for ac in ac_allocs.keys()}
    st.bar_chart(target_chart_data)

# ---------------------------------------------------------------------------
# Section 2: Policy Status
# ---------------------------------------------------------------------------
st.subheader("Policy Status")

passes = [r for r in constraint_results if r.passed]
failures = [r for r in constraint_results if not r.passed]

if failures:
    st.error(f"**{len(failures)} violation(s) detected** — action required.")
else:
    st.success("All policy rules are satisfied.")

# Show individual results in an expander
with st.expander("View all constraint checks", expanded=bool(failures)):
    for r in constraint_results:
        icon = "✅" if r.passed else "❌"
        status = "PASS" if r.passed else "FAIL"
        st.markdown(f"{icon} **{r.rule} — {r.subject}** ({status})")
        st.caption(r.detail)

# ---------------------------------------------------------------------------
# Section 3: Decision Brief
# ---------------------------------------------------------------------------
st.subheader("Decision Brief")

if not brief.requires_action:
    st.success(f"**{brief.title}**")
    st.caption(brief.body)
else:
    st.warning(f"**{brief.title}**")
    st.markdown(brief.body)

    # Show recommended trades if present
    actionable = [t for t in brief.trades if t.action != "hold"]
    if actionable:
        st.markdown("**Recommended trades:**")
        trade_rows = [
            {
                "Ticker": t.ticker,
                "Asset Class": t.asset_class,
                "Action": t.action.upper(),
                "Amount ($)": f"{t.amount_usd:,.2f}",
            }
            for t in actionable
        ]
        st.dataframe(
            trade_rows,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Action": st.column_config.TextColumn("Action", width="small"),
                "Amount ($)": st.column_config.TextColumn("Amount ($)", width="medium"),
            },
        )

    st.caption("⚠️ FinSignal cannot execute trades. These recommendations require your review.")
