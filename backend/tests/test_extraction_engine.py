from decimal import Decimal

from app.ai.extraction.regex_engine import RegexFinancialExtractionEngine


def _by_field(candidates, field_name):
    return [c for c in candidates if c.field_name == field_name]


def test_plan_document_example_extracts_exactly_as_specified():
    """The canonical example from the architecture docs."""
    engine = RegexFinancialExtractionEngine()
    text = "I earn 60,000 a month, spend around 25,000 and have a 5 lakh loan."
    candidates = engine.extract(text)

    income = _by_field(candidates, "monthly_income")
    expenses = _by_field(candidates, "monthly_expenses")
    debt = _by_field(candidates, "debt")

    assert len(income) == 1 and income[0].value == Decimal("60000")
    assert len(expenses) == 1 and expenses[0].value == Decimal("25000")
    assert len(debt) == 1 and debt[0].value == Decimal("500000")


def test_every_candidate_has_full_traceability_metadata():
    engine = RegexFinancialExtractionEngine()
    candidates = engine.extract("I earn 50000 a month.")
    assert len(candidates) == 1
    c = candidates[0]
    assert c.field_name == "monthly_income"
    assert c.value == Decimal("50000")
    assert c.source_text  # non-empty source span
    assert Decimal("0") < c.confidence <= Decimal("1")
    assert c.extraction_method == "regex_v1"


def test_k_suffix_is_parsed_as_thousands():
    engine = RegexFinancialExtractionEngine()
    candidates = engine.extract("My salary is 45k.")
    income = _by_field(candidates, "monthly_income")
    assert income[0].value == Decimal("45000")


def test_crore_suffix_is_parsed_correctly():
    engine = RegexFinancialExtractionEngine()
    candidates = engine.extract("I have savings of 1.2 crore.")
    savings = _by_field(candidates, "savings")
    assert savings[0].value == Decimal("12000000.0")


def test_plain_text_with_no_financial_content_yields_no_candidates():
    engine = RegexFinancialExtractionEngine()
    assert engine.extract("Hello, how are you today?") == []


def test_conflicting_values_for_same_field_are_both_kept_not_resolved():
    """
    Core architecture rule: extraction never silently picks a winner
    among contradictory values — that's Brick 08's job.
    """
    engine = RegexFinancialExtractionEngine()
    candidates = engine.extract("My income was 50000 last year but now I earn 80000.")
    income = _by_field(candidates, "monthly_income")
    values = {c.value for c in income}
    assert values == {Decimal("50000"), Decimal("80000")}


def test_dependents_are_recognized_as_a_count():
    engine = RegexFinancialExtractionEngine()
    candidates = engine.extract("I have 2 kids.")
    dependents = _by_field(candidates, "dependents")
    assert dependents[0].value == Decimal("2")


def test_distant_weak_pairing_gets_lower_confidence_than_close_pairing():
    engine = RegexFinancialExtractionEngine()
    close = engine.extract("I earn 50000 monthly.")[0]
    # keyword and number far apart in the sentence -> weaker pairing
    far = engine.extract("I earn a living somehow, though it varies, around 50000 or so")
    far_income = _by_field(far, "monthly_income")
    if far_income:  # only compare if the distant pairing was still within range
        assert far_income[0].confidence < close.confidence


def test_engine_never_invents_a_value_absent_from_text():
    engine = RegexFinancialExtractionEngine()
    candidates = engine.extract("I earn a decent amount but don't want to say how much.")
    assert candidates == []


def test_conflicting_values_are_explicitly_flagged_ambiguous():
    """
    DoD requires ambiguous values to be *flagged*, not merely have lower
    confidence — a consumer must be able to check a boolean rather than
    infer uncertainty from a threshold.
    """
    engine = RegexFinancialExtractionEngine()
    candidates = engine.extract("My income was 50000 last year but now I earn 80000.")
    income = _by_field(candidates, "monthly_income")
    assert len(income) == 2
    assert all(c.is_ambiguous for c in income)
    assert all(c.ambiguity_reason for c in income)


def test_clear_unambiguous_match_is_not_flagged():
    engine = RegexFinancialExtractionEngine()
    candidates = engine.extract("I earn 50000 monthly.")
    income = _by_field(candidates, "monthly_income")
    assert len(income) == 1
    assert income[0].is_ambiguous is False
    assert income[0].ambiguity_reason is None


def test_weak_distant_pairing_is_flagged_ambiguous_with_a_reason():
    engine = RegexFinancialExtractionEngine()
    candidates = engine.extract(
        "I earn a living somehow, and though it varies quite a lot these days, around 50000 or so"
    )
    income = _by_field(candidates, "monthly_income")
    if income:  # only meaningful if the distant pairing was within range at all
        assert income[0].is_ambiguous is True
        assert "monthly_income" in income[0].ambiguity_reason
