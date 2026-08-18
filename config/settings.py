from dataclasses import dataclass
from pathlib import Path
import os

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")


@dataclass(frozen=True)
class Settings:
    kis_env: str
    kis_app_key: str
    kis_app_secret: str
    dart_api_key: str
    db_path: Path
    log_level: str

    @property
    def kis_base_url(self) -> str:
        if self.kis_env.lower() in {"real", "prod", "production"}:
            return "https://openapi.koreainvestment.com:9443"
        if self.kis_env.lower() in {"virtual", "paper", "demo"}:
            return "https://openapivts.koreainvestment.com:29443"
        raise ValueError("KIS_ENV는 real 또는 virtual이어야 합니다.")


def get_settings() -> Settings:
    raw_path = os.getenv("DB_PATH", "./data/stock_analytics.db")
    return Settings(
        kis_env=os.getenv("KIS_ENV", "virtual"),
        kis_app_key=os.getenv("KIS_APP_KEY", ""),
        kis_app_secret=os.getenv("KIS_APP_SECRET", ""),
        dart_api_key=os.getenv("DART_API_KEY", ""),
        db_path=(PROJECT_ROOT / raw_path).resolve(),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
    )
