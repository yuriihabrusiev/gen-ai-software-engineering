import logging

from src.models.ticket import Category, Priority
from src.services import classification_service


def test_classifies_account_access() -> None:
    result = classification_service.classify("Login failed", "Password reset keeps failing.")

    assert result.category == Category.account_access
    assert "login" in result.keywords_found


def test_classifies_technical_issue() -> None:
    result = classification_service.classify("App crash", "The application crashes with an error.")

    assert result.category == Category.technical_issue


def test_classifies_billing_question() -> None:
    result = classification_service.classify("Invoice", "I need a refund for a duplicate charge.")

    assert result.category == Category.billing_question


def test_classifies_feature_request() -> None:
    result = classification_service.classify("Suggestion", "Please add support for dark mode.")

    assert result.category == Category.feature_request


def test_classifies_bug_report() -> None:
    result = classification_service.classify(
        "Regression",
        "Steps to reproduce include expected behavior and actual behavior.",
    )

    assert result.category == Category.bug_report


def test_defaults_to_other_and_medium() -> None:
    result = classification_service.classify(
        "Hello", "I have a question about something unrelated."
    )

    assert result.category == Category.other
    assert result.priority == Priority.medium


def test_urgent_priority_takes_precedence() -> None:
    result = classification_service.classify(
        "Important but critical",
        "This is important and critical for production down recovery.",
    )

    assert result.priority == Priority.urgent


def test_high_priority_keywords() -> None:
    result = classification_service.classify("Blocking issue", "Please handle this asap.")

    assert result.priority == Priority.high


def test_low_priority_keywords() -> None:
    result = classification_service.classify("Cosmetic", "This is a minor suggestion.")

    assert result.priority == Priority.low


def test_confidence_increases_with_more_keywords() -> None:
    weak = classification_service.classify("Login", "A valid description without much else.")
    strong = classification_service.classify(
        "Login password 2FA",
        "Locked out with authentication access denied and cannot access anything.",
    )

    assert strong.confidence > weak.confidence


def test_reasoning_mentions_defaults() -> None:
    result = classification_service.classify("Hello", "General question that has no mapped words.")

    assert "defaulting to 'other'" in result.reasoning
    assert "defaulting to 'medium'" in result.reasoning


def test_classification_logs_decision(caplog) -> None:  # type: ignore[no-untyped-def]
    with caplog.at_level(logging.INFO):
        classification_service.classify("Invoice", "Refund requested for duplicate payment.")

    assert "Auto-classification decision" in caplog.text
