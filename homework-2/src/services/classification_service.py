"""Keyword-based automatic ticket categorization and priority assignment."""

import logging

from src.models.ticket import Category, ClassificationResult, Priority

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Keyword maps
# ---------------------------------------------------------------------------

_CATEGORY_KEYWORDS: dict[Category, list[str]] = {
    Category.account_access: [
        "login",
        "password",
        "2fa",
        "two-factor",
        "two factor",
        "sign in",
        "signin",
        "account",
        "locked",
        "locked out",
        "authentication",
        "forgot password",
        "reset password",
        "access denied",
        "unauthorized",
    ],
    Category.technical_issue: [
        "error",
        "crash",
        "exception",
        "broken",
        "not working",
        "failed",
        "failure",
        "outage",
        "down",
        "unavailable",
        "slow",
        "timeout",
        "glitch",
        "issue",
        "problem",
    ],
    Category.billing_question: [
        "payment",
        "invoice",
        "refund",
        "charge",
        "billing",
        "subscription",
        "pricing",
        "cost",
        "fee",
        "receipt",
        "overpaid",
        "overcharged",
        "plan",
        "renewal",
    ],
    Category.feature_request: [
        "feature",
        "enhancement",
        "suggestion",
        "improve",
        "would like",
        "please add",
        "request",
        "wish",
        "could you",
        "add support",
        "new functionality",
        "consider adding",
    ],
    Category.bug_report: [
        "reproduce",
        "steps to reproduce",
        "defect",
        "regression",
        "expected behavior",
        "actual behavior",
        "workaround",
        "replicat",
    ],
}

# Priority keywords ordered from highest to lowest — first match wins for ties
_PRIORITY_KEYWORDS: dict[Priority, list[str]] = {
    Priority.urgent: [
        "can't access",
        "cannot access",
        "critical",
        "production down",
        "security",
        "emergency",
        "immediately",
        "data loss",
        "breach",
        "severe",
        "urgent",
    ],
    Priority.high: [
        "important",
        "blocking",
        "asap",
        "high priority",
        "needs immediate",
        "as soon as possible",
    ],
    Priority.low: [
        "minor",
        "cosmetic",
        "nice to have",
        "low priority",
        "whenever",
        "not urgent",
        "suggestion",
        "trivial",
    ],
}

_PRIORITY_OVERRIDES: dict[Priority, list[str]] = {
    Priority.low: ["not urgent"],
}


# ---------------------------------------------------------------------------
# Confidence formula
# ---------------------------------------------------------------------------


def _confidence(match_count: int) -> float:
    """Convert keyword match count to a 0–1 confidence score."""
    if match_count == 0:
        return 0.2
    if match_count == 1:
        return 0.5
    if match_count == 2:
        return 0.7
    return min(0.95, 0.7 + 0.1 * (match_count - 2))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def classify(subject: str, description: str) -> ClassificationResult:
    """Classify a ticket by keyword analysis of subject and description."""
    text = (subject + " " + description).lower()

    # --- Category ---
    category_scores: dict[Category, list[str]] = {}
    for category, keywords in _CATEGORY_KEYWORDS.items():
        matched = [kw for kw in keywords if kw in text]
        if matched:
            category_scores[category] = matched

    if category_scores:
        best_category = max(category_scores, key=lambda c: len(category_scores[c]))
        cat_keywords = category_scores[best_category]
    else:
        best_category = Category.other
        cat_keywords = []

    cat_confidence = _confidence(len(cat_keywords))

    # --- Priority ---
    priority_keywords_found: list[str] = []
    best_priority = Priority.medium

    for priority, keywords in _PRIORITY_OVERRIDES.items():
        matched = [kw for kw in keywords if kw in text]
        if matched:
            best_priority = priority
            priority_keywords_found = matched
            break
    else:
        for priority in (Priority.urgent, Priority.high, Priority.low):
            matched = [kw for kw in _PRIORITY_KEYWORDS[priority] if kw in text]
            if matched:
                best_priority = priority
                priority_keywords_found = matched
                break

    pri_confidence = _confidence(len(priority_keywords_found)) if priority_keywords_found else 0.5

    # Combined confidence = average of category and priority confidences
    overall_confidence = round((cat_confidence + pri_confidence) / 2, 4)

    all_keywords = cat_keywords + priority_keywords_found

    # Build human-readable reasoning
    reasoning_parts: list[str] = []
    if cat_keywords:
        reasoning_parts.append(
            f"Category '{best_category}' matched keywords: {', '.join(cat_keywords)}."
        )
    else:
        reasoning_parts.append("No category keywords found; defaulting to 'other'.")
    if priority_keywords_found:
        reasoning_parts.append(
            f"Priority '{best_priority}' matched keywords: {', '.join(priority_keywords_found)}."
        )
    else:
        reasoning_parts.append("No priority keywords found; defaulting to 'medium'.")

    reasoning = " ".join(reasoning_parts)

    result = ClassificationResult(
        category=best_category,
        priority=best_priority,
        confidence=overall_confidence,
        reasoning=reasoning,
        keywords_found=all_keywords,
    )

    logger.info(
        "Auto-classification decision: category=%s priority=%s confidence=%.4f keywords=%s",
        result.category,
        result.priority,
        result.confidence,
        result.keywords_found,
    )

    return result
