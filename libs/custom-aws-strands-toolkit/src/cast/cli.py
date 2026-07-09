"""CLI REPL — interactive agent loop with /save, /sessions, /help."""

import sys
from datetime import datetime

from .factory import AgentFactory


def run_cli(factory: AgentFactory, system_prompt: str = "", tools=None) -> None:
    """Run an interactive REPL for a CAST agent.

    Commands:
        /save <id>   Save current conversation
        /sessions    List saved sessions
        /help        Show help
        Ctrl+C       Exit
    """
    session_id = None
    agent = factory.create_agent(system_prompt=system_prompt, tools=tools)

    print(f"Model: {type(factory.model).__name__}")
    print(f"Tools: {len(agent.tool_names)}")
    print("Commands: /save <id>  /sessions  /help  (Ctrl+C to exit)\n")

    while True:
        try:
            user_input = input(">>> ").strip()
            if not user_input:
                continue

            if user_input.startswith("/"):
                parts = user_input.split(maxsplit=1)
                cmd, arg = parts[0], parts[1] if len(parts) > 1 else ""

                if cmd == "/save":
                    if not arg:
                        print("Usage: /save <session_id>")
                        continue
                    path = factory.sessions.save(agent, arg)
                    print(f"Session saved to: {path}")

                elif cmd == "/sessions":
                    sessions = factory.sessions.list()
                    if not sessions:
                        print("No saved sessions.")
                    else:
                        for s in sessions:
                            print(f"  - {s}")

                elif cmd == "/help":
                    print("Commands:")
                    print("  /save <id>   Save current conversation")
                    print("  /sessions    List saved sessions")
                    print("  /help        Show this help")
                    print("  Ctrl+C       Exit")

                else:
                    print(f"Unknown: {cmd}. Type /help.")
            else:
                response = agent(user_input)
                print(response)

        except KeyboardInterrupt:
            print("\nBye!")
            break
