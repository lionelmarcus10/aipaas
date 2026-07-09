"""Tools package — deterministic "arms" of the Financial Dispute Agent.

Each tool is a pure function: input dict → output dict.
No LLM, no side effects (except payment_mock which is intentionally mock).
"""
