"""Validation rules for passwords selected by users."""

from dataclasses import dataclass
from unicodedata import category


MINIMUM_PASSWORD_LENGTH = 12


@dataclass(frozen=True)
class PasswordValidationResult:
    """Describe whether a password meets the policy and why it does not."""

    is_valid: bool
    is_too_short: bool
    has_too_few_categories: bool
    category_count: int


def validate_password(password: str) -> PasswordValidationResult:
    """Validate a user-selected password without transforming or storing it.

    Lowercase and uppercase letters use Python's Unicode-aware string methods.
    Numbers are Unicode decimal digits. Special characters are Unicode punctuation
    or symbols; whitespace and control characters are permitted but do not add a
    category.
    """

    has_lowercase = any(character.islower() for character in password)
    has_uppercase = any(character.isupper() for character in password)
    has_number = any(character.isdecimal() for character in password)
    has_special_character = any(category(character)[0] in {"P", "S"} for character in password)

    category_count = sum(
        (has_lowercase, has_uppercase, has_number, has_special_character)
    )
    is_too_short = len(password) < MINIMUM_PASSWORD_LENGTH
    has_too_few_categories = category_count < 3

    return PasswordValidationResult(
        is_valid=not is_too_short and not has_too_few_categories,
        is_too_short=is_too_short,
        has_too_few_categories=has_too_few_categories,
        category_count=category_count,
    )
