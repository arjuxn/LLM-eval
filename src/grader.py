"""Deterministic answer and retrieval grading for the controlled benchmark.

The answer grader accepts a small, explicit set of wording variants for known
benchmark facts. This keeps grading reproducible while avoiding false failures
caused only by harmless grammatical or punctuation differences. It is not an
open-ended semantic or LLM-based judge.
"""
from __future__ import annotations
import re
from typing import Any


def _norm(value: Any) -> str:
    """Normalize case, punctuation, slash variants, and whitespace."""
    text = str(value).strip().lower()
    text = text.replace("’", "'").replace("–", "-").replace("—", "-")
    # Treat common separators consistently without deleting meaningful words.
    text = text.replace("/", " or ")
    text = re.sub(r"[^a-z0-9%.'+-]+", " ", text)
    return " ".join(text.split())


# Explicitly reviewed, deterministic alternatives for phrases in this benchmark.
# Keep this list fixed before the final experiment run; do not add variants merely
# to make a particular model run pass after seeing its answers.
_PHRASE_ALIASES: dict[str, tuple[str, ...]] = {
    "isolate one factor's contribution": (
        "isolate one factor's contribution",
        "isolate the contribution of one factor",
        "isolating the contribution of one factor",
        "to isolate the contribution of one factor",
        "to isolate one factor's contribution",
    ),
    "not f1": (
        "not f1",
        "rather than f1",
        "instead of f1",
        "rather than the f1 score",
        "not the f1 score",
    ),
    "synthetic or simulated data": (
        "synthetic or simulated data",
        "simulated or synthetic data",
        "synthetic and simulated data",
        "synthetic simulated data",
        "synthetic data",
        "simulated data",
    ),
    "no real-world validation": (
        "no real-world validation",
        "without real-world validation",
        "without validation on real-world data",
        "lacks real-world validation",
        "lack of real-world validation",
    ),
    "under 500mb": (
        "under 500mb",
        "less than 500mb",
        "below 500mb",
    ),
    "without a network connection": (
        "without a network connection",
        "without network connectivity",
        "with no network connection",
        "without internet access",
        "offline",
    ),
}


def _variants(expected: str) -> tuple[str, ...]:
    normalized = _norm(expected)
    aliases = _PHRASE_ALIASES.get(normalized, ())
    return tuple(dict.fromkeys(_norm(item) for item in (expected, *aliases)))


def _contains_phrase(text: str, expected: str) -> bool:
    normalized_text = _norm(text)
    for variant in _variants(expected):
        # Word boundaries prevent e.g. "f1" matching an unrelated longer token.
        if re.search(rf"(?<![a-z0-9]){re.escape(variant)}(?![a-z0-9])", normalized_text):
            return True
    return False


def _contains_numeric_unit(text: str, expected: str) -> bool:
    """Allow punctuation/spacing variation around numeric facts, not arbitrary numbers."""
    normalized_text = _norm(text)
    for variant in _variants(expected):
        if variant and re.search(rf"(?<![a-z0-9]){re.escape(variant)}(?![a-z0-9])", normalized_text):
            return True
    normalized_expected = _norm(expected)
    nums = re.findall(r"\d+(?:\.\d+)?", normalized_expected)
    if not nums:
        return False
    if not all(re.search(rf"(?<!\d){re.escape(number)}(?!\d)", normalized_text) for number in nums):
        return False
    labels = re.findall(r"[a-z]+|%", normalized_expected)
    labels = [label for label in labels if label not in {"the", "a", "an", "of", "by", "to", "and", "is", "are"}]
    return not labels or any(label in normalized_text for label in labels)


def _contains_fact(text: str, expected: str) -> bool:
    return _contains_phrase(text, expected) or _contains_numeric_unit(text, expected)


def check_answer(answer: str, rule: dict[str, Any]) -> tuple[bool, list[str]]:
    text = _norm(answer)
    mode = rule.get("mode", "contains_all")
    if mode == "exact":
        expected = _norm(rule["value"])
        return text == expected, ([] if text == expected else [f"Expected exact answer: {rule['value']}"])
    if mode == "contains_all":
        missing = [value for value in rule.get("values", []) if not _contains_fact(text, str(value))]
        forbidden = [value for value in rule.get("must_not_contain", []) if _contains_phrase(text, str(value))]
        issues = []
        if missing:
            issues.append("Missing answer facts: " + ", ".join(map(str, missing)))
        if forbidden:
            issues.append("Unexpected answer facts: " + ", ".join(map(str, forbidden)))
        return not issues, issues
    if mode == "contains_any":
        values = rule.get("values", [])
        if any(_contains_fact(text, str(value)) for value in values):
            return True, []
        return False, ["Expected one of: " + ", ".join(map(str, values))]
    raise ValueError(f"Unknown answer_check mode: {mode}")


def _tool_matches(actual: dict, expected: dict) -> bool:
    """Ignore generated search wording, but require correct IDs for record fetches."""
    expected_tool = expected.get("tool")
    if actual.get("tool") != expected_tool:
        return False
    if expected.get("match") == "name_only" or expected_tool in {"search_knowledge", "search_notes"}:
        return True
    return actual.get("args", {}) == expected.get("args", {})


def check_retrieval(expected: list[dict], actual: list[dict]) -> tuple[bool, list[str]]:
    if not expected:
        return True, []
    missing = []
    index = 0
    for wanted in expected:
        found = False
        while index < len(actual):
            current = actual[index]
            index += 1
            if _tool_matches(current, wanted):
                found = True
                break
        if not found:
            missing.append(f"{wanted.get('tool')} {wanted.get('args', {})}")
    return not missing, (["Missing required executed tool calls: " + "; ".join(missing)] if missing else [])


def grade(answer: str, answer_check: dict[str, Any], executed_tool_calls: list[dict] | None = None, expected_tool_calls: list[dict] | None = None) -> dict[str, Any]:
    answer_correct, answer_issues = check_answer(answer, answer_check)
    retrieval_required = bool(expected_tool_calls)
    retrieval_success, retrieval_issues = check_retrieval(expected_tool_calls or [], executed_tool_calls or [])
    return {
        "task_success": answer_correct,
        "answer_correct": answer_correct,
        "retrieval_required": retrieval_required,
        "retrieval_success": retrieval_success,
        "answer_issues": answer_issues,
        "retrieval_issues": retrieval_issues,
        "grading_issues": answer_issues + (retrieval_issues if retrieval_required else []),
    }
