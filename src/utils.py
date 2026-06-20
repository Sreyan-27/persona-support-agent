"""
utils.py
--------
Small shared helpers used across the agent:

  - get_genai_client(): lazily constructs a single Gemini client instance.
  - call_with_backoff(): wraps any API call with exponential backoff + jitter,
    so transient rate limits (429s) or network blips don't crash a
    conversation turn.
"""

import random
import time
from typing import Callable, TypeVar

from src.config import settings

T = TypeVar("T")

_client = None


def get_genai_client():
    """Lazily initialize and cache a single google-genai Client instance."""
    global _client
    if _client is None:
        from google import genai  # imported lazily so the rest of the app can
                                   # be syntax-checked/tested without the SDK installed
        _client = genai.Client(api_key=settings.gemini_api_key)
    return _client


def call_with_backoff(func: Callable[[], T], max_retries: int = 5) -> T:
    """
    Calls `func` with no arguments, retrying on exception with exponential
    backoff and jitter. Re-raises the last exception if all retries fail.

    This is intentionally generic (not Gemini-specific) so it can wrap any
    network call, including embeddings, generation, or future providers.
    """
    last_exc = None
    for attempt in range(max_retries):
        try:
            return func()
        except Exception as exc:  # noqa: BLE001 - we want to retry on anything network-related
            last_exc = exc
            if attempt == max_retries - 1:
                raise
            sleep_time = (2 ** attempt) + random.uniform(0, 1)
            time.sleep(sleep_time)
    raise last_exc  # pragma: no cover - unreachable, kept for safety
