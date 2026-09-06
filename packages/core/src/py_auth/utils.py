import os, copy, hashlib, secrets, logging

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

def merge_cookie_config(
    user_config: Optional[Union[PyAuthCookiesInput, Dict[str, Any]]] = None,
    *,
    is_production: bool = os.environ.get("ENVIRONMENT", "development") == "production",
) -> Dict[str, Dict[str, Any]]:
    """Merge user cookie options with safe defaults based on environment."""
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

    if isinstance(user_config, PyAuthCookiesInput):
        user_config_dict = user_config.model_dump(exclude_unset=True)
    elif isinstance(user_config, dict):
        user_config_dict = user_config
    else:
        user_config_dict = {}

    result: Dict[str, Dict[str, Any]] = {}
    defaults = copy.deepcopy(_DEFAULTS)

    # Ensure 'secure' default reflects production environment unless explicitly specified
    for cfg in defaults.values():
        if "options" in cfg and cfg["options"].get("secure") is None:
            cfg["options"]["secure"] = bool(is_production)

    keys = set(defaults.keys()) | set(user_config_dict.keys())

    for key in keys:
        default_cfg = defaults.get(
            key,
            {"name": key, "options": {"path": "/", "secure": bool(is_production)}},
        )
        user_val = user_config_dict.get(key)

        merged_name = default_cfg.get("name", key)
        merged_opts = dict(default_cfg.get("options", {}))

        if isinstance(user_val, str):
            merged_name = user_val
        elif isinstance(user_val, Mapping):
            parsed = (
                CookieConfig.model_validate(user_val)
                if hasattr(CookieConfig, "model_validate")
                else CookieConfig.parse_obj(user_val)
            )
            if parsed.name is not None:
                merged_name = parsed.name
            if parsed.options is not None:
                dump = (
                    parsed.options.model_dump(exclude_none=True)
                    if hasattr(parsed.options, "model_dump")
                    else parsed.options.dict(exclude_none=True)
                )
                merged_opts.update(dump)
        elif isinstance(user_val, CookieConfig):
            if user_val.name is not None:
                merged_name = user_val.name
            if user_val.options is not None:
                dump = (
                    user_val.options.model_dump(exclude_none=True)
                    if hasattr(user_val.options, "model_dump")
                    else user_val.options.dict(exclude_none=True)
                )
                merged_opts.update(dump)

        merged_opts.setdefault("secure", bool(is_production))
        result[key] = {"name": merged_name, "options": merged_opts}

    return result