"""
tests/test_offline.py
----------------------
Quick sanity checks that DON'T require a Gemini API key or network access,
covering the parts of the pipeline that are pure logic: document loading,
chunking, rule-based persona classification fallback, and escalation
trigger logic. Useful to run first to confirm your environment + data
folder are set up correctly before spending API quota.

Usage:
    python -m tests.test_offline
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.classifier import _rule_based_classify  # noqa: E402
from src.escalator import check_escalation  # noqa: E402
from src.rag_pipeline import load_and_chunk_documents  # noqa: E402

TEST_MESSAGES = [
    ("Can you explain the API authentication failure and provide error details?", "Technical Expert"),
    ("I've tried everything and nothing works! This is so frustrating!!", "Frustrated User"),
    ("How does this issue impact operations and when will it be resolved?", "Business Executive"),
    ("My billing statement has unexpected duplicate charges. I demand an immediate refund!", "Frustrated User"),
    ("What are the header parameter requirements for your bearer token auth implementation?", "Technical Expert"),
]


def test_document_loading():
    chunks = load_and_chunk_documents()
    assert len(chunks) > 0, "No chunks were loaded from /data — check the data directory."
    sources = sorted({c.source for c in chunks})
    print(f"[OK] Loaded {len(chunks)} chunks from {len(sources)} documents:")
    for s in sources:
        print(f"     - {s}")
    pdf_sources = [s for s in sources if s.lower().endswith(".pdf")]
    assert pdf_sources, "Assignment requires at least one PDF in the knowledge base."
    print(f"[OK] Found required PDF document: {pdf_sources}")


def test_rule_based_classification():
    print("\nRule-based persona classification (fallback path, no API needed):")
    correct = 0
    for msg, expected in TEST_MESSAGES:
        result = _rule_based_classify(msg)
        match = "✓" if result.persona == expected else "✗"
        if result.persona == expected:
            correct += 1
        print(f"  {match} '{msg[:55]}...' -> {result.persona} (expected {expected})")
    print(f"[INFO] Rule-based fallback matched {correct}/{len(TEST_MESSAGES)} expected personas.")
    print("       (The primary Gemini classifier is expected to be more accurate; this")
    print("        fallback only needs to be reasonable, not perfect.)")


def test_escalation_logic():
    print("\nEscalation trigger logic:")
    no_chunks_decision = check_escalation("random query", [], unresolved_turns=0)
    assert no_chunks_decision.escalate, "Should escalate when no chunks are retrieved."
    print("  [OK] Escalates on zero retrieved chunks")

    sensitive_decision = check_escalation(
        "I want a refund for the duplicate charge", [{"score": 0.9, "source": "billing_policy.txt"}]
    )
    assert sensitive_decision.escalate, "Should escalate on sensitive billing keyword."
    print("  [OK] Escalates on sensitive keyword ('refund')")

    safe_decision = check_escalation(
        "How do I reset my password?", [{"score": 0.8, "source": "password_reset_guide.pdf"}]
    )
    assert not safe_decision.escalate, "Should NOT escalate on a confident, non-sensitive match."
    print("  [OK] Does NOT escalate on confident, non-sensitive retrieval")


if __name__ == "__main__":
    print("=" * 60)
    print("OFFLINE SANITY CHECKS (no API key / network required)")
    print("=" * 60)
    test_document_loading()
    test_rule_based_classification()
    test_escalation_logic()
    print("\nAll offline checks passed.")
