from app.services.password_policy import validate_password


def test_password_with_eleven_characters_is_too_short():
    """The minimum length applies even when all four categories are present."""

    result = validate_password("Abcdefghi1!")

    assert result.is_valid is False
    assert result.is_too_short is True
    assert result.has_too_few_categories is False


def test_password_with_twelve_characters_and_three_categories_is_valid():
    """Twelve characters and lowercase, uppercase, and numbers meet the policy."""

    result = validate_password("Abcdefghij12")

    assert result.is_valid is True
    assert result.category_count == 3


def test_password_longer_than_twelve_characters_is_valid_when_categories_match():
    """The policy intentionally has no maximum length."""

    result = validate_password("LongEnough12!")

    assert result.is_valid is True
    assert result.category_count == 4


def test_lowercase_uppercase_and_numbers_are_a_valid_combination():
    assert validate_password("Abcdefghij12").is_valid is True


def test_lowercase_uppercase_and_special_characters_are_a_valid_combination():
    assert validate_password("Abcdefghij!!").is_valid is True


def test_lowercase_numbers_and_special_characters_are_a_valid_combination():
    assert validate_password("abcdefghi1!!").is_valid is True


def test_uppercase_numbers_and_special_characters_are_a_valid_combination():
    assert validate_password("ABCDEFGHI1!!").is_valid is True


def test_all_four_categories_are_valid():
    assert validate_password("Abcdefghi1!Z").is_valid is True


def test_only_lowercase_characters_are_invalid():
    result = validate_password("abcdefghijkl")

    assert result.is_valid is False
    assert result.has_too_few_categories is True


def test_lowercase_and_uppercase_characters_are_invalid():
    result = validate_password("Abcdefghijkl")

    assert result.is_valid is False
    assert result.category_count == 2


def test_lowercase_and_numbers_are_invalid():
    result = validate_password("abcdefghij12")

    assert result.is_valid is False
    assert result.has_too_few_categories is True


def test_empty_password_is_invalid_for_both_rules():
    result = validate_password("")

    assert result.is_valid is False
    assert result.is_too_short is True
    assert result.has_too_few_categories is True


def test_unicode_letters_decimal_digits_and_symbols_are_recognized():
    """Unicode semantics are intentional rather than limited to ASCII classes."""

    result = validate_password("Äbcdefghij١!")

    assert result.is_valid is True
    assert result.category_count == 4
