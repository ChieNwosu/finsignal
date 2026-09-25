# FinSignal MVP — Requirements

## Overview

FinSignal is an autonomous financial-attention agent built with the Strands Agents SDK. It monitors fictional investment portfolios composed of real-world securities, evaluates them against user-defined portfolio policies, handles routine analysis silently, and surfaces concise decision briefs only when human judgment is required. No real trades are executed.

---

## Functional Requirements

### FR-1 Portfolio Monitoring
- The agent must load a synthetic portfolio from `data/portfolio.json` containing holdings with ticker symbols, quantities, and current prices.
- The agent must compute current market values and percentage allocations for each holding.
- Portfolio total value and per-holding values must be calculated deterministically in Python.

### FR-2 Policy Evaluation
- The agent must load a portfolio policy from `data/policy.json` defining:
  - Target allocation percentages per asset class or ticker.
  - Concentration limits (maximum % any single holding may represent).
  - Drift thresholds (how far an actual allocation may deviate from target before action is needed).
- The agent must compare actual allocations against policy targets and flag any violations.

### FR-3 Constraint Checking
- A dedicated `constraints` tool must check:
  - Whether any single holding exceeds the concentration limit.
  - Whether any asset class has drifted beyond the allowed threshold.
- Constraint checks must return structured results indicating pass/fail per rule.

### FR-4 Rebalance Simulation
- An `allocation` tool must simulate a rebalance: given current holdings and policy targets, compute the trades (buy/sell amounts in dollars) required to return to target allocations.
- Simulation must be deterministic and produce no side effects.
- The tool must also compute how a new contribution should be allocated across holdings to move the portfolio toward target.

### FR-5 Decision Surfacing
- A `decisions` tool must evaluate constraint results and rebalance outputs and determine whether a human decision is required.
- Routine states (portfolio within policy, no concentration breach) must be handled silently — no alert is generated.
- A decision brief must be surfaced when:
  - A concentration limit is breached.
  - Drift exceeds the policy threshold on any position.
  - A new contribution is available for deployment.
- Decision briefs must be concise and reference specific dollar amounts and percentages from the portfolio.

### FR-6 Scenario Injection
- The agent must support loading named scenarios from `data/scenarios.json` that override portfolio prices or add a pending contribution, enabling demo flows without live data.

### FR-7 Streamlit UI
- A Streamlit app (`app.py`) must provide:
  - A sidebar for selecting a scenario or entering a contribution amount.
  - A portfolio summary table showing ticker, value, and actual vs. target allocation.
  - A policy status panel showing pass/fail for each constraint.
  - A decision brief panel that displays the agent's output when action is required, or a "No action needed" message otherwise.

### FR-8 Persona
- A `data/persona.json` file defines the fictional investor profile (name, risk tolerance, investment goals) used to contextualize agent responses.

---

## Non-Functional Requirements

### NFR-1 No Real Trades
- FinSignal must never connect to any brokerage API or execute real orders.

### NFR-2 Determinism
- All financial calculations must produce identical output given identical input. No randomness or LLM-generated numbers in the calculation path.

### NFR-3 Testability
- Every financial calculation function must have unit tests in `tests/`.
- Tool modules must be importable and runnable independently of the agent.

### NFR-4 Simplicity
- Code must remain readable to a hackathon judge unfamiliar with the codebase.
- Avoid over-engineering; one clean abstraction layer between tools and the agent is sufficient.

### NFR-5 Python 3.10+
- All code must be compatible with Python 3.10 and above.
