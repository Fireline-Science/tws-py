import pytest
from tws.utils import is_valid_jwt


@pytest.mark.parametrize(
    "value,expected",
    [
        # Valid JWT (base64url encoded parts)
        [
            "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U",
            True,
        ],
        # Whitespace should be trimmed
        [
            " eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U ",
            True,
        ],
        # Invalid JWTs
        [None, False],
        ["", False],
        ["too.many.dots.here", False],
        ["not.enough", False],
        ["invalid@chars.in.jwt", False],
        ["header.payload.signature", False],  # not b64 parts
        [123, False],  # Non-string input
        ["   ", False],  # Just whitespace
    ],
)
def test_is_valid_jwt(value, expected):
    """Test JWT validation for various input cases"""
    assert is_valid_jwt(value) == expected
