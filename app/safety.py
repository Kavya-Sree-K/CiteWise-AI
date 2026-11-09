import re

EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
NUMBER = re.compile(r"\+?\d[\d\s().-]{7,}\d")

INJECTION_PATTERNS = [
    r"ignore (all |any |the )?(previous|prior|above|earlier) (instructions|rules|prompts)",
    r"disregard (all |any |the )?(previous |prior |above |earlier )?(instructions|rules)",
    r"forget (all |your |the )?(previous |prior )?(instructions|rules)",
    r"reveal (all |the )?(restricted|confidential|hidden|secret)",
]
INJECTION = [re.compile(p, re.IGNORECASE) for p in INJECTION_PATTERNS]


def _mask_number(m):
    # long digit strings (phone, ID numbers) are hidden, short ones and dates stay
    digits = sum(ch.isdigit() for ch in m.group(0))
    return "[NUMBER]" if digits >= 9 else m.group(0)


def redact(text):
    text = EMAIL.sub("[EMAIL]", text)
    return NUMBER.sub(_mask_number, text)


def looks_like_injection(text):
    """Return the suspicious phrase if found, otherwise an empty string."""
    for pattern in INJECTION:
        m = pattern.search(text)
        if m:
            return m.group(0)
    return ""


def citations_ok(answer, n_sources):
    """True if every [n] in the answer points to a real source."""
    numbers = [int(x) for x in re.findall(r"\[(\d+)\]", answer)]
    return all(1 <= n <= n_sources for n in numbers)