"""Cryptographically secure generation of temporary initial passwords."""

import secrets


TEMPORARY_PASSWORD_LENGTH = 12
LOWERCASE_ALPHABET = "abcdefghijkmnopqrstuvwxyz"
UPPERCASE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ"
NUMBER_ALPHABET = "23456789"
SPECIAL_CHARACTER_ALPHABET = "!?@#$%&*+-_/="
GENERATOR_ALPHABET = (
    LOWERCASE_ALPHABET
    + UPPERCASE_ALPHABET
    + NUMBER_ALPHABET
    + SPECIAL_CHARACTER_ALPHABET
)


def generate_temporary_password() -> str:
    """Return a 12-character password containing every required category."""

    characters = [
        secrets.choice(LOWERCASE_ALPHABET),
        secrets.choice(UPPERCASE_ALPHABET),
        secrets.choice(NUMBER_ALPHABET),
        secrets.choice(SPECIAL_CHARACTER_ALPHABET),
    ]
    characters.extend(
        secrets.choice(GENERATOR_ALPHABET)
        for _ in range(TEMPORARY_PASSWORD_LENGTH - len(characters))
    )
    _secure_shuffle(characters)
    return "".join(characters)


def _secure_shuffle(characters: list[str]) -> None:
    """Shuffle in place using a Fisher-Yates algorithm backed by ``secrets``."""

    for index in range(len(characters) - 1, 0, -1):
        replacement_index = secrets.randbelow(index + 1)
        characters[index], characters[replacement_index] = (
            characters[replacement_index],
            characters[index],
        )
