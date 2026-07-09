"""Lambda package — one handler per Step Functions state.

Each handler is a pure function: event dict → result dict.
LLM states use CAST (AgentFactory) to call the model.
Script states call tools directly.
"""
