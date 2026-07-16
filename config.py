from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    gemini_api_key: SecretStr = SecretStr("")
    waqi_api_key: SecretStr = SecretStr("")
    city_bounds: dict = {"lat_min": 28.40, "lat_max": 28.88, "lon_min": 76.83, "lon_max": 77.34}
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = AppSettings()
