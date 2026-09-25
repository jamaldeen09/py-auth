
from py_auth._utils import generate_token, hash_token


def test_generate_token_returns_string():
    """Should return a string — sanity check before anything else."""
    token = generate_token()
    assert isinstance(token, str)

def test_generate_token_default_is_not_empty():
    """An empty token would be catastrophic for session security."""
    token = generate_token()
    assert len(token) > 0

def test_generate_token_custom_length():
    """
    num_bytes controls entropy — a caller asking for more bytes should get a longer token.
    secrets.token_urlsafe returns ceil(num_bytes * 4/3) chars due to base64 encoding,
    so we just assert that a larger num_bytes gives a longer string.
    """
    short = generate_token(num_bytes=16)
    long = generate_token(num_bytes=64)
    assert len(long) > len(short)

def test_generate_token_is_unique():
    """
    Two consecutive calls must never return the same token.
    If they did, session tokens could collide and an attacker could guess valid sessions.
    """
    token_a = generate_token()
    token_b = generate_token()
    assert token_a != token_b


def test_hash_token_returns_string():
    """SHA-256 hex digest should always be a string."""
    result = hash_token("some_token")
    assert isinstance(result, str)

def test_hash_token_is_deterministic():
    """
    The same token must always produce the same hash.
    This matters because I store the hash in the DB and re-hash the cookie value
    to look up the session — if the hash changes, sessions would be invalid.
    """
    token = "my_session_token"
    assert hash_token(token) == hash_token(token)

def test_hash_token_different_inputs_give_different_hashes():
    """Two different tokens must not produce the same hash (collision resistance)."""
    assert hash_token("token_a") != hash_token("token_b")

def test_hash_token_output_is_64_chars():
    """SHA-256 hex digest is always exactly 64 characters — good to assert this explicitly."""
    result = hash_token("anything")
    assert len(result) == 64
