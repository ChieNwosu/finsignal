# FinSignal v0.1

**An autonomous financial-attention agent built with the Strands Agents SDK.**

FinSignal monitors fictional investment portfolios composed of real-world securities, evaluates them against user-defined portfolio policies, handles routine analysis silently, and surfaces concise decision briefs only when human judgment is required.

> ⚠️ FinSignal uses synthetic data only. No real trades are executed. Not financial advice.

---

## Architecture

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

**Key design principle:** The LLM handles language only. All portfolio arithmetic is deterministic Python — the LLM never invents numbers.

---

## Setup

### Prerequisites
- Python 3.10+
- AWS credentials with Amazon Bedrock access (default model provider), **or** an Anthropic/OpenAI API key

### Install

```bash
# Clone the repo
git clone <repo-url>
cd finsignal

# Create and activate a virtual environment
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Configure AWS credentials (for Bedrock — default provider)

```bash
# Option A: Bedrock API key (quickest for local dev)
export AWS_BEARER_TOKEN_BEDROCK=<your-bedrock-api-key>

# Option B: Standard AWS credentials
aws configure
```

To use Anthropic or OpenAI instead, set the relevant API key and update the `Agent()` call in `src/agent.py` with the appropriate model object. See the [Strands model providers docs](https://strandsagents.com/docs/user-guide/sdk/model-providers/index.md).

---

## Running the App

```bash
streamlit run app.py
```

Open [http://localhost:8501](http://localhost:8501) in your browser.

---

## Running the Tests

```bash
pytest tests/ -v
```

To run with coverage:

```bash
pytest tests/ -v --cov=src --cov-report=term-missing
```

---

## Scenarios

FinSignal ships with five demo scenarios. Select one in the sidebar:

| Scenario | Description | Expected outcome |
|---|---|---|
| `baseline` | Portfolio at current market prices | No action needed |
| `tech_rally` | AAPL & MSFT surge 20% | Concentration breach + drift alert |
| `bond_selloff` | BND & VCIT drop 15% | Drift alert on Bonds |
| `contribution_due` | $5,000 available to invest | Contribution allocation brief |
| `contribution_with_drift` | Tech rally + $5,000 contribution | Combined rebalance + contribution brief |

---

## Project Structure

```
finsignal/
├── .kiro/
│   ├── specs/finsignal-mvp/     # requirements, design, tasks
│   └── steering/                # engineering rules
│
├── src/
│   ├── agent.py                 # Strands agent + @tool wrappers
│   ├── prompts.py               # system prompt + tool descriptions
│   ├── tools/
│   │   ├── portfolio.py         # load_portfolio(), load_policy()
│   │   ├── constraints.py       # check_constraints()
│   │   ├── allocation.py        # simulate_rebalance(), allocate_contribution()
│   │   └── decisions.py         # evaluate_decision()
│   └── models/
│       └── schemas.py           # Pydantic models
│
├── data/
│   ├── persona.json             # Fictional investor: Alex Rivera
│   ├── portfolio.json           # 7 synthetic holdings (AAPL, MSFT, VTI, ...)
│   ├── policy.json              # 60/20/20 targets, 25% concentration, 5% drift
│   └── scenarios.json           # 5 named demo scenarios
│
├── tests/
│   ├── test_constraints.py      # 9 unit tests for constraint checks
│   └── test_allocation.py       # 9 unit tests for rebalance + contribution
│
├── app.py                       # Streamlit UI entry point
├── requirements.txt
├── .gitignore
└── README.md
```

---

## Investor Persona

Alex Rivera — 38, moderate risk tolerance, 20-year investment horizon, long-term growth with capital preservation.

**Portfolio policy:**
- Target allocation: 60% US Equity / 20% International Equity / 20% Bonds
- Concentration limit: no single holding > 25%
- Drift threshold: rebalance triggered when any asset class deviates > 5 percentage points from target

---

## Demo Walkthrough

1. Launch the app: `streamlit run app.py`
2. **Baseline** — portfolio is within policy. No brief is shown.
3. **Tech Rally** — AAPL spikes. Concentration breach + US Equity drift. Brief shows sell recommendations.
4. **Bond Selloff** — bonds drop. Brief shows buy recommendation for BND/VCIT.
5. **Contribution Due** — $5,000 to invest. Brief shows how to allocate it optimally.
6. **Tech Rally + Contribution** — both triggers fire. Combined brief with full guidance.
