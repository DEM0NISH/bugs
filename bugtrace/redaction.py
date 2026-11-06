import re


PATTERNS = (
    (re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b"), "[REDACTED_EMAIL]"),
    (re.compile(r"(?<!\w)(?:\+?\d{1,3}[ .-]?)?(?:\d{3,5}[ .-]){1,2}\d{4,5}(?!\w)"), "[REDACTED_PHONE]"),
    (re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/-]+=*"), "Bearer [REDACTED]"),
    (re.compile(r"(?i)\b(?:sk|pk|api)[-_][A-Za-z0-9_-]{12,}\b"), "[REDACTED_KEY]"),
    (re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b"), "[REDACTED_PAN]"),
    (re.compile(r"(?i)\b[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]\b"), "[REDACTED_GSTIN]"),
)
SENSITIVE_KEYS = {"password", "token", "secret", "authorization"}


def redact_text(value: str) -> str:
    result = value
    for pattern, replacement in PATTERNS:
        result = pattern.sub(replacement, result)
    return result


def redact(value):
    if isinstance(value, dict):
        return {key: "[REDACTED]" if str(key).lower() in SENSITIVE_KEYS else redact(item) for key, item in value.items()}
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, str):
        return redact_text(value)
    return value
