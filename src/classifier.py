"""
classifier.py
--------------
Detects which of the three target personas a customer message represents:

    1. Technical Expert    - jargon, APIs, logs, configs, wants depth
    2. Frustrated User      - emotional language, urgency, repeated complaints
    3. Business Executive   - outcome-focused, brief, asks about impact/timelines

Strategy
--------
Primary: Gemini structured JSON output (matches the reference implementation
in the assignment doc almost exactly) - the model returns a persona label,
a confidence score, and a short justification.

Fallback: a deterministic keyword/heuristic rule engine. This fires when:
  - No API key is configured (so the CLI/Streamlit app still runs end to end
    for structural testing without a live key), or
  - The Gemini call fails after retries (e.g. transient API error), or
  - The model returns malformed JSON.

Having an explicit rule-based fallback also makes the "classification method
and rules used" easy to document transparently in the README, rather than
treating persona detection as an opaque LLM call.
"""

import json
import re
from dataclasses import dataclass
from typing import Optional

from src.config import settings
from src.utils import call_with_backoff, get_genai_client

VALID_PERSONAS = ("Technical Expert", "Frustrated User", "Business Executive")

CLASSIFIER_SYSTEM_INSTRUCTION = (
    "You are an advanced classification engine for a customer support system. "
    "Analyze the sentiment, vocabulary, and tone of an incoming support message and "
    "classify it into EXACTLY one of three customer personas:\n\n"
    "1. 'Technical Expert': Uses technical jargon, asks about APIs, error codes, logs, "
    "configurations, or wants detailed root-cause explanations.\n"
    "2. 'Frustrated User': Uses emotional language, exclamation marks, words like "
    "'nothing works', urgency, or describes repeated failed attempts.\n"
    "3. 'Business Executive': Focuses on business/operational impact, timelines, "
    "resolution ETAs, cost, or prefers brief, outcome-oriented communication.\n\n"
    "If a message could fit more than one persona, pick the SINGLE strongest signal. "
    "Respond strictly in the requested JSON structure."
)

RESPONSE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "persona": {"type": "STRING", "enum": list(VALID_PERSONAS)},
        "confidence": {"type": "NUMBER"},
        "reasoning": {"type": "STRING"},
    },
    "required": ["persona", "confidence", "reasoning"],
}


@dataclass
class PersonaResult:
    persona: str
    confidence: float
    reasoning: str
    method: str  # "llm" or "rule_based_fallback"


# ---------------------------------------------------------------------------
# Rule-based fallback
# ---------------------------------------------------------------------------
_TECH_PATTERNS = [
    r"\bapi\b", r"\bendpoint\b", r"\berror code\b", r"\b\d{3} (error|unauthorized|forbidden)\b",
    r"\blog(s)?\b", r"\bconfig(uration)?\b", r"\bauthentication\b", r"\bwebhook\b",
    r"\bjson\b", r"\bheader\b", r"\btoken\b", r"\bschema\b", r"\bstack trace\b",
    r"\bdatabase\b", r"\bsdk\b", r"\brate limit\b", r"\bpayload\b",
]
_FRUSTRATED_PATTERNS = [
    r"\bnothing works\b", r"\bnot working\b", r"!{2,}", r"\bfrustrat", r"\bangry\b",
    r"\bawful\b", r"\bterrible\b", r"\bunacceptable\b", r"\bfed up\b", r"\bridiculous\b",
    r"\bstill (broken|not working)\b", r"\bi['’]ve tried everything\b", r"\bimmediately\b",
    r"\bdemand\b", r"\bworst\b",
]
_EXEC_PATTERNS = [
    r"\bbusiness impact\b", r"\boperations?\b", r"\btimeline\b", r"\bresolution time\b",
    r"\bsla\b", r"\bwhen will\b", r"\bcost\b", r"\brevenue\b", r"\buptime\b",
    r"\bstakeholders?\b", r"\bexecutive\b", r"\bcontract\b", r"\bour team\b",
]


def _rule_based_classify(message: str) -> PersonaResult:
    text = message.lower()
    scores = {
        "Technical Expert": sum(1 for p in _TECH_PATTERNS if re.search(p, text)),
        "Frustrated User": sum(1 for p in _FRUSTRATED_PATTERNS if re.search(p, text)),
        "Business Executive": sum(1 for p in _EXEC_PATTERNS if re.search(p, text)),
    }
    best_persona = max(scores, key=scores.get)
    best_score = scores[best_persona]

    if best_score == 0:
        # No strong signal either way -> default to Frustrated User is unsafe;
        # default to Technical Expert is unsafe too. We default to the persona
        # that yields the SAFEST response style: clear, moderately detailed,
        # non-presumptuous. Business Executive's concise/neutral tone is the
        # least likely to feel condescending or overly casual if wrong.
        return PersonaResult(
            persona="Business Executive",
            confidence=0.34,
            reasoning="No strong lexical signal for any persona; defaulted to the "
                      "neutral, concise communication style.",
            method="rule_based_fallback",
        )

    total = sum(scores.values()) or 1
    confidence = round(min(0.95, 0.5 + (best_score / total) * 0.45), 2)
    reasoning = (
        f"Keyword-based match: {best_score} signal(s) for '{best_persona}' "
        f"(scores={scores})."
    )
    return PersonaResult(best_persona, confidence, reasoning, method="rule_based_fallback")


# ---------------------------------------------------------------------------
# LLM-based classification (primary)
# ---------------------------------------------------------------------------
def _llm_classify(message: str) -> Optional[PersonaResult]:
    if not settings.gemini_api_key:
        return None

    try:
        client = get_genai_client()
        from google.genai import types  # local import keeps module importable without the SDK

        def _call():
            return client.models.generate_content(
                model=settings.generation_model,
                contents=message,
                config=types.GenerateContentConfig(
                    system_instruction=CLASSIFIER_SYSTEM_INSTRUCTION,
                    response_mime_type="application/json",
                    response_schema=RESPONSE_SCHEMA,
                    temperature=0.1,
                ),
            )

        response = call_with_backoff(_call, max_retries=settings.max_api_retries)
        payload = json.loads(response.text)

        persona = payload.get("persona")
        if persona not in VALID_PERSONAS:
            return None

        return PersonaResult(
            persona=persona,
            confidence=float(payload.get("confidence", 0.7)),
            reasoning=payload.get("reasoning", ""),
            method="llm",
        )
    except Exception:
        # Any failure (network, malformed JSON, quota, etc.) falls through
        # to the rule-based fallback below — the agent must never crash on
        # a classification failure.
        return None


def classify_customer_persona(user_message: str) -> PersonaResult:
    """
    Public entry point. Tries the Gemini-based classifier first; falls back
    to deterministic keyword rules if the API is unavailable or fails.
    """
    result = _llm_classify(user_message)
    if result is not None:
        return result
    return _rule_based_classify(user_message)
