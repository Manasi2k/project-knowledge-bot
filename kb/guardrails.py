"""Simple guardrails. Real protection is the permission checks; these add cheap extra safety."""
import re
import time

MAX_QUESTION_CHARS = 500
INJECTION_PHRASES = (
    "ignore previous instructions", "ignore all previous", "ignore your instructions",
    "disregard your instructions", "reveal your system prompt", "show your system prompt",
    "print your instructions", "developer mode", "jailbreak",
)
CARD_RE = re.compile(r"\b\d(?:[ -]?\d){12,18}\b")
SECRET_RES = [
    re.compile(r"\bgsk_[A-Za-z0-9]{20,}\b"),                                   # Groq API keys
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),                                       # AWS access key ids
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?(?:-----END [A-Z ]*PRIVATE KEY-----|$)"),
]


def check_question(question: str) -> str | None:
    """A message to show the user if the question must not be processed, else None."""
    q = question.strip()
    if not q:
        return "Please type a question."
    if len(q) > MAX_QUESTION_CHARS:
        return f"Please keep questions under {MAX_QUESTION_CHARS} characters."
    lowered = q.lower()
    if any(p in lowered for p in INJECTION_PHRASES):
        return "I can only answer questions about your project documents."
    return None


def rate_limited(timestamps: list[float], limit: int = 20, window: float = 600.0,
                 now: float | None = None) -> bool:
    """True if this user already asked `limit` questions in the last `window` seconds."""
    now = time.time() if now is None else now
    timestamps[:] = [t for t in timestamps if now - t < window]
    if len(timestamps) >= limit:
        return True
    timestamps.append(now)
    return False


def _luhn_ok(digits: str) -> bool:
    total, flip = 0, False
    for ch in reversed(digits):
        d = int(ch)
        if flip:
            d = d * 2 - 9 if d * 2 > 9 else d * 2
        total += d
        flip = not flip
    return total % 10 == 0


def redact(text: str) -> str:
    """Remove card numbers (Luhn-valid only, to avoid false alarms) and obvious secrets from text."""
    def card(m: re.Match) -> str:
        digits = re.sub(r"\D", "", m.group())
        return "[card number removed]" if 13 <= len(digits) <= 19 and _luhn_ok(digits) else m.group()
    text = CARD_RE.sub(card, text)
    for rx in SECRET_RES:
        text = rx.sub("[secret removed]", text)
    return text