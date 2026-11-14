"""Argon2id password hashing and constant-cost unknown-account verification."""

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from argon2.low_level import Type

PASSWORD_HASHER = PasswordHasher(
    time_cost=2,
    memory_cost=19_456,
    parallelism=1,
    hash_len=32,
    salt_len=16,
    type=Type.ID,
)
_DUMMY_PASSWORD_HASH = PASSWORD_HASHER.hash("not-a-real-account-password")


def hash_password(password: str) -> str:
    """Return an Argon2id PHC string with a fresh random salt."""
    return PASSWORD_HASHER.hash(password)


def password_matches(stored_hash: str, password: str) -> bool:
    """Verify a password without leaking malformed hashes through exceptions."""
    try:
        return PASSWORD_HASHER.verify(stored_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def verify_unknown_account(password: str) -> None:
    """Perform equivalent Argon2 work for unknown-email login attempts."""
    password_matches(_DUMMY_PASSWORD_HASH, password)


def hash_needs_upgrade(stored_hash: str) -> bool:
    """Check whether a valid legacy hash should be re-encoded with current parameters."""
    try:
        return PASSWORD_HASHER.check_needs_rehash(stored_hash)
    except (VerificationError, InvalidHashError):
        return False
