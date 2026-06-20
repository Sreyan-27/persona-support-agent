"""
escalator.py
------------
Decides whether a conversation needs to be handed off to a human agent, and
builds the structured handoff summary the human will see.

Escalation triggers (all configurable in config.py / .env)
------------------------------------------------------------
  1. Low retrieval confidence  - best chunk score < RETRIEVAL_CONFIDENCE_THRESHOLD
  2. No relevant chunks found  - retrieval returned zero results
  3. Sensitive topic detected  - billing/legal/account-security keyword match
  4. Repeated user frustration - the same conversation has gone N turns
     without resolution (tracked by the caller via `unresolved_turns`)
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from src.config import settings


@dataclass
class EscalationDecision:
    escalate: bool
    triggers: list = field(default_factory=list)  # e.g. ["low_confidence", "sensitive_topic"]
    explanation: str = ""


def _matches_sensitive_topic(text: str) -> Optional[str]:
    lowered = text.lower()
    for keyword in settings.sensitive_keywords:
        if keyword in lowered:
            return keyword
    return None


def check_escalation(
    user_query: str,
    context_chunks: list,
    unresolved_turns: int = 0,
) -> EscalationDecision:
    """
    Evaluates all configured escalation triggers for a single turn.

    Parameters
    ----------
    user_query: the raw customer message for this turn
    context_chunks: the list of retrieved RAG chunks (each with a 'score')
    unresolved_turns: how many consecutive prior turns on this issue were
        not resolved (maintained by the calling application/session state)
    """
    triggers = []

    # Trigger 1 & 2: low / zero retrieval confidence
    best_score = max((c["score"] for c in context_chunks), default=0.0)
    if not context_chunks:
        triggers.append("no_relevant_documents_found")
    elif best_score < settings.retrieval_confidence_threshold:
        triggers.append("low_retrieval_confidence")

    # Trigger 3: sensitive topic
    sensitive_hit = _matches_sensitive_topic(user_query)
    if sensitive_hit:
        triggers.append(f"sensitive_topic:{sensitive_hit}")

    # Trigger 4: repeated frustration / unresolved issue
    if unresolved_turns >= settings.max_unresolved_turns:
        triggers.append("repeated_unresolved_turns")

    if triggers:
        explanation = "Escalating due to: " + "; ".join(triggers)
    else:
        explanation = "No escalation triggers met; retrieval confidence and topic are within self-service bounds."

    return EscalationDecision(escalate=bool(triggers), triggers=triggers, explanation=explanation)


def generate_handoff_summary(
    user_query: str,
    persona: str,
    context_chunks: list,
    conversation_history: Optional[list] = None,
    attempted_steps: Optional[list] = None,
    decision: Optional[EscalationDecision] = None,
) -> dict:
    """
    Builds the structured JSON handoff package a human agent sees. Includes
    everything required by the assignment spec: persona, issue summary,
    conversation history, documents used, attempted steps, and a
    recommendation for next steps.
    """
    conversation_history = conversation_history or []
    attempted_steps = attempted_steps or []
    sources_used = sorted({c["source"] for c in context_chunks if c.get("source")})
    best_score = max((c["score"] for c in context_chunks), default=0.0)

    recommendation = _build_recommendation(decision, persona)

    summary = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "persona": persona,
        "issue_summary": user_query.strip()[:300],
        "conversation_history": conversation_history,
        "documents_used": sources_used,
        "retrieval_confidence": best_score,
        "attempted_steps": attempted_steps,
        "escalation_triggers": decision.triggers if decision else [],
        "recommended_next_steps": recommendation,
    }
    return summary


def _build_recommendation(decision: Optional[EscalationDecision], persona: str) -> str:
    if decision is None or not decision.triggers:
        return "Review conversation context and respond directly to the customer."

    triggers = decision.triggers
    if any(t.startswith("sensitive_topic") for t in triggers):
        return (
            "Route to the appropriate specialist team (Billing/Legal/Account Security) "
            "per the sensitive-topic policy. Verify customer identity before taking any "
            "account or payment action."
        )
    if "no_relevant_documents_found" in triggers or "low_retrieval_confidence" in triggers:
        return (
            "No sufficiently confident match was found in the knowledge base. Human agent "
            "should investigate the underlying system/account directly and consider adding "
            "a new knowledge base article if this is a recurring gap."
        )
    if "repeated_unresolved_turns" in triggers:
        return (
            f"Customer ({persona}) has not been resolved across multiple turns. Prioritize "
            "this handoff and consider proactive outreach rather than waiting for the next message."
        )
    return "Review conversation context and respond directly to the customer."
