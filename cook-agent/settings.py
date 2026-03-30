from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    openai_api_key: str = ""
    bing_search_api_key: str = ""
    xhs_cookie: str = ""
    a1: str = ""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @staticmethod
    def _has_value(value: str) -> bool:
        return bool(value and value.strip())

    @property
    def openai_enabled(self) -> bool:
        return self._has_value(self.openai_api_key)

    @property
    def bing_enabled(self) -> bool:
        return self._has_value(self.bing_search_api_key)

    @property
    def mcp_enabled(self) -> bool:
        return self._has_value(self.xhs_cookie) and self._has_value(self.a1)
