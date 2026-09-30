from argon2 import PasswordHasher, Type

from app.services.password_service import PasswordService


def test_hash_password_returns_a_verifiable_argon2id_hash():
    service = PasswordService()
    password = "test-password-for-hashing"

    password_hash = service.hash_password(password)

    assert password_hash != password
    assert password_hash.startswith("$argon2id$")
    assert service.verify_password(password, password_hash) is True


def test_hash_password_uses_a_unique_salt_for_each_hash():
    service = PasswordService()
    password = "same-test-password"

    first_hash = service.hash_password(password)
    second_hash = service.hash_password(password)

    assert first_hash != second_hash
    assert service.verify_password(password, first_hash) is True
    assert service.verify_password(password, second_hash) is True


def test_verify_password_accepts_the_correct_password():
    service = PasswordService()
    password_hash = service.hash_password("correct-test-password")

    assert service.verify_password("correct-test-password", password_hash) is True


def test_verify_password_rejects_an_incorrect_password():
    service = PasswordService()
    password_hash = service.hash_password("correct-test-password")

    assert service.verify_password("incorrect-test-password", password_hash) is False


def test_verify_password_rejects_an_invalid_hash():
    service = PasswordService()

    assert service.verify_password("test-password", "not-an-argon2-hash") is False


def test_current_hash_does_not_need_rehashing():
    service = PasswordService()
    password_hash = service.hash_password("current-configuration-password")

    assert service.needs_rehash(password_hash) is False


def test_hash_with_different_parameters_needs_rehashing():
    service = PasswordService()
    legacy_hasher = PasswordHasher(
        time_cost=1,
        memory_cost=8 * 1024,
        parallelism=1,
        hash_len=16,
        salt_len=16,
        type=Type.ID,
    )

    legacy_hash = legacy_hasher.hash("rehash-test-password")

    assert service.needs_rehash(legacy_hash) is True
