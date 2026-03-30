from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


ENV_FILE = Path(__file__).resolve().parent / ".env"


class AppSettings(BaseSettings):
    openai_api_key: str = ""
    gemini_api_key: str = ""
    gemini_planning_model: str = "gemini-2.5-flash"
    gemini_generation_model: str = "gemini-2.5-flash"

    bing_search_api_key: str = ""
    xhs_cookie: str = ""
    a1: str = ""

    xhs_mcp_binary_path: str = "vendor/xiaohongshu-mcp/bin/xiaohongshu-mcp-windows-amd64.exe"
    xhs_login_binary_path: str = "vendor/xiaohongshu-mcp/bin/xiaohongshu-login-windows-amd64.exe"
    xhs_cookies_path: str = "vendor/xiaohongshu-mcp/cookies.json"
    xhs_mcp_base_url: str = "http://127.0.0.1:18060"

    backend_host: str = "0.0.0.0"
    backend_port: int = 8000
    backend_log_level: str = "info"
    backend_url: str = "http://localhost:8000"
    frontend_url: str = "http://localhost:8501"
    streamlit_server_port: int = 8501

    playwright_timeout: int = 30000
    random_delay_min: float = 1.5
    random_delay_max: float = 4.3
    captcha_detection_enabled: bool = True

    model_config = SettingsConfigDict(extra="ignore")

    def __init__(self, **data):
        env_file = data.pop("_env_file", ENV_FILE)
        super().__init__(_env_file=env_file, **data)

    @staticmethod
    def _has_value(value: str) -> bool:
        return bool(value and value.strip())

    @property
    def openai_enabled(self) -> bool:
        return self._has_value(self.openai_api_key)

    @property
    def gemini_enabled(self) -> bool:
        return self._has_value(self.gemini_api_key)

    @property
    def bing_enabled(self) -> bool:
        return self._has_value(self.bing_search_api_key)

    @property
    def mcp_enabled(self) -> bool:
        return self._has_value(self.xhs_cookie) and self._has_value(self.a1)

    @property
    def project_root(self) -> Path:
        return Path(__file__).resolve().parent

    @property
    def xhs_mcp_binary(self) -> Path:
        return (self.project_root / self.xhs_mcp_binary_path).resolve()

    @property
    def xhs_login_binary(self) -> Path:
        return (self.project_root / self.xhs_login_binary_path).resolve()

    @property
    def xhs_cookies_file(self) -> Path:
        return (self.project_root / self.xhs_cookies_path).resolve()
