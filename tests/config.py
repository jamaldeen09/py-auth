import os

from pathlib import Path
from dotenv import load_dotenv
from pydantic import BaseModel

current_dir = Path(__file__).resolve().parent
root_dir = current_dir.parent
dotenv_path = root_dir / '.env'

load_dotenv(dotenv_path=dotenv_path)

class Config (BaseModel):
    database_url: str

config = Config(
    database_url=os.getenv("DATABASE_URL")
)