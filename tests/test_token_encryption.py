"""
Property-based test for Strava token encryption round-trip.

**Property 7: Token Encryption Round-Trip**
**Validates: Requirements 20.3, 30.1**

For all Strava tokens T, decrypt(encrypt(T)) SHALL equal T.
"""
import pytest
import os
from hypothesis import given, strategies as st, settings
from cryptography.fernet import Fernet
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.services.strava_client import StravaClient
from app.models.base import Base


# Strategy for generating valid token strings
# Strava tokens are typically alphanumeric strings of varying lengths
token_strategy = st.text(
    alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'), whitelist_characters='_-'),
    min_size=20,
    max_size=200
)


def create_test_client():
    """Create a test StravaClient with in-memory database."""
    # Set up test encryption key in environment
    test_key = Fernet.generate_key().decode()
    os.environ['STRAVA_ENCRYPTION_KEY'] = test_key
    os.environ['STRAVA_CLIENT_ID'] = 'test_client_id'
    os.environ['STRAVA_CLIENT_SECRET'] = 'test_client_secret'
    
    # Create in-memory database
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    TestSessionLocal = sessionmaker(bind=engine)
    db = TestSessionLocal()
    
    return StravaClient(db)


@given(token=token_strategy)
@settings(max_examples=100)
def test_token_encryption_round_trip(token):
    """
    Property 7: Token Encryption Round-Trip
    
    For all Strava tokens T, decrypt(encrypt(T)) SHALL equal T.
    
    This property ensures that:
    1. Encryption is reversible
    2. No data is lost during encryption/decryption
    3. The original token can always be recovered
    
    Requirements: 20.3, 30.1
    """
    client = create_test_client()
    
    # Encrypt the token
    encrypted = client._encrypt_token(token)
    
    # Verify encrypted is bytes
    assert isinstance(encrypted, bytes), "Encrypted token must be bytes"
    
    # Decrypt the token
    decrypted = client._decrypt_token(encrypted)
    
    # Verify decrypted is string
    assert isinstance(decrypted, str), "Decrypted token must be string"
    
    # Property: decrypt(encrypt(T)) == T
    assert decrypted == token, f"Round-trip failed: expected '{token}', got '{decrypted}'"


@given(token=token_strategy)
@settings(max_examples=50)
def test_encryption_produces_different_output(token):
    """
    Additional property: Encryption should produce output different from input.
    
    This ensures that tokens are actually being encrypted and not just stored as-is.
    """
    client = create_test_client()
    encrypted = client._encrypt_token(token)
    
    # Encrypted bytes should not equal the original token bytes
    assert encrypted != token.encode(), "Encrypted token should differ from original"


@given(token=token_strategy)
@settings(max_examples=50)
def test_encryption_is_deterministic(token):
    """
    Additional property: Multiple encryptions of the same token should be decryptable.
    
    Note: Fernet includes a timestamp, so encryptions won't be identical,
    but all should decrypt to the same value.
    """
    client = create_test_client()
    
    encrypted1 = client._encrypt_token(token)
    encrypted2 = client._encrypt_token(token)
    
    # Both should decrypt to the original token
    assert client._decrypt_token(encrypted1) == token
    assert client._decrypt_token(encrypted2) == token


def test_empty_token_encryption():
    """Edge case: Test encryption of empty string."""
    client = create_test_client()
    token = ""
    encrypted = client._encrypt_token(token)
    decrypted = client._decrypt_token(encrypted)
    assert decrypted == token


def test_special_characters_encryption():
    """Edge case: Test encryption with special characters that might appear in tokens."""
    client = create_test_client()
    tokens = [
        "abc123_def456-ghi789",
        "TOKEN_WITH_UNDERSCORES",
        "token-with-dashes",
        "MixedCaseToken123",
    ]
    
    for token in tokens:
        encrypted = client._encrypt_token(token)
        decrypted = client._decrypt_token(encrypted)
        assert decrypted == token, f"Failed for token: {token}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
