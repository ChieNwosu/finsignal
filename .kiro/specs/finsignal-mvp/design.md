# FinSignal MVP — Design

## System Overview

FinSignal is composed of four layers:

```
Streamlit UI (app.py)
       │
       ▼
Strands Agent (src/agent.py)
       │
       ├── Portfolio Tool      (src/tools/portfolio.py)
       ├── Constraints Tool    (src/tools/constraints.py)
       ├── Allocation Tool     (src/tools/allocation.py)
       └── Decisions Tool      (src/tools/decisions.py)
                  │
                  ▼
       Deterministic Python Engine
                  │
                  ▼
       Synthetic Data Layer (data/)
```

---

## Data Layer

### `data/persona.json`
Fictional investor profile. Consumed by the agent's system prompt to contextualize language.

```json
{
  "name": "Alex Rivera",
  "risk_tolerance": "moderate",
  "investment_goal": "long-term growth with capital preservation",
  "investment_horizon_years": 20
}
```

### `data/portfolio.json`
Synthetic holdings. Each entry has a ticker, asset class, quantity, and current price.

```json
{
  "holdings": [
    {"ticker": "AAPL", "asset_class": "US Equity", "quantity": 50, "price": 189.50},
    ...
  ]
}
```

### `data/policy.json`
User-defined portfolio policy: target allocations, concentration limit, and drift threshold.

```json
{
  "targets": {
    "US Equity": 0.60,
    "International Equity": 0.20,
    "Bonds": 0.20
  },
  "concentration_limit": 0.25,
  "drift_threshold": 0.05
}
```

### `data/scenarios.json`
Named scenario overrides used during demos. Each scenario can override prices or add a pending contribution.

```json
{
  "scenarios": {
    "baseline": {},
    "tech_rally": {"price_overrides": {"AAPL": 230.00, "MSFT": 420.00}},
    "contribution_due": {"pending_contribution": 5000.00}
  }
}
```

---

## Models (`src/models/schemas.py`)

Pydantic models used for data validation and type safety across all tool boundaries:

- `Holding` — ticker, asset_class, quantity, price, computed market_value
- `Portfolio` — list of Holdings, computed total_value and allocations
- `Policy` — targets dict, concentration_limit, drift_threshold
- `ConstraintResult` — rule name, passed bool, actual value, limit
- `RebalanceTrade` — ticker, action (buy/sell), amount_usd
- `DecisionBrief` — requires_action bool, title, body, trades list

---

## Tools

### `src/tools/portfolio.py` — `load_portfolio(scenario: str) -> Portfolio`
1. Read `data/portfolio.json`.
2. If scenario has price overrides, apply them.
3. Compute `market_value = quantity × price` for each holding.
4. Compute `total_value` and `allocation_pct` per holding and per asset class.
5. Return a `Portfolio` object.

### `src/tools/constraints.py` — `check_constraints(portfolio, policy) -> list[ConstraintResult]`
Two checks:
1. **Concentration check** — for each holding, flag if `allocation_pct > concentration_limit`.
2. **Drift check** — for each asset class, flag if `|actual_pct - target_pct| > drift_threshold`.

### `src/tools/allocation.py`
Two functions:
1. `simulate_rebalance(portfolio, policy) -> list[RebalanceTrade]`
   - For each asset class: `trade_usd = (target_pct - actual_pct) × total_value`.
   - Positive → buy, negative → sell.
2. `allocate_contribution(portfolio, policy, contribution_usd) -> list[RebalanceTrade]`
   - Compute new total = `total_value + contribution_usd`.
   - Allocate contribution to close the gap between actual and target allocations.

### `src/tools/decisions.py` — `evaluate_decision(constraint_results, trades, contribution) -> DecisionBrief`
- If all constraints pass and no contribution is pending → `requires_action = False`.
- Otherwise build a human-readable brief referencing specific numbers.

---

## Agent (`src/agent.py`)

Uses the Strands Agents SDK. The agent is initialized with:
- A system prompt from `src/prompts.py` that describes the agent's role, the persona, and the "silent unless needed" behavior.
- The four tools registered via the Strands `@tool` decorator.

The agent entry point accepts a user message (e.g., "Check my portfolio" or "I have $5,000 to invest") and a scenario name, then orchestrates the tool calls:

1. `load_portfolio(scenario)` → portfolio
2. `check_constraints(portfolio, policy)` → constraint_results
3. `simulate_rebalance(portfolio, policy)` → trades
4. `evaluate_decision(constraint_results, trades, contribution)` → brief

The agent returns the `DecisionBrief` to the UI. Intermediate tool results are not shown to the user.

---

## Streamlit UI (`app.py`)

Three-panel layout:

| Panel | Content |
|---|---|
| Sidebar | Scenario selector, optional contribution amount input, "Analyze" button |
| Main — Portfolio | Table: ticker, asset class, value, actual %, target %, drift |
| Main — Decision Brief | Agent output or "Portfolio is within policy — no action needed." |

The UI calls `run_agent(scenario, contribution)` from `src/agent.py` and renders the returned `DecisionBrief`.

---

## Key Design Decisions

1. **LLM handles language, Python handles math.** The agent never performs arithmetic. All numbers in a decision brief come from tool return values.
2. **Silent-by-default.** The `evaluate_decision` function is the gatekeeper. If nothing is wrong, the agent produces no visible output.
3. **Scenarios over live data.** No API keys needed. The scenario layer makes demos fully reproducible.
4. **Pydantic for tool boundaries.** All data crossing tool boundaries is validated, making bugs easy to spot during a live demo.
