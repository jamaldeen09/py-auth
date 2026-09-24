
from pydantic import BaseModel

class LoginSchema(BaseModel):
    """Minimal login schema — just what I need to test credentials validation."""
    email: str
    password: str