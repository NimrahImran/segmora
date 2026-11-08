from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    allowed_origins: str = "http://localhost:5173"
    allowed_origin_regex: str = ""
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.5-flash-lite,gemini-3.8-flash,gemini-flash-lite-latest"  # tried in order
    gmail_user: str = ""
    gmail_app_password: str = ""
    max_upload_mb: int = 4  # Vercel Functions accept request bodies up to 4.5 MB
    max_rows: int = 100_000
    max_customers: int = 20_000
    rate_limit_per_minute: int = 40
    model_path: Path = ROOT / "artifacts" / "segmora_model.json"
    data_path: Path = ROOT / "data" / "customers.csv"


@lru_cache
def get_settings() -> Settings:
    return Settings()
