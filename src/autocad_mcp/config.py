"""Configuracion del servidor, cargada desde variables de entorno / .env."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class AutoCADMCPConfig(BaseSettings):
    """Configuracion por variables de entorno (prefijo ``AUTOCAD_MCP_``)."""

    model_config = SettingsConfigDict(
        env_prefix="AUTOCAD_MCP_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    autocad_progid: str = "AutoCAD.Application"
    connect_timeout: float = 10.0
    retry_max_attempts: int = 5
    retry_wait_base: float = 1.0
    retry_wait_max: float = 30.0
    cache_ttl_seconds: float = 30.0
    cache_maxsize: int = 128
    log_level: str = "INFO"
    metrics_enabled: bool = True
    ftool_exe: str = ""
    ftool_output_dir: str = ""


@lru_cache(maxsize=1)
def get_config() -> AutoCADMCPConfig:
    """Devuelve la configuracion (cacheada)."""
    return AutoCADMCPConfig()
