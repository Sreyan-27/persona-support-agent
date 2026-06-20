"""
generator.py
------------
Combines the detected persona, the retrieved knowledge-base chunks, and the
user's query into a persona-specific system prompt, then calls Gemini to
produce a grounded response. If escalator.check_escalation() determines this
turn must be handed off, generation is skipped and an escalation message +
handoff summary is returned instead.

Hallucination control: the system prompt explicitly restricts the model to
the supplied context documents only, and instructs it to say so plainly if
the context doesn't contain the answer (rather than guessing).
"""

from dataclasses import dataclass, field
from typing import Optional

from src.config import settings
from src.escalator import EscalationDecision, check_escalation, generate_handoff_summary
from src.utils import call_with_backoff, get_genai_client

PERSONA_INSTRUCTIONS = {
    "Technical Expert": (
        "You are a Senior Support Engineer speaking to a technically sophisticated user. "
        "Provide a precise root-cause explanation, exact configuration/parameter details, "
        "and step-by-step troubleshooting. Use code blocks or HTTP examples where the source "
        "material includes them. Do not oversimplify or pad the answer with reassurance."
    ),
    "Frustrated User": (
        "You are an empathetic Customer Care Specialist. Open with a brief, genuine "
        "acknowledgement of the customer's frustration. Then give clear, simple, "
        "action-oriented steps as a short bulleted list. Avoid jargon. Keep the tone "
        "calm, reassuring, and focused on resolving the problem quickly."
    ),
    "Business Executive": (
        "You are a concise Client Relations lead speaking to a business stakeholder. "
        "Lead with the direct answer and business impact. Mention timelines or SLA "
        "details if the source material includes them. Keep the response brief — "
        "avoid step-by-step technical instructions or jargon."
    ),
}

GROUNDING_RULES = (
    "CRITICAL RULES:\n"
    "- Base your answer ONLY on the FACTUAL CONTEXT DOCUMENTS provided below.\n"
    "- Do not invent steps, policies, numbers, or product behavior not present in the context.\n"
    "- If the context only partially answers the question, answer the part it covers and "
    "clearly note what isn't covered.\n"
    "- Cite which source document(s) you drew from inline using square brackets, e.g. [billing_policy.txt]."
)


@dataclass
class AgentResponse:
    escalated: bool
    response_text: str
    persona: str
    retrieved_sources: list = field(default_factory=list)
    handoff_summary: Optional[dict] = None
    escalation_triggers: list = field(default_factory=list)


def _build_system_prompt(persona: str, context_chunks: list) -> str:
    persona_instructions = PERSONA_INSTRUCTIONS.get(persona, PERSONA_INSTRUCTIONS["Business Executive"])
    context_lines = []
    for c in context_chunks:
        locator = f"page {c['page']}" if c.get("page") else (c.get("section") or "")
        locator_str = f" ({locator})" if locator else ""
        context_lines.append(f"Source [{c['source']}{locator_str}]: {c['text']}")
    context_text = "\n\n".join(context_lines)

    return f"{persona_instructions}\n\n{GROUNDING_RULES}\n\nFACTUAL CONTEXT DOCUMENTS:\n{context_text}"


def _call_gemini(system_prompt: str, user_query: str) -> str:
    client = get_genai_client()
    from google.genai import types

    def _call():
        return client.models.generate_content(
            model=settings.generation_model,
            contents=user_query,
            config=types.GenerateContentConfig(system_instruction=system_prompt, temperature=0.2),
        )

    response = call_with_backoff(_call, max_retries=settings.max_api_retries)
    return response.text


def _offline_fallback_response(persona: str, context_chunks: list) -> str:
    """
    Used only when GEMINI_API_KEY is not configured, so the CLI/Streamlit app
    can still be exercised structurally (chunk retrieval, persona detection,
    escalation logic) without a live API key. This is NOT a substitute for
    real generation and is clearly labeled as such.
    """
    if not context_chunks:
        return (
            "[OFFLINE MODE - no GEMINI_API_KEY configured] No response was generated because "
            "no LLM is connected. Retrieved 0 relevant chunks."
        )
    bullet_sources = ", ".join(sorted({c["source"] for c in context_chunks}))
    return (
        f"[OFFLINE MODE - no GEMINI_API_KEY configured] Persona detected: {persona}. "
        f"Relevant source documents found: {bullet_sources}. "
        f"Set GEMINI_API_KEY in your .env file to generate a real adaptive response."
    )


def generate_adaptive_response(
    user_query: str,
    persona: str,
    context_chunks: list,
    conversation_history: Optional[list] = None,
    attempted_steps: Optional[list] = None,
    unresolved_turns: int = 0,
) -> AgentResponse:
    """
    Main entry point for a single conversation turn. Performs the escalation
    check first; only calls the LLM for generation if the turn does not need
    to be escalated.
    """
    decision = check_escalation(user_query, context_chunks, unresolved_turns=unresolved_turns)

    if decision.escalate:
        handoff = generate_handoff_summary(
            user_query=user_query,
            persona=persona,
            context_chunks=context_chunks,
            conversation_history=conversation_history,
            attempted_steps=attempted_steps,
            decision=decision,
        )
        escalation_message = (
            "I want to make sure this gets resolved correctly, so I'm connecting you with a "
            "human support specialist who can take it from here. They'll have the full context "
            "of our conversation so you won't need to repeat yourself."
        )
        return AgentResponse(
            escalated=True,
            response_text=escalation_message,
            persona=persona,
            retrieved_sources=context_chunks,
            handoff_summary=handoff,
            escalation_triggers=decision.triggers,
        )

    if not settings.gemini_api_key:
        response_text = _offline_fallback_response(persona, context_chunks)
    else:
        system_prompt = _build_system_prompt(persona, context_chunks)
        try:
            response_text = _call_gemini(system_prompt, user_query)
        except Exception as exc:
            # If generation itself fails after retries, escalate rather than
            # surface a broken/empty response to the customer.
            handoff = generate_handoff_summary(
                user_query=user_query,
                persona=persona,
                context_chunks=context_chunks,
                conversation_history=conversation_history,
                attempted_steps=attempted_steps,
                decision=EscalationDecision(escalate=True, triggers=["generation_api_failure"]),
            )
            return AgentResponse(
                escalated=True,
                response_text=(
                    "I'm having trouble generating a response right now, so I'm connecting "
                    "you with a human support specialist instead."
                ),
                persona=persona,
                retrieved_sources=context_chunks,
                handoff_summary=handoff,
                escalation_triggers=["generation_api_failure"],
            )

    return AgentResponse(
        escalated=False,
        response_text=response_text,
        persona=persona,
        retrieved_sources=context_chunks,
        handoff_summary=None,
        escalation_triggers=[],
    )
