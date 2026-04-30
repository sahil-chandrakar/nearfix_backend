from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_ignore_empty=True,
        extra="ignore",
    )

    app_name: str = "NearFix API"
    environment: Literal["local", "development", "staging", "production"] = "local"
    api_v1_prefix: str = "/api/v1"
    backend_cors_origins: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    secret_key: str = "change-this-secret-before-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    mysql_host: str = "localhost"
    mysql_port: int = 3306
    mysql_user: str = "nearfix_user"
    mysql_password: str = "nearfix_password"
    mysql_database: str = "nearfix"
    upload_dir: str = "uploads"

    @property
    def database_url(self) -> URL:
        return URL.create(
            "mysql+pymysql",
            username=self.mysql_user,
            password=self.mysql_password,
            host=self.mysql_host,
            port=self.mysql_port,
            database=self.mysql_database,
            query={"charset": "utf8mb4"},
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
