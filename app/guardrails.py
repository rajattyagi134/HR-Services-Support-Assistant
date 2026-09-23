"""Input/output guardrails: PII redaction, prompt-injection & off-topic blocking,
length limits, and groundedness checks. Kept dependency-free (regex based) so the
project stays small and easy to follow.
"""
import re
from dataclasses import dataclass

from app.config import settings

_PII_PATTERNS = {
    "ssn": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "credit_card": re.compile(r"\b(?:\d[ -]*?){13,16}\b"),
    "email": re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b"),
    "phone": re.compile(r"\b\+?\d{1,2}[\s.-]?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}\b"),
}

_INJECTION_PATTERNS = [
    re.compile(r"ignore (all|any|previous) instructions", re.I),
    re.compile(r"disregard (the|your) (system|prior) prompt", re.I),
    re.compile(r"you are now (in )?(dan|developer) mode", re.I),
    re.compile(r"reveal (your|the) (system prompt|instructions)", re.I),
]

# Very small allow-list of HR-relevant keywords used as a cheap topic gate before
# the router agent makes the final call.
_HR_KEYWORDS = [
    "leave", "pto", "vacation", "payroll", "salary", "benefit", "insurance",
    "policy", "onboarding", "offboarding", "resignation", "notice period",
    "holiday", "attendance", "wfh", "work from home", "hr", "harassment",
    "reimbursement", "expense", "promotion", "appraisal", "background check",
]


@dataclass
class GuardrailResult:
    allowed: bool
    reason: str = ""


def check_length(text: str) -> GuardrailResult:
    if len(text) > settings.max_input_chars:
        return GuardrailResult(False, f"Message too long (max {settings.max_input_chars} chars).")
    return GuardrailResult(True)


def check_prompt_injection(text: str) -> GuardrailResult:
    for pattern in _INJECTION_PATTERNS:
        if pattern.search(text):
            return GuardrailResult(False, "Message looks like a prompt-injection attempt.")
    return GuardrailResult(True)


def looks_hr_related(text: str) -> bool:
    lowered = text.lower()
    return any(keyword in lowered for keyword in _HR_KEYWORDS)


def redact_pii(text: str) -> str:
    redacted = text
    for label, pattern in _PII_PATTERNS.items():
        redacted = pattern.sub(f"[REDACTED_{label.upper()}]", redacted)
    return redacted


def run_input_guardrails(text: str) -> GuardrailResult:
    for check in (check_length, check_prompt_injection):
        result = check(text)
        if not result.allowed:
            return result
    return GuardrailResult(True)


def check_groundedness(answer: str, retrieved_any: bool) -> bool:
    """Reject answers that claim knowledge with no supporting retrieved context."""
    if retrieved_any:
        return True
    refusal_markers = ("i don't know", "not sure", "no information", "can't find")
    return any(marker in answer.lower() for marker in refusal_markers)
