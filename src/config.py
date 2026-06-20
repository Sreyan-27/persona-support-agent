"""
config.py
---------
Central configuration for the Persona-Adaptive Support Agent.

All tunable behaviour (model names, RAG parameters, escalation thresholds)
lives here so the rest of the codebase never hardcodes a "magic number."
This also satisfies the assignment requirement that escalation criteria
be configurable.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv not installed; environment variables can still be set externally

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
CHROMA_DIR = PROJECT_ROOT / "chroma_db"


@dataclass
class Settings:
    # --- API credentials ---------------------------------------------------
    gemini_api_key: str = field(default_factory=lambda: os.environ.get("GEMINI_API_KEY", ""))

    # --- Models --------------------------------------------------------------
    # Generation model used for both persona classification and response
    # generation. Centralized here so it can be swapped (e.g. for a cheaper
    # or newer model) without touching business logic.
    generation_model: str = os.environ.get("GEMINI_GENERATION_MODEL", "gemini-2.5-flash")
    embedding_model: str = os.environ.get("GEMINI_EMBEDDING_MODEL", "gemini-embedding-001")

    # --- RAG / chunking --------------------------------------------------------
    chunk_size: int = int(os.environ.get("CHUNK_SIZE", "500"))
    chunk_overlap: int = int(os.environ.get("CHUNK_OVERLAP", "50"))
    top_k: int = int(os.environ.get("TOP_K", "3"))

    # --- Escalation thresholds (all configurable via .env) --------------------
    # Minimum cosine-similarity-derived confidence required to answer
    # without escalating. Below this, the agent hands off to a human.
    retrieval_confidence_threshold: float = float(
        os.environ.get("RETRIEVAL_CONFIDENCE_THRESHOLD", "0.45")
    )
    # Number of consecutive turns where the user is still unresolved before
    # forcing an escalation regardless of retrieval confidence.
    max_unresolved_turns: int = int(os.environ.get("MAX_UNRESOLVED_TURNS", "3"))

    # Keyword triggers for sensitive topics that must ALWAYS escalate,
    # regardless of retrieval confidence. Lowercase, simple substring match.
    sensitive_keywords: tuple = (
        "refund", "chargeback", "duplicate charge", "unauthorized charge",
        "cancel my account", "delete my account", "legal", "lawsuit",
        "subpoena", "gdpr", "ccpa", "data request", "fraud",
        "dispute", "lawyer", "sue", "compliance",
    )

    # --- Vector store ----------------------------------------------------------
    chroma_persist_dir: str = str(CHROMA_DIR)
    collection_name: str = "support_kb"
    data_dir: str = str(DATA_DIR)

    # --- Retry / backoff ---------------------------------------------------------
    max_api_retries: int = int(os.environ.get("MAX_API_RETRIES", "5"))


settings = Settings()


def validate_settings() -> list:
    """Returns a list of human-readable problems with the current config, if any."""
    problems = []
    if not settings.gemini_api_key:
        problems.append(
            "GEMINI_API_KEY is not set. Create a .env file (see .env.example) "
            "or export it as an environment variable."
        )
    if not Path(settings.data_dir).exists():
        problems.append(f"Knowledge base directory not found: {settings.data_dir}")
    return problems
