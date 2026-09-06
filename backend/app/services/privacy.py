"""Small, deterministic privacy checks used before external AI calls."""
import re


_PATTERNS = (
    ('身份证号', re.compile(r'(?<!\d)\d{17}[0-9Xx](?!\d)')),
    ('手机号', re.compile(r'(?<!\d)1[3-9]\d{9}(?!\d)')),
    ('电子邮箱', re.compile(
        r'(?<![A-Z0-9._%+-])[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}(?![A-Z0-9._%+-])',
        re.IGNORECASE)),
    ('银行卡号', re.compile(r'(?<!\d)\d{16,19}(?!\d)')),
)


def detect_sensitive_types(text):
    value = str(text or '')
    return [name for name, pattern in _PATTERNS if pattern.search(value)]


def redact_sensitive_text(text):
    value = str(text or '')
    found = []
    for name, pattern in _PATTERNS:
        value, count = pattern.subn(f'[{name}已脱敏]', value)
        if count:
            found.append(name)
    return value, found
