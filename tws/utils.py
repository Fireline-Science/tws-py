import re

BASE64URL_REGEX = r"^([a-z0-9_-]{4})*($|[a-z0-9_-]{3}$|[a-z0-9_-]{2}$)$"


def is_valid_jwt(value: str) -> bool:
    """Checks if value seems to be a JWT without attempting to decode it."""
    if not isinstance(value, str):
        return False

    value = value.strip()

    # Valid JWT must have exactly 2 periods (Header.Payload.Signature)
    if value.count(".") != 2:
        return False

    # Each of the parts must be base64 encoded
    for part in value.split("."):
        if not part or not re.search(BASE64URL_REGEX, part, re.IGNORECASE):
            return False

    return True
