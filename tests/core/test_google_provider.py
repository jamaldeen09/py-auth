import httpx2, pytest

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from py_auth.providers import GoogleProvider
from py_auth._utils import generate_code_verifier, generate_nonce
from joserfc.errors import JoseError

def test_generate_code_verifier():
    """Test that generate_code_verifier creates a unique, non-empty cryptographically secure string.

    Verifies that the PKCE code verifier is properly generated as a string, is not empty,
    and that consecutive calls produce different values to ensure randomness.
    """
    verifier = generate_code_verifier()

    assert isinstance(verifier, str)
    assert verifier
    assert verifier != generate_code_verifier()

def test_generate_nonce():
    """Test that generate_nonce creates a unique, non-empty cryptographically secure string.

    Verifies that the OIDC nonce is properly generated as a string, is not empty,
    and that consecutive calls produce different values to ensure randomness for replay attack prevention.
    """
    nonce = generate_nonce()

    assert isinstance(nonce, str)
    assert nonce
    assert nonce != generate_nonce()

def test_get_client(google_provider):
    """Test that GoogleProvider.get_client creates an AsyncOAuth2Client with correct OAuth 2.0 configuration.

    Verifies that the client is initialized with the provider's client_id, client_secret, redirect_uri,
    the required Google OAuth scope (openid email profile), and PKCE code challenge method (S256).
    """
    with patch(
        "py_auth.providers.google.AsyncOAuth2Client"
    ) as mock_client:
        google_provider.get_client()

    mock_client.assert_called_once_with(
        client_id="test-client-id",
        client_secret="test-client-secret",
        redirect_uri="https://example.com/callback",
        scope="openid email profile",
        code_challenge_method="S256",
    )


def test_create_auth_url(google_provider):
    """Test that GoogleProvider.create_auth_url generates a valid Google OAuth authorization URL.

    Verifies that the method uses the mocked OAuth client to create an authorization URL
    with the correct Google OAuth endpoint and includes the PKCE code verifier and nonce parameters.
    """
    client = MagicMock()
    client.create_authorization_url.return_value = (
        "https://accounts.google.com/auth",
        {"state": "state123"},
    )

    result = google_provider.create_auth_url(
        code_verifier="verifier123",
        nonce="nonce123",
        client=client,
    )

    assert result[0] == "https://accounts.google.com/auth"

    client.create_authorization_url.assert_called_once_with(
        "https://accounts.google.com/o/oauth2/v2/auth",
        access_type="offline",
        prompt=None,
        nonce="nonce123",
        code_verifier="verifier123",
    )


def test_create_auth_url_respects_prompt_and_access_type():
    """Test that create_auth_url respects custom access_type and prompt parameters.

    Verifies that when a GoogleProvider is configured with custom access_type and prompt values,
    these parameters are correctly passed to the OAuth client's authorization URL creation.
    """
    provider = GoogleProvider(
        client_id="client",
        client_secret="secret",
        redirect_uri="https://example.com/callback",
        access_type="online",
        prompt="consent",
    )

    client = MagicMock()
    provider.create_auth_url("verifier", "nonce", client)

    client.create_authorization_url.assert_called_once_with(
        "https://accounts.google.com/o/oauth2/v2/auth",
        access_type="online",
        prompt="consent",
        nonce="nonce",
        code_verifier="verifier",
    )

@pytest.mark.asyncio
async def test_handle_callback_success(google_provider):
    """Test that GoogleProvider.handle_callback successfully exchanges authorization code for tokens.

    Verifies that when the OAuth callback receives a valid authorization code, the provider
    correctly exchanges it for access and refresh tokens, and returns the token data including
    the ID token for subsequent user authentication.
    """
    token_response = {
        "access_token": "access123",
        "refresh_token": "refresh123",
        "expires_at": 1893456000,
        "token_type": "Bearer",
        "scope": "openid email profile",
        "id_token": "idtoken123",
        "session_state": "session123",
    }

    client = AsyncMock()
    client.fetch_token.return_value = token_response

    with patch.object(google_provider, "get_client", return_value=client):
        result = await google_provider.handle_callback(
            request_url="https://example.com/callback?code=abc",
            state="state123",
            code_verifier="verifier123",
        )

    assert result["error"] is None
    assert result["data"]["id_token"] == "idtoken123"
    assert result["data"]["access_token"] == "access123"
    assert result["data"]["type"] == "oidc"

    client.fetch_token.assert_awaited_once_with(
        "https://oauth2.googleapis.com/token",
        authorization_response="https://example.com/callback?code=abc",
        code_verifier="verifier123",
    )


@pytest.mark.asyncio
async def test_handle_callback_unexpected_error(google_provider):
    """Test that GoogleProvider.handle_callback handles unexpected errors gracefully.

    Verifies that when the token exchange fails due to an unexpected error (like a RuntimeError),
    the provider returns an InternalServerError instead of crashing, ensuring robust error handling.
    """
    client = AsyncMock()
    client.fetch_token.side_effect = RuntimeError("unexpected failure")

    with patch.object(google_provider, "get_client", return_value=client):
        result = await google_provider.handle_callback(
            request_url="https://example.com/callback",
            state="state123",
            code_verifier="verifier123",
        )

    assert result["error"]["code"] == "InternalServerError"
    assert result["error"]["status_code"] == 500

@pytest.mark.asyncio
async def test_fetch_google_public_keys_success():
    """Test that GoogleProvider.fetch_google_public_keys successfully retrieves Google's public keys.

    Verifies that the static method can fetch and parse Google's JWKS (JSON Web Key Set) endpoint,
    returning the public keys needed to verify ID token signatures.
    """
    response = MagicMock()
    response.raise_for_status.return_value = None
    response.json.return_value = {
        "keys": [{"kid": "key123", "kty": "RSA"}]
    }

    client = AsyncMock()
    client.get.return_value = response

    with patch(
        "py_auth.providers.google.httpx2.AsyncClient"
    ) as mock_client_class:
        mock_client_class.return_value.__aenter__.return_value = client

        result = await GoogleProvider.fetch_google_public_keys()

    assert result["error"] is None
    assert result["data"]["keys"] == [
        {"kid": "key123", "kty": "RSA"}
    ]

    client.get.assert_awaited_once_with(
        "https://www.googleapis.com/oauth2/v3/certs"
    )


@pytest.mark.asyncio
async def test_fetch_google_public_keys_rate_limited():
    """Test that GoogleProvider.fetch_google_public_keys handles rate limiting from Google's service.

    Verifies that when Google returns a 429 Too Many Requests status, the provider
    returns a GoogleJWKSRateLimited error with appropriate 503 status code.
    """
    response = MagicMock()
    response.status_code = 429

    client = AsyncMock()
    client.get.return_value = response
    response.raise_for_status.side_effect = httpx2.HTTPStatusError(
        "rate limited",
        request=httpx2.Request("GET", "https://example.com"),
        response=httpx2.Response(429),
    )

    with patch(
        "py_auth.providers.google.httpx2.AsyncClient"
    ) as mock_client_class:
        mock_client_class.return_value.__aenter__.return_value = client

        result = await GoogleProvider.fetch_google_public_keys()

    assert result["error"]["code"] == "GoogleJWKSRateLimited"
    assert result["error"]["status_code"] == 503


@pytest.mark.asyncio
async def test_fetch_google_public_keys_server_error():
    """Test that GoogleProvider.fetch_google_public_keys handles server errors from Google's service.

    Verifies that when Google returns a 5xx server error, the provider
    returns a GoogleJWKSUnavailable error with appropriate 503 status code.
    """
    response = MagicMock()
    response.raise_for_status.side_effect = httpx2.HTTPStatusError(
        "server error",
        request=httpx2.Request("GET", "https://example.com"),
        response=httpx2.Response(500),
    )

    client = AsyncMock()
    client.get.return_value = response

    with patch(
        "py_auth.providers.google.httpx2.AsyncClient"
    ) as mock_client_class:
        mock_client_class.return_value.__aenter__.return_value = client

        result = await GoogleProvider.fetch_google_public_keys()

    assert result["error"]["code"] == "GoogleJWKSUnavailable"
    assert result["error"]["status_code"] == 503


@pytest.mark.asyncio
async def test_fetch_google_public_keys_invalid_json():
    """Test that GoogleProvider.fetch_google_public_keys handles invalid JSON responses.

    Verifies that when Google returns a response that cannot be parsed as JSON,
    the provider returns an InvalidGoogleJWKS error with appropriate 502 status code.
    """
    response = MagicMock()
    response.raise_for_status.return_value = None
    response.json.side_effect = ValueError("invalid JSON")

    client = AsyncMock()
    client.get.return_value = response

    with patch(
        "py_auth.providers.google.httpx2.AsyncClient"
    ) as mock_client_class:
        mock_client_class.return_value.__aenter__.return_value = client

        result = await GoogleProvider.fetch_google_public_keys()

    assert result["error"]["code"] == "InvalidGoogleJWKS"
    assert result["error"]["status_code"] == 502


@pytest.mark.asyncio
async def test_fetch_google_public_keys_invalid_structure():
    """Test that GoogleProvider.fetch_google_public_keys handles invalid JWKS structure.

    Verifies that when Google returns a valid JSON response but missing the required "keys" array,
    the provider returns an InvalidGoogleJWKS error with appropriate 502 status code.
    """
    response = MagicMock()
    response.raise_for_status.return_value = None
    response.json.return_value = {"not_keys": []}

    client = AsyncMock()
    client.get.return_value = response

    with patch(
        "py_auth.providers.google.httpx2.AsyncClient"
    ) as mock_client_class:
        mock_client_class.return_value.__aenter__.return_value = client

        result = await GoogleProvider.fetch_google_public_keys()

    assert result["error"]["code"] == "InvalidGoogleJWKS"
    assert result["error"]["status_code"] == 502

def test_validate_id_token_success(google_provider):
    """Test that GoogleProvider.validate_id_token successfully validates a properly formatted ID token.

    Verifies that when a valid ID token with correct claims (sub, email, iss, aud, exp, iat, nonce)
    is provided, the provider successfully decodes and validates it, returning the token claims.
    """
    claims = {
        "sub": "google_user_123",
        "email": "test@example.com",
        "iss": google_provider.google_issuer,
        "aud": google_provider.client_id,
        "exp": 1893456000,
        "iat": 1893450000,
        "nonce": "nonce123",
    }

    fake_token = SimpleNamespace(claims=claims)

    with (
        patch("py_auth.providers.google.KeySet.import_key_set"),
        patch("py_auth.providers.google.decode", return_value=fake_token),
        patch("py_auth.providers.google.JWTClaimsRegistry") as registry,
    ):
        registry.return_value.validate.return_value = None

        result = google_provider.validate_id_token(
            "fake.id.token",
            jwks={"keys": [{"kid": "key123"}]},
            nonce="nonce123",
        )

    assert result["error"] is None
    assert result["data"]["sub"] == "google_user_123"
    assert result["data"]["email"] == "test@example.com"


def test_validate_id_token_nonce_mismatch(google_provider):
    """Test that GoogleProvider.validate_id_token detects nonce mismatch for replay attack prevention.

    Verifies that when the nonce in the ID token doesn't match the expected nonce value,
    the provider returns an InvalidIDToken error, preventing token replay attacks.
    """
    claims = {
        "sub": "google_user_123",
        "email": "test@example.com",
        "iss": google_provider.google_issuer,
        "aud": google_provider.client_id,
        "exp": 1893456000,
        "iat": 1893450000,
        "nonce": "actual_nonce",
    }

    fake_token = SimpleNamespace(claims=claims)

    with (
        patch("py_auth.providers.google.KeySet.import_key_set"),
        patch("py_auth.providers.google.decode", return_value=fake_token),
        patch("py_auth.providers.google.JWTClaimsRegistry") as registry,
    ):
        registry.return_value.validate.return_value = None

        result = google_provider.validate_id_token(
            "fake.id.token",
            jwks={"keys": [{"kid": "key123"}]},
            nonce="wrong_nonce",
        )

    assert result["error"]["code"] == "InvalidIDToken"
    assert result["error"]["status_code"] == 401


def test_validate_id_token_decode_failure(google_provider):
    """Test that GoogleProvider.validate_id_token handles JWT decoding failures gracefully.

    Verifies that when the ID token cannot be decoded due to signature verification failure
    or other JWT decoding errors, the provider returns an InvalidIDToken error with 401 status.
    """
    with (
        patch("py_auth.providers.google.KeySet.import_key_set"),
        patch(
            "py_auth.providers.google.decode",
            side_effect=JoseError("invalid token"),
        ),
    ):
        result = google_provider.validate_id_token(
            "invalid.token",
            jwks={"keys": []},
        )

    assert result["error"]["code"] == "InvalidIDToken"
    assert result["error"]["status_code"] == 401