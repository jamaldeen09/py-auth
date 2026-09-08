import os, hashlib, secrets, logging

from typing import Any, Dict, Mapping, Optional, Union

from .schemas import CookieConfig, PyAuthCookiesInput


def generate_token(num_bytes: int = 32) -> str:
    """Generate a cryptographically secure URL-safe token."""
    return secrets.token_urlsafe(num_bytes)


def hash_token(token: str) -> str:
    """Produce a SHA-256 hash digest of a given token string."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def get_logger():
    """Retrieve the centralized namespaced logger for the py-auth library.

    Using a dedicated namespace ('py_auth') allows consuming applications
    to configure logging levels, formats, or handlers specifically for this
    package without polluting or altering the main application's logs.
    """
    return logging.getLogger("py_auth")


_DEFAULTS = {
    "session_token": {
        "name": "__Host-py_auth_session",
        "options": {
            "http_only": True,
            "secure": True,
            "same_site": "lax",
            "path": "/",
            "max_age": 30 * 24 * 60 * 60,
        },
    },
    "csrf_token": {
        "name": "py_auth_csrf",
        "options": {
            "http_only": False,
            "secure": True,
            "same_site": "lax",
            "path": "/",
            "max_age": 60 * 60,
        },
    },
}


def merge_cookie_config(
    user_config: Optional[Union[PyAuthCookiesInput, Dict[str, Any]]] = None,
    *,
    is_production: bool = os.environ.get("ENVIRONMENT", "development") == "production",
) -> Dict[str, Dict[str, Any]]:
    """Merge user cookie options with safe defaults based on environment."""

    if isinstance(user_config, PyAuthCookiesInput):
        user_config_dict = user_config.model_dump(exclude_unset=True)
    elif isinstance(user_config, dict):
        user_config_dict = user_config
    else:
        user_config_dict = {}

    # Avoid slow copy.deepcopy by constructing a shallow/dict copy inline
    defaults = {
        k: {"name": v["name"], "options": v["options"].copy()}
        for k, v in _DEFAULTS.items()
    }

    keys = defaults.keys() | user_config_dict.keys()
    result: Dict[str, Dict[str, Any]] = {}

    for key in keys:
        default_cfg = defaults.get(key)
        if default_cfg:
            merged_name = default_cfg["name"]
            merged_opts = default_cfg["options"].copy()
        else:
            merged_name = key
            merged_opts = {"path": "/", "secure": is_production}

        user_val = user_config_dict.get(key)

        if isinstance(user_val, str):
            merged_name = user_val
        elif user_val is not None:
            if isinstance(user_val, CookieConfig):
                parsed = user_val
            elif isinstance(user_val, Mapping):
                parsed = CookieConfig.model_validate(user_val)
            else:
                parsed = None

            if parsed:
                if parsed.name is not None:
                    merged_name = parsed.name
                if parsed.options is not None:
                    merged_opts.update(parsed.options.model_dump(exclude_none=True))

        merged_opts.setdefault("secure", is_production)
        result[key] = {"name": merged_name, "options": merged_opts}

    return result
