"""Phase 3 — runtime bias filter heuristics."""

from __future__ import annotations

from pawpal.guardrails import bias_filter


class _FakeChunk:
    """Minimal stand-in for `pawpal.rag.models.Chunk` — only need truthy len."""


def test_zero_retrieval_emits_warning_with_species():
    warnings = bias_filter.scan_answer(
        "generic answer", species="rabbit", retrieved_chunks=[]
    )
    assert len(warnings) == 1
    assert warnings[0].kind == "zero_retrieval"
    assert "rabbit" in warnings[0].message
    assert warnings[0].meta["retrieval_count"] == 0


def test_zero_retrieval_without_species_still_works():
    warnings = bias_filter.scan_answer(
        "generic answer", species=None, retrieved_chunks=None
    )
    assert len(warnings) == 1
    assert warnings[0].kind == "zero_retrieval"


def test_short_answer_for_underrepresented_species_is_flagged():
    warnings = bias_filter.scan_answer(
        "feed pellets",  # very short
        species="hamster",
        retrieved_chunks=[_FakeChunk(), _FakeChunk()],
    )
    assert any(w.kind == "possibly_underspecified" for w in warnings)


def test_long_answer_for_underrepresented_species_is_not_flagged():
    long_answer = "Feed your hamster a balanced diet of high-quality pellets " * 8
    warnings = bias_filter.scan_answer(
        long_answer,
        species="hamster",
        retrieved_chunks=[_FakeChunk(), _FakeChunk()],
    )
    assert not any(w.kind == "possibly_underspecified" for w in warnings)


def test_short_answer_for_dog_is_not_flagged():
    warnings = bias_filter.scan_answer(
        "feed twice daily", species="dog", retrieved_chunks=[_FakeChunk()]
    )
    assert not any(w.kind == "possibly_underspecified" for w in warnings)


def test_warnings_to_dicts_returns_jsonable_payload():
    ws = bias_filter.scan_answer("x", species="rabbit", retrieved_chunks=[])
    payload = bias_filter.warnings_to_dicts(ws)
    assert isinstance(payload, list)
    assert payload[0]["kind"] == "zero_retrieval"
    assert isinstance(payload[0]["message"], str)
    assert isinstance(payload[0]["meta"], dict)


def test_underrepresented_species_set_includes_expected_values():
    assert "hamster" in bias_filter.UNDERREPRESENTED_SPECIES
    assert "rabbit" in bias_filter.UNDERREPRESENTED_SPECIES
    assert "bird" in bias_filter.UNDERREPRESENTED_SPECIES
    assert "dog" not in bias_filter.UNDERREPRESENTED_SPECIES
    assert "cat" not in bias_filter.UNDERREPRESENTED_SPECIES
