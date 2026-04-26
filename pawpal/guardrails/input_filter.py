"""Lightweight pre-flight filter for user queries.

Catches three classes of inputs that should not reach the RAG pipeline:

1. **Out-of-scope** — the user is asking about something clearly unrelated
   to pet care (stocks, weather, news). Answering would burn tokens and risk
   hallucinated nonsense.
2. **Medical-diagnosis requests** — "is my dog dying?" type questions that
   should be redirected to a vet, not answered by an LLM.
3. **Personal data leakage** — phone numbers, SSNs, emails. We refuse to
   process them so they never reach a third-party LLM.

This is intentionally a coarse keyword/regex filter. Phase 3 may layer a
classifier on top; for now simple rules give us deterministic behaviour
that is easy to test and explain.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

# Topic keywords that strongly suggest the query is about pets at all.
_PET_KEYWORDS = (
    "pet", "pets",
    "dog", "dogs", "puppy", "puppies",
    "cat", "cats", "kitten", "kittens",
    "bird", "birds", "parrot", "canary",
    "rabbit", "rabbits", "bunny",
    "hamster", "guinea pig",
    "reptile", "lizard", "snake", "turtle", "tortoise",
    "fish", "aquarium",
    "vet", "veterinarian", "vaccine", "vaccinated",
    "litter box", "leash", "collar",
    "groom", "grooming",
    "feed", "feeding", "food", "diet", "treat",
    "walk", "walking", "exercise",
    "spay", "neuter",
    "flea", "tick", "worm",
)

_OFFTOPIC_HARD_BLOCKS = (
    r"\bstock\s+price\b",
    r"\bcrypto\b",
    r"\bbitcoin\b",
    r"\bweather\b",
    r"\bnews\b",
    r"\belection\b",
    r"\bmovie\b.*\brecommend",
    r"\bhomework\b",
    r"\bessay\b",
    r"\bwrite\s+code\b",
)

_DIAGNOSIS_PATTERNS = (
    r"\bis\s+my\s+(dog|cat|pet|puppy|kitten)\s+(dying|sick|ok|okay|fine)\b",
    r"\bdoes\s+my\s+(dog|cat|pet)\s+have\b",
    r"\bdiagnose\b",
    r"\bwhat\s+disease\b",
    r"\bsymptom(s)?\s+of\b",
)

# Simplified PII detectors: full SSN / phone / email patterns.
_PII_PATTERNS = (
    r"\b\d{3}-\d{2}-\d{4}\b",                  # US SSN
    r"\b\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}\b",  # US phone
    r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b",            # email
)


@dataclass
class PreflightResult:
    allowed: bool
    reason: Optional[str]
    safe_answer: Optional[str]


def preflight(query: str) -> PreflightResult:
    """Decide whether ``query`` should reach the RAG pipeline."""
    if not query or not query.strip():
        return PreflightResult(
            allowed=False,
            reason="empty_query",
            safe_answer="Please type a question about your pet.",
        )

    text = query.strip()

    for pat in _PII_PATTERNS:
        if re.search(pat, text):
            return PreflightResult(
                allowed=False,
                reason="pii_detected",
                safe_answer=(
                    "I noticed something that looks like personal data "
                    "(phone, email, or ID). Please rephrase your question "
                    "without those details and I'll happily help."
                ),
            )

    lowered = text.lower()
    for pat in _OFFTOPIC_HARD_BLOCKS:
        if re.search(pat, lowered):
            return PreflightResult(
                allowed=False,
                reason="off_topic",
                safe_answer=(
                    "I'm a pet-care assistant, so I can only help with "
                    "questions about your pet's health, feeding, training, "
                    "or routine."
                ),
            )

    for pat in _DIAGNOSIS_PATTERNS:
        if re.search(pat, lowered):
            return PreflightResult(
                allowed=False,
                reason="medical_diagnosis",
                safe_answer=(
                    "I can't diagnose medical conditions. If you're worried "
                    "about your pet's health, please contact a veterinarian "
                    "— they can examine the animal and run the right tests."
                ),
            )

    if not any(kw in lowered for kw in _PET_KEYWORDS):
        # Unknown but not obviously off-topic. Let it pass; downstream
        # retrieval threshold (Q3) will short-circuit if the KB has nothing.
        pass

    return PreflightResult(allowed=True, reason=None, safe_answer=None)
