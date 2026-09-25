# FinSignal Engineering Rules

## Stack & Runtime
- Python 3.10+
- Use the Strands Agents SDK for all agent orchestration.
- Streamlit for the UI layer.

## Financial Calculation Rules
- All portfolio arithmetic must be deterministic Python — never delegate math to the LLM.
- Never allow the LLM to invent financial calculations, weights, or numeric results.
- Rebalance simulation, concentration checks, and contribution allocation are pure functions with no side effects.

## Data Rules
- Use synthetic portfolio values and fictional personas.
- Real ticker symbols (e.g., AAPL, MSFT, BND) are permitted for realism.
- FinSignal cannot execute real trades. No brokerage credentials or brokerage integrations of any kind.

## Agent Behavior
- The agent should handle routine analysis silently.
- Surface a decision brief only when human judgment is genuinely required.
- Decision briefs must be concise, actionable, and reference specific numbers from the portfolio.

## Code Quality
- Prefer simple implementation over unnecessary abstractions.
- Add tests for every financial calculation function.
- Keep code understandable for hackathon judges — favor clarity over cleverness.
- Use type hints throughout.
- Each tool module must be independently importable and testable without the agent running.
