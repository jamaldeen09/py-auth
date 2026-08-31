from typing import Any
from datetime import datetime, timezone, timedelta
import jwt, sys

def clean_value(original_value: Any, data_type: type):
    DEFAULT_MAP = {str: "", int: 0, float: 0.0, callable: lambda: None}

    new_value = original_value
    # Check if data_type is callable, if it is then properly check
    # if the original value is a function by running callable()
    if data_type == callable:
        if not (original_value is not None and callable(original_value)):
            new_value = DEFAULT_MAP[data_type]

    else:
        if not isinstance(original_value, data_type):
            new_value = DEFAULT_MAP.get(data_type, None)

    # Return the newly cleaned value
    return new_value


def create_token(payload: dict[str, Any], secret: str) -> str:
    to_encode = payload.copy()
    expires_delta = timedelta(hours=1)
    expire = datetime.now(timezone.utc) + expires_delta
    
    # Standard JWT expiration claim
    to_encode.update({"exp": expire})
    
    encoded_jwt = jwt.encode(to_encode, secret, algorithm="HS256")
    return encoded_jwt


def log(level: str, message: str, details: str = None):
    """
    Prints a distinctively branded, modern terminal log for py_auth.
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # ANSI Color Codes & Styles
    RESET = "\033[0m"
    DIM = "\033[2m"
    
    # Signature branding badge for the py-auth (Magenta/Purple background)
    BRAND_BADGE = "\033[45m\033[37m py-auth \033[0m"
    
    # Level-specific badge styling
    if level.upper() == "INFO":
        level_badge = f"{DIM}[INFO]{RESET}"
        text_color = "\033[36m" # Cyan
    elif level.upper() == "SUCCESS":
        level_badge = "\033[32m✔ SUCCESS\033[0m"
        text_color = "\033[32m"
    elif level.upper() == "WARNING":
        level_badge = "\033[33m⚠ WARNING\033[0m"
        text_color = "\033[33m"
    elif level.upper() == "ERROR":
        level_badge = "\033[31m✖ ERROR\033[0m"
        text_color = "\033[31m"
    else:
        level_badge = "[LOG]"
        text_color = RESET

    # Output the structured, branded log line
    print(f"{DIM}{timestamp}{RESET} {BRAND_BADGE} {level_badge} {text_color}{message}{RESET}", file=sys.stderr)
    
    # Optional diagnostic detail line
    if details:
        print(f"             {DIM}╰─ {details}{RESET}", file=sys.stderr)