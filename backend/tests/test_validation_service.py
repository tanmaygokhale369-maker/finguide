from decimal import Decimal

from app.models.extracted_field import ExtractedField
from app.models.user import User
from app.models.validation_status import ValidationStatus
from app.services.validation_service import (
    TRACKED_FIELDS,
    get_all_field_summaries,
    get_field_summary,
    revalidate_field,
)


def _make_message(db_session, user):
    """Creates a minimal conversation+message to satisfy ExtractedField's
    FK requirement, since these tests exercise the validation service
    directly rather than going through the chat API."""
    from app.models.conversation import Conversation
    from app.models.message import Message, MessageRole

    conversation = Conversation(user_id=user.id)
    db_session.add(conversation)
    db_session.flush()
    message = Message(conversation_id=conversation.id, role=MessageRole.USER, content="test")
    db_session.add(message)
    db_session.flush()
    return message


def _add_extracted_field(db_session, user, message, field_name, value, confidence, is_ambiguous=False):
    row = ExtractedField(
        message_id=message.id,
        user_id=user.id,
        field_name=field_name,
        value=Decimal(value),
        source_text="test source",
        confidence=Decimal(confidence),
        extraction_method="regex_v1",
        is_ambiguous=is_ambiguous,
    )
    db_session.add(row)
    db_session.flush()
    return row


def _make_user(db_session, email="validation-test@example.com"):
    user = User(email=email)
    db_session.add(user)
    db_session.flush()
    return user


def test_field_with_no_data_is_incomplete(db_session):
    user = _make_user(db_session)
    summary = get_field_summary(db_session, user.id, "monthly_income")
    assert summary.status == ValidationStatus.INCOMPLETE
    assert summary.value is None


def test_single_high_confidence_value_is_valid(db_session):
    user = _make_user(db_session)
    message = _make_message(db_session, user)
    _add_extracted_field(db_session, user, message, "monthly_income", "60000", "0.90")
    revalidate_field(db_session, user.id, "monthly_income")

    summary = get_field_summary(db_session, user.id, "monthly_income")
    assert summary.status == ValidationStatus.VALID
    assert summary.value == Decimal("60000")


def test_single_low_confidence_value_is_flagged_low_confidence(db_session):
    user = _make_user(db_session)
    message = _make_message(db_session, user)
    _add_extracted_field(db_session, user, message, "monthly_income", "60000", "0.50")
    revalidate_field(db_session, user.id, "monthly_income")

    summary = get_field_summary(db_session, user.id, "monthly_income")
    assert summary.status == ValidationStatus.LOW_CONFIDENCE
    assert summary.value == Decimal("60000")


def test_conflicting_values_do_not_silently_pick_a_winner(db_session):
    """Core architecture rule: a contradiction must never be silently
    resolved by picking one value."""
    user = _make_user(db_session)
    message = _make_message(db_session, user)
    _add_extracted_field(db_session, user, message, "monthly_income", "50000", "0.90")
    _add_extracted_field(db_session, user, message, "monthly_income", "80000", "0.90")
    revalidate_field(db_session, user.id, "monthly_income")

    summary = get_field_summary(db_session, user.id, "monthly_income")
    assert summary.status == ValidationStatus.REQUIRES_CLARIFICATION
    assert summary.value is None  # no winner picked
    assert len(summary.contributing_field_ids) == 2


def test_conflict_detected_across_different_messages_not_just_within_one(db_session):
    """
    The doc's own example: income=50000 mentioned, then later
    income=80000 mentioned — in *separate* messages, not one sentence.
    Brick 07's is_ambiguous only catches same-message conflicts; cross-
    message conflicts are Brick 08's job.
    """
    user = _make_user(db_session)
    message_1 = _make_message(db_session, user)
    message_2 = _make_message(db_session, user)  # a distinct message
    _add_extracted_field(db_session, user, message_1, "monthly_income", "50000", "0.90")
    _add_extracted_field(db_session, user, message_2, "monthly_income", "80000", "0.90")
    revalidate_field(db_session, user.id, "monthly_income")

    summary = get_field_summary(db_session, user.id, "monthly_income")
    assert summary.status == ValidationStatus.REQUIRES_CLARIFICATION
    assert summary.value is None


def test_out_of_range_value_is_rejected(db_session):
    user = _make_user(db_session)
    message = _make_message(db_session, user)
    _add_extracted_field(db_session, user, message, "dependents", "500", "0.90")  # absurd dependents count
    revalidate_field(db_session, user.id, "dependents")

    summary = get_field_summary(db_session, user.id, "dependents")
    assert summary.status == ValidationStatus.REJECTED
    assert summary.value is None


def test_rejected_value_never_becomes_the_winner_even_if_newest(db_session):
    user = _make_user(db_session)
    message = _make_message(db_session, user)
    _add_extracted_field(db_session, user, message, "dependents", "3", "0.90")
    _add_extracted_field(db_session, user, message, "dependents", "999", "0.95")  # newer, higher confidence, but absurd
    revalidate_field(db_session, user.id, "dependents")

    summary = get_field_summary(db_session, user.id, "dependents")
    assert summary.status == ValidationStatus.VALID
    assert summary.value == Decimal("3")


def test_new_conflicting_value_flips_an_old_valid_row_to_conflicting(db_session):
    """Revalidation re-evaluates the *entire* history, so a value
    considered VALID before a contradiction shows up must become
    CONFLICTING once one does."""
    user = _make_user(db_session)
    message = _make_message(db_session, user)
    row1 = _add_extracted_field(db_session, user, message, "monthly_income", "60000", "0.90")
    revalidate_field(db_session, user.id, "monthly_income")
    assert row1.validation_status == ValidationStatus.VALID

    _add_extracted_field(db_session, user, message, "monthly_income", "90000", "0.90")
    revalidate_field(db_session, user.id, "monthly_income")
    db_session.flush()

    assert row1.validation_status == ValidationStatus.CONFLICTING


def test_repeated_identical_value_reinforces_rather_than_conflicts(db_session):
    user = _make_user(db_session)
    message = _make_message(db_session, user)
    _add_extracted_field(db_session, user, message, "monthly_income", "60000", "0.60")
    _add_extracted_field(db_session, user, message, "monthly_income", "60000", "0.60")
    revalidate_field(db_session, user.id, "monthly_income")

    summary = get_field_summary(db_session, user.id, "monthly_income")
    assert summary.status in (ValidationStatus.VALID, ValidationStatus.LOW_CONFIDENCE)
    assert summary.value == Decimal("60000")


def test_get_all_field_summaries_covers_every_tracked_field(db_session):
    user = _make_user(db_session)
    summaries = get_all_field_summaries(db_session, user.id)
    assert {s.field_name for s in summaries} == set(TRACKED_FIELDS)
    assert all(s.status == ValidationStatus.INCOMPLETE for s in summaries)


def test_untracked_field_name_is_a_no_op(db_session):
    user = _make_user(db_session)
    # Should not raise even though "not_a_real_field" isn't tracked.
    revalidate_field(db_session, user.id, "not_a_real_field")
