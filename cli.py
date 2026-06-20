#!/usr/bin/env python3
"""
cli.py
------
Interactive command-line chatbot for the Persona-Adaptive Support Agent.
Satisfies the assignment's minimum UI requirement. Displays, for every turn:
user message, detected persona, retrieved sources, generated response, and
escalation status.

Usage:
    python cli.py
"""

import sys

from src.config import validate_settings
from src.rag_pipeline import LocalRAGPipeline
from src.session import SupportSession

BANNER = """
============================================================
 TechCorp Cloud - Persona-Adaptive Support Agent (CLI)
============================================================
Type your support question below. Type 'exit' or 'quit' to leave.
"""


def print_turn_result(result: dict):
    print(f"\n[Persona detected]: {result['persona']}  "
          f"(confidence={result['persona_confidence']:.2f}, method={result['persona_method']})")

    if result["retrieved_sources"]:
        print("[Retrieved sources]:")
        for s in result["retrieved_sources"]:
            locator = f"page {s['page']}" if s.get("page") else (s.get("section") or "")
            locator_str = f" - {locator}" if locator else ""
            print(f"   - {s['source']}{locator_str}  (score={s['score']:.2f})")
    else:
        print("[Retrieved sources]: none")

    status = "ESCALATED TO HUMAN" if result["escalated"] else "Resolved by agent"
    print(f"[Escalation status]: {status}")
    if result["escalated"]:
        print(f"[Escalation triggers]: {', '.join(result['escalation_triggers'])}")

    print(f"\nAgent: {result['response']}\n")

    if result["handoff_summary"]:
        import json
        print("---- Human Handoff Summary " + "-" * 30)
        print(json.dumps(result["handoff_summary"], indent=2))
        print("-" * 58)


def main():
    problems = validate_settings()
    for p in problems:
        print(f"[CONFIG WARNING] {p}")
    if any("data directory" in p.lower() for p in problems):
        sys.exit(1)
    if any("GEMINI_API_KEY" in p for p in problems):
        print("Continuing in OFFLINE MODE: persona detection will use rule-based "
              "fallback and responses will be placeholders until a key is set.\n")

    print("Initializing knowledge base (first run may take a moment to embed documents) ...")
    pipeline = LocalRAGPipeline()
    count = pipeline.ingest_all()
    print(f"Knowledge base ready: {count} chunks indexed.\n")

    session = SupportSession(pipeline=pipeline)
    print(BANNER)

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye.")
            break

        if not user_input:
            continue
        if user_input.lower() in ("exit", "quit"):
            print("Goodbye.")
            break

        result = session.send(user_input)
        print_turn_result(result)


if __name__ == "__main__":
    main()
