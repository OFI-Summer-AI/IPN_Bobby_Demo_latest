"""Shared deterministic text normalization for classification and retrieval."""
from __future__ import annotations

import re

_WORD_CORRECTIONS = {
    "wfi": "wifi",
    "wi fi": "wifi",
    "conect": "connect",
    "conected": "connected",
    "conecting": "connecting",
    "connct": "connect",
    "lapotp": "laptop",
    "laptp": "laptop",
    "pasword": "password",
    "passwrd": "password",
    "outlok": "outlook",
    "prnter": "printer",
    "acount": "account",
    "loggin": "login",
    "cant": "can't",
    "wont": "won't",
}
_CORRECTION_PATTERNS = tuple(
    (re.compile(rf"\b{re.escape(incorrect)}\b"), corrected)
    for incorrect, corrected in _WORD_CORRECTIONS.items()
)

EMAIL_RE = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
PHONE_RE = re.compile(r"[\+]?\d[\d\s\-\(\)]{5,}\d")
_NON_NAME_WORDS = {
    "please", "plan", "find", "book", "tell", "show", "give", "help", "want",
    "need", "my", "the", "a", "an", "me", "you", "your", "weekend", "holiday",
    "weather", "recipe", "movie", "hotel", "flight", "advice", "activities",
}


def extract_message_text(content: object) -> str:
    """Extract a plain string from a LangChain BaseMessage content value or raw message."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and "text" in item:
                parts.append(str(item["text"]))
            else:
                parts.append(str(item))
        return " ".join(parts)
    return "" if content is None else str(content)


def normalize_query(value: str) -> str:
    """Normalize casing, spacing, apostrophes, and common IT-support typos."""
    text = value.strip().lower().replace("’", "'").replace("`", "'")
    text = re.sub(r"\s+", " ", text)
    for pattern, corrected in _CORRECTION_PATTERNS:
        text = pattern.sub(corrected, text)
    return text


def extract_email(value: str) -> str | None:
    match = EMAIL_RE.search(value.strip())
    return match.group(0).lower() if match else None


def extract_phone(value: str) -> str | None:
    match = PHONE_RE.search(value.strip())
    if not match:
        return None
    phone = match.group(0).strip()
    digits = re.sub(r"\D", "", phone)
    return phone if 7 <= len(digits) <= 15 else None


def is_valid_contact_name(value: str) -> bool:
    words = value.replace("-", " ").replace("'", " ").split()
    return (
        1 <= len(words) <= 5
        and all(word.isalpha() for word in words)
        and not any(word.lower() in _NON_NAME_WORDS for word in words)
    )
