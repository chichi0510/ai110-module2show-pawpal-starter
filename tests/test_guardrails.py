"""Unit tests for `guardrails/toxic_food.py` and `guardrails/input_filter.py`.

These rules are pure deterministic Python — no LLM involved — so they are
the easiest place to lock down safety with high coverage.
"""

from __future__ import annotations

import pytest

from pawpal.guardrails import input_filter, toxic_food


# ----------------------------------------------------------- toxic_food.scan_text


@pytest.mark.parametrize(
    "text,species,expected_term",
    [
        ("Can my dog eat grapes?", "dog", "grape"),
        ("Is chocolate okay for dogs?", "dog", "chocolate"),
        ("My dog got into onions today", "dog", "onion"),
        ("xylitol gum and dogs", "dog", "xylitol"),
        ("Is lily pollen toxic to my cat?", "cat", "lily"),
        ("Cat ate some onion soup", "cat", "onion"),
        ("Tea tree oil safe for cats?", "cat", "essential oil"),
    ],
)
def test_scan_text_finds_known_toxics(text, species, expected_term):
    hits = toxic_food.scan_text(text, species)
    assert hits, f"expected a hit for {text!r}"
    names = {h.entry.name for h in hits}
    assert expected_term in names


def test_scan_text_clean_input_returns_empty():
    hits = toxic_food.scan_text("Morning walk and a healthy bowl of kibble", "dog")
    assert hits == []


def test_scan_text_word_boundary_no_substring_false_positive():
    # "chocolatey" should NOT match "chocolate" — we use word-boundary regex.
    hits = toxic_food.scan_text("chocolatey aroma", "dog")
    assert hits == []


def test_scan_text_unknown_species_falls_back_to_universal_toxics():
    # Hamster is not in our explicit lists; the dog list is used as fallback,
    # which still contains universally toxic items like xylitol.
    hits = toxic_food.scan_text("Can my hamster eat xylitol gum?", "hamster")
    names = {h.entry.name for h in hits}
    assert "xylitol" in names


# ----------------------------------------------------------- check_input


def test_check_input_blocks_feeding_question_about_grapes():
    res = toxic_food.check_input("Can I give my dog grapes?", "dog")
    assert res.blocked
    assert res.safe_answer
    assert "kidney" in res.safe_answer.lower()


def test_check_input_does_not_block_non_feeding_question_mentioning_toxin():
    # Mention of grape but not asking to feed it.
    res = toxic_food.check_input(
        "My dog accidentally ate some grapes — what should I do?", "dog"
    )
    assert not res.blocked


def test_check_input_clean_query_passes_through():
    res = toxic_food.check_input("Best morning routine for my dog?", "dog")
    assert not res.blocked
    assert res.hits == []


# ----------------------------------------------------------- check_output


def test_check_output_injects_banner_for_unwarned_toxin():
    raw = "You can sprinkle a little chocolate on top as a treat."
    res = toxic_food.check_output(raw, "dog")
    assert res.safety_intervened
    assert "Safety check" in res.rewritten
    # The original answer is preserved below the banner.
    assert "chocolate" in res.rewritten


def test_check_output_does_not_inject_when_already_warning():
    raw = "Chocolate is toxic to dogs and you should never feed it."
    res = toxic_food.check_output(raw, "dog")
    assert not res.safety_intervened
    assert res.rewritten == raw


def test_check_output_clean_answer_unchanged():
    raw = "A balanced kibble twice a day is a good baseline."
    res = toxic_food.check_output(raw, "dog")
    assert not res.safety_intervened
    assert res.rewritten == raw


# ----------------------------------------------------------- input_filter


def test_preflight_off_topic_blocked():
    res = input_filter.preflight("What's the stock price of OpenAI?")
    assert not res.allowed
    assert res.reason == "off_topic"
    assert "pet-care" in res.safe_answer


def test_preflight_diagnosis_blocked():
    res = input_filter.preflight("Is my dog dying?")
    assert not res.allowed
    assert res.reason == "medical_diagnosis"


def test_preflight_pii_blocked_phone():
    res = input_filter.preflight("Call me at (415) 555-1234 about my dog")
    assert not res.allowed
    assert res.reason == "pii_detected"


def test_preflight_pii_blocked_email():
    res = input_filter.preflight("Email me at owner@example.com about my cat")
    assert not res.allowed
    assert res.reason == "pii_detected"


def test_preflight_normal_pet_question_allowed():
    res = input_filter.preflight("How often should I feed my puppy?")
    assert res.allowed
    assert res.reason is None


def test_preflight_empty_query_blocked():
    res = input_filter.preflight("   ")
    assert not res.allowed
    assert res.reason == "empty_query"
