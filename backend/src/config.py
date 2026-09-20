"""
Application settings: the only place the backend reads its environment.
Precedence, highest first:
  1. Real environment variables (Dockerfile ENV, compose, shell exports)
  2. backend/.env (gitignored, one per checkout, does not override 1)
  3. The defaults below
Paths come from DATA_DIR. In development it defaults to
<this checkout>/backend/data-dev, so every checkout and worktree gets its
own data. Production must set DATA_DIR explicitly.
"""
from __future__ import annotations
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, Optional, TypeVar
from dotenv import load_dotenv
from src.utils.logging import ContextLogger

logger = ContextLogger(__name__)
T = TypeVar("T")

BACKEND_DIR = Path(__file__).resolve().parent.parent  # .../backend
ENV_FILE = BACKEND_DIR / ".env"
VALID_ENVS = {"development", "test", "production"}
SECRET_MARKERS = ("KEY", "SECRET", "TOKEN", "PASSWORD")


class ConfigError(RuntimeError):
    """Invalid or missing configuration. Raised at startup."""


@dataclass(frozen=True)
class Settings:
    app_env: str
    data_dir: Path
    database_path: Path
    upload_folder: Path
    max_receipt_batch_size: int
    receipt_extraction_method: str
    ocr_method: str
    max_workers: int
    gemini_model: str
    gemini_max_concurrency: int
    llm_gateway_url: Optional[str]
    receipt_task_timeout: float
    receipt_stream_timeout: float
    receipt_stream_heartbeat: float
    receipt_match_date_tolerance_days: int
    receipt_match_amount_tolerance: float
    receipt_auto_link_threshold: float

    # Which layer each value came from: "environment" | ".env" | "default"
    sources: Dict[str, str] = field(default_factory=dict, compare=False)

    def to_flask_config(self) -> Dict[str, object]:
        return {
            "APP_ENV": self.app_env,
            "DATA_DIR": str(self.data_dir),
            "DATABASE_PATH": str(self.database_path),
            "UPLOAD_FOLDER": str(self.upload_folder),
            "MAX_RECEIPT_BATCH_SIZE": self.max_receipt_batch_size,
            "RECEIPT_EXTRACTION_METHOD": self.receipt_extraction_method,
            "OCR_METHOD": self.ocr_method,
            "MAX_WORKERS": self.max_workers,
            "GEMINI_MODEL": self.gemini_model,
            "GEMINI_MAX_CONCURRENCY": self.gemini_max_concurrency,
            "LLM_GATEWAY_URL": self.llm_gateway_url,
            "RECEIPT_TASK_TIMEOUT": self.receipt_task_timeout,
            "RECEIPT_STREAM_TIMEOUT": self.receipt_stream_timeout,
            "RECEIPT_STREAM_HEARTBEAT": self.receipt_stream_heartbeat,
            "RECEIPT_MATCH_DATE_TOLERANCE_DAYS": self.receipt_match_date_tolerance_days,
            "RECEIPT_MATCH_AMOUNT_TOLERANCE": self.receipt_match_amount_tolerance,
            "RECEIPT_AUTO_LINK_THRESHOLD": self.receipt_auto_link_threshold,
        }

    def log_summary(self) -> None:
        logger.info(f"Configuration | app_env={self.app_env} | env_file={ENV_FILE if ENV_FILE.exists() else 'none'}")
        for key, value in self.to_flask_config().items():
            shown = "***" if any(m in key for m in SECRET_MARKERS) and value else value
            logger.info(f"  {key:36} = {shown}  [{self.sources.get(key, 'derived')}]")


class _Reader:
    """Reads env vars and records which layer each one came from."""
    def __init__(self, before_dotenv: set[str]):
        self._before = before_dotenv
        self.sources: Dict[str, str] = {}

    def raw(self, key: str) -> Optional[str]:
        value = os.environ.get(key)
        if value is None or value.strip() == "":
            self.sources[key] = "default"
            return None  # An empty string counts as unset.
        self.sources[key] = "environment" if key in self._before else ".env"
        return value.strip()

    def get(self, key: str, default: T, cast: Callable[[str], T] = str) -> T:
        value = self.raw(key)
        if value is None:
            return default
        try:
            return cast(value)
        except ValueError as exc:
            raise ConfigError(f"{key}={value!r} is not a valid {cast.__name__}") from exc

        
def load_settings() -> Settings:
    before = set(os.environ)

    if ENV_FILE.exists():
        load_dotenv(ENV_FILE, override=False)

    env = _Reader(before)
    app_env = env.get("APP_ENV", "development").lower()

    if app_env not in VALID_ENVS:
        raise ConfigError(f"APP_ENV must be one of {sorted(VALID_ENVS)}, got {app_env!r}")
    
    data_dir_raw = env.raw("DATA_DIR")
    if data_dir_raw is None:
        if app_env == "production":
            raise ConfigError("DATA_DIR must be set in production")
        data_dir = BACKEND_DIR / "data-dev"
    else:
        data_dir = Path(data_dir_raw).expanduser()
        if not data_dir.is_absolute():
            data_dir = BACKEND_DIR / data_dir  # relative to backend/, not to the cwd
    data_dir = data_dir.resolve()

    settings = Settings(
        app_env=app_env,
        data_dir=data_dir,
        database_path=data_dir / "financial_data.db",
        upload_folder=data_dir / "uploads",
        max_receipt_batch_size=env.get("MAX_RECEIPT_BATCH_SIZE", 50, int),
        receipt_extraction_method=env.get("RECEIPT_EXTRACTION_METHOD", "ocr"),
        ocr_method=env.get("OCR_METHOD", "paddle"),
        max_workers=env.get("MAX_WORKERS", 2, int),
        gemini_model=env.get("GEMINI_MODEL", "gemini-3.5-flash"),
        gemini_max_concurrency=env.get("GEMINI_MAX_CONCURRENCY", 4, int),
        llm_gateway_url=env.raw("LLM_GATEWAY_URL"),
        receipt_task_timeout=env.get("RECEIPT_TASK_TIMEOUT", 180.0, float),
        receipt_stream_timeout=env.get("RECEIPT_STREAM_TIMEOUT", 900.0, float),
        receipt_stream_heartbeat=env.get("RECEIPT_STREAM_HEARTBEAT", 10.0, float),
        receipt_match_date_tolerance_days=env.get("RECEIPT_MATCH_DATE_TOLERANCE_DAYS", 5, int),
        receipt_match_amount_tolerance=env.get("RECEIPT_MATCH_AMOUNT_TOLERANCE", 0.01, float),
        receipt_auto_link_threshold=env.get("RECEIPT_AUTO_LINK_THRESHOLD", 0.98, float),
        sources=env.sources,
    )

    _validate(settings)

    return settings

def _validate(s: Settings) -> None:
    if s.receipt_match_date_tolerance_days < 0:
        raise ConfigError("RECEIPT_MATCH_DATE_TOLERANCE_DAYS must be >= 0")
    if s.receipt_match_amount_tolerance < 0:
        raise ConfigError("RECEIPT_MATCH_AMOUNT_TOLERANCE must be >= 0")
    if not 0.0 <= s.receipt_auto_link_threshold <= 1.01:
        raise ConfigError("RECEIPT_AUTO_LINK_THRESHOLD must be in [0, 1.01]")
    if s.receipt_stream_heartbeat * 2 >= 30:
        # The frontend's STREAM_IDLE_TIMEOUT_MS is 30s. Heartbeats must arrive well within it.
        raise ConfigError("RECEIPT_STREAM_HEARTBEAT must be under 15s (frontend idle timeout is 30s)")