from app.services.password_policy import validate_password
from app.services.temporary_password_generator import (
    GENERATOR_ALPHABET,
    LOWERCASE_ALPHABET,
    NUMBER_ALPHABET,
    SPECIAL_CHARACTER_ALPHABET,
    TEMPORARY_PASSWORD_LENGTH,
    UPPERCASE_ALPHABET,
    generate_temporary_password,
)


def test_generated_passwords_always_have_the_configured_length():
    """Every generated temporary password is exactly twelve characters long."""

    passwords = [generate_temporary_password() for _ in range(100)]

    assert all(len(password) == TEMPORARY_PASSWORD_LENGTH for password in passwords)


def test_generated_passwords_always_contain_all_four_categories():
    """The generator constructs every category before securely mixing positions."""

    passwords = [generate_temporary_password() for _ in range(100)]

    for password in passwords:
        assert any(character in LOWERCASE_ALPHABET for character in password)
        assert any(character in UPPERCASE_ALPHABET for character in password)
        assert any(character in NUMBER_ALPHABET for character in password)
        assert any(character in SPECIAL_CHARACTER_ALPHABET for character in password)


def test_generated_passwords_exclude_ambiguous_characters():
    """The generator, unlike the user policy, excludes hard-to-read characters."""

    passwords = [generate_temporary_password() for _ in range(100)]

    assert all(not set(password).intersection("0O1lI") for password in passwords)


def test_generated_passwords_only_use_the_defined_generator_alphabet():
    passwords = [generate_temporary_password() for _ in range(100)]

    assert all(set(password).issubset(set(GENERATOR_ALPHABET)) for password in passwords)


def test_generator_produces_varying_values_without_requiring_global_uniqueness():
    """A sample must not be constant; distinct values are not treated as an invariant."""

    passwords = [generate_temporary_password() for _ in range(20)]

    assert any(password != passwords[0] for password in passwords[1:])


def test_generated_passwords_also_meet_the_general_password_policy():
    passwords = [generate_temporary_password() for _ in range(100)]

    assert all(validate_password(password).is_valid for password in passwords)
