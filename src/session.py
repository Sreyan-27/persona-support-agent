"""
session.py
----------
Orchestrates a full conversation turn end-to-end:

    user message
        -> persona detection            (classifier.py)
        -> knowledge base retrieval     (rag_pipeline.py)
        -> adaptive generation /
           escalation check             (generator.py / escalator.py)

Also maintains lightweight multi-turn state (conversation history and an
"unresolved turns" counter) so the escalator's repeated-frustration trigger
has something real to evaluate, and so the human handoff summary can include
genuine prior context rather than just the single latest message.

This is the single module both the CLI (cli.py) and the Streamlit app
(app.py) call into, so the two interfaces can never drift out of sync in
their behaviour.
"""

from dataclasses import dataclass, field
from typing import Optional

from src.classifier import classify_customer_persona
from src.generator import generate_adaptive_response
from src.rag_pipeline import LocalRAGPipeline


@dataclass
class Turn:
    role: str  # "user" or "agent"
    text: str
    persona: Optional[str] = None
    escalated: Optional[bool] = None


class SupportSession:
    """Holds state for a single end-user conversation."""

    def __init__(self, pipeline: Optional[LocalRAGPipeline] = None):
        self.pipeline = pipeline or LocalRAGPipeline()
        self.history: list = []
        self.attempted_steps: list = []
        self.unresolved_turns: int = 0

    def _history_as_strings(self) -> list:
        return [f"{t.role}: {t.text}" for t in self.history]

    def send(self, user_message: str, top_k: Optional[int] = None) -> dict:
        """
        Processes one user message through the full pipeline and returns a
        dict the UI layer (CLI or Streamlit) can render directly:

            {
                "persona": ..., "persona_confidence": ..., "persona_method": ...,
                "retrieved_sources": [...], "response": ..., "escalated": bool,
                "handoff_summary": dict | None,
            }
        """
        self.history.append(Turn(role="user", text=user_message))

        persona_result = classify_customer_persona(user_message)
        context_chunks = self.pipeline.retrieve_context(user_message, top_k=top_k)

        agent_response = generate_adaptive_response(
            user_query=user_message,
            persona=persona_result.persona,
            context_chunks=context_chunks,
            conversation_history=self._history_as_strings(),
            attempted_steps=self.attempted_steps,
            unresolved_turns=self.unresolved_turns,
        )

        self.history.append(
            Turn(
                role="agent",
                text=agent_response.response_text,
                persona=persona_result.persona,
                escalated=agent_response.escalated,
            )
        )

        if agent_response.escalated:
            self.unresolved_turns = 0  # reset; a human is now taking over
        else:
            self.unresolved_turns += 1
            # Track a lightweight "attempted step" trail for the eventual
            # handoff summary, in case a later turn does escalate.
            top_source = context_chunks[0]["source"] if context_chunks else None
            if top_source:
                self.attempted_steps.append(f"Suggested guidance from {top_source}")

        return {
            "persona": persona_result.persona,
            "persona_confidence": persona_result.confidence,
            "persona_method": persona_result.method,
            "persona_reasoning": persona_result.reasoning,
            "retrieved_sources": context_chunks,
            "response": agent_response.response_text,
            "escalated": agent_response.escalated,
            "escalation_triggers": agent_response.escalation_triggers,
            "handoff_summary": agent_response.handoff_summary,
        }
