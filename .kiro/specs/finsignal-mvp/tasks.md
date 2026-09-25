# FinSignal MVP — Implementation Tasks

## Task Status Key
- [ ] Not started
- [~] In progress
- [x] Done

---

## Phase 1 — Data & Models

### T-01 Synthetic data files
- [ ] Create `data/persona.json` with fictional investor profile
- [ ] Create `data/portfolio.json` with 6–8 synthetic holdings across 3 asset classes
- [ ] Create `data/policy.json` with targets, concentration limit, and drift threshold
- [ ] Create `data/scenarios.json` with at least 3 named scenarios: baseline, tech_rally, contribution_due

### T-02 Pydantic schemas
- [ ] Implement `Holding`, `Portfolio`, `Policy` models in `src/models/schemas.py`
- [ ] Implement `ConstraintResult`, `RebalanceTrade`, `DecisionBrief` models
- [ ] All models must use Python type hints and have `model_config` set for immutability where appropriate

---

## Phase 2 — Deterministic Engine (Tools)

### T-03 Portfolio tool
- [ ] Implement `load_portfolio(scenario: str) -> Portfolio` in `src/tools/portfolio.py`
- [ ] Apply scenario price overrides when present
- [ ] Compute per-holding market value, total value, per-holding allocation %, per-asset-class allocation %

### T-04 Constraints tool
- [ ] Implement `check_constraints(portfolio: Portfolio, policy: Policy) -> list[ConstraintResult]` in `src/tools/constraints.py`
- [ ] Concentration check: flag any holding exceeding `concentration_limit`
- [ ] Drift check: flag any asset class where `|actual - target| > drift_threshold`

### T-05 Allocation tool
- [ ] Implement `simulate_rebalance(portfolio: Portfolio, policy: Policy) -> list[RebalanceTrade]` in `src/tools/allocation.py`
- [ ] Implement `allocate_contribution(portfolio: Portfolio, policy: Policy, contribution_usd: float) -> list[RebalanceTrade]`

### T-06 Decisions tool
- [ ] Implement `evaluate_decision(constraint_results, trades, contribution_usd) -> DecisionBrief` in `src/tools/decisions.py`
- [ ] Return `requires_action=False` when all constraints pass and no contribution is pending
- [ ] Build actionable brief referencing specific dollar amounts and percentages when action is needed

---

## Phase 3 — Agent

### T-07 Prompts
- [ ] Write system prompt in `src/prompts.py` referencing persona and silent-unless-needed behavior
- [ ] Write tool descriptions used by Strands SDK

### T-08 Agent wiring
- [ ] Implement agent in `src/agent.py` using Strands Agents SDK
- [ ] Register all four tools with `@tool` decorator
- [ ] Implement `run_agent(scenario: str, contribution_usd: float | None) -> DecisionBrief` entry point
- [ ] Agent must orchestrate tools in the correct order and pass results through

---

## Phase 4 — UI

### T-09 Streamlit app
- [ ] Implement `app.py` with sidebar (scenario selector, contribution input, Analyze button)
- [ ] Portfolio summary table: ticker, asset class, value, actual %, target %, drift
- [ ] Policy status section: pass/fail indicators per constraint
- [ ] Decision brief panel: renders brief body or "No action needed" message

---

## Phase 5 — Tests

### T-10 Constraint tests
- [ ] `tests/test_constraints.py`: test concentration check passes when under limit
- [ ] `tests/test_constraints.py`: test concentration check fails when over limit
- [ ] `tests/test_constraints.py`: test drift check passes when within threshold
- [ ] `tests/test_constraints.py`: test drift check fails when beyond threshold

### T-11 Allocation tests
- [ ] `tests/test_allocation.py`: test rebalance trades sum to zero (no cash created or destroyed)
- [ ] `tests/test_allocation.py`: test contribution allocation sums to contribution amount
- [ ] `tests/test_allocation.py`: test rebalance brings allocations to target

---

## Phase 6 — Documentation

### T-12 README
- [ ] Project description and architecture summary
- [ ] Setup and run instructions
- [ ] Scenario descriptions
- [ ] Demo walkthrough
