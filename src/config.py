# config.py — единая загрузка переменных окружения и настроек

from pathlib import Path
from dataclasses import dataclass
from typing import Optional
from os import getenv

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None


def load_env() -> None:
    """Загружает .env из корня проекта (родитель каталога src/)."""
    project_root = Path(__file__).resolve().parent.parent
    env_path = project_root / ".env"
    if env_path.exists() and load_dotenv:
        load_dotenv(str(env_path))


@dataclass(frozen=True)
class Settings:
    """Настройки из переменных окружения."""

    DB_HOST: str
    DB_PORT: int
    DB_USER: str
    DB_PASSWORD: str
    DB_NAME: str
    T_API_KEY: str
    BM_API_KEY: str
    ADMIN_ID: Optional[int]
    DEBUG_PROFILE_ID: Optional[int]
    STEAM_API_KEY: Optional[str]

    @classmethod
    def from_env(cls) -> "Settings":
        def _int_or_none(val: Optional[str]) -> Optional[int]:
            if val is None or (isinstance(val, str) and val.strip() == ""):
                return None
            try:
                return int(val)
            except (ValueError, TypeError):
                return 0

        port_str = getenv("DB_PORT", "3306")
        try:
            port = int(port_str)
        except (ValueError, TypeError):
            port = 3306

        return cls(
            DB_HOST=getenv("DB_HOST", "").strip() or "127.0.0.1",
            DB_PORT=port,
            DB_USER=getenv("DB_USER", "").strip() or "",
            DB_PASSWORD=getenv("DB_PASSWORD", "").strip() or "",
            DB_NAME=getenv("DB_NAME", "").strip() or "",
            T_API_KEY=getenv("T_API_KEY", "").strip() or "",
            BM_API_KEY=getenv("BM_API_KEY", "").strip() or "",
            ADMIN_ID=_int_or_none(getenv("ADMIN_ID")),
            DEBUG_PROFILE_ID=_int_or_none(getenv("DEBUG_PROFILE_ID")),
            STEAM_API_KEY=(getenv("STEAM_API_KEY") or "").strip() or None,
        )


_settings_cache: Optional[Settings] = None


def get_settings() -> Settings:
    """Возвращает настройки (singleton-кэш)."""
    global _settings_cache
    if _settings_cache is None:
        _settings_cache = Settings.from_env()
    return _settings_cache


def validate_required() -> None:
    """
    Проверяет наличие обязательных переменных для запуска бота.
    Вызывает исключение с перечислением отсутствующих переменных.
    """
    required = [
        "DB_HOST",
        "DB_USER",
        "DB_PASSWORD",
        "DB_NAME",
        "T_API_KEY",
        "BM_API_KEY",
    ]
    missing = []
    s = get_settings()
    mapping = {
        "DB_HOST": s.DB_HOST,
        "DB_USER": s.DB_USER,
        "DB_PASSWORD": s.DB_PASSWORD,
        "DB_NAME": s.DB_NAME,
        "T_API_KEY": s.T_API_KEY,
        "BM_API_KEY": s.BM_API_KEY,
    }
    for var in required:
        val = mapping.get(var, "")
        if val is None or (isinstance(val, str) and not val.strip()):
            missing.append(var)
    if missing:
        raise RuntimeError(
            "Отсутствуют обязательные переменные окружения: " + ", ".join(missing)
            + ". Скопируйте .env.example в .env и заполните значения."
        )
