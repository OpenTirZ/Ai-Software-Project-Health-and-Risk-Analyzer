"""
Email normalization utilities.
"""


def normalize_email(email: str | None) -> str:
    """
    Normalize an email address for consistent storage and lookup:
    - Strips leading and trailing whitespace
    - Converts all characters to lowercase
    - Returns empty string for None or empty inputs
    """
    if not email:
        return ""
    return email.strip().lower()
