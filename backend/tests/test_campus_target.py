"""Pure target validation tests. No probes or historical boundary checks."""
import pytest

from campus_http import validate_target


@pytest.mark.parametrize('url,run', [
    ('http://example.invalid:18100', 'a' * 12),
    ('http://127.0.0.1:3306', 'a' * 12),
    ('http://127.0.0.1:6379', 'a' * 12),
    ('http://127.0.0.1:18100', ''),
    ('http://127.0.0.1:18100/path', 'a' * 12),
    ('http://user:password@127.0.0.1:18100', 'a' * 12),
])
def test_refuses_unowned_targets_without_connecting(url, run):
    with pytest.raises(ValueError):
        validate_target(url, run)


def test_accepts_explicit_dedicated_loopback():
    validate_target('http://127.0.0.1:18100', 'a' * 12)
