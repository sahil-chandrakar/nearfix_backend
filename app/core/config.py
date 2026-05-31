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
    access_token_expire_minutes: int = 0

    mysql_host: str = "localhost"
    mysql_port: int = 3306
    mysql_user: str = "nearfix_user"
    mysql_password: str = "nearfix_password"
    mysql_database: str = "nearfix"
    mysql_unix_socket: str | None = None

    storage_backend: Literal["local", "gcs"] = "local"
    upload_dir: str = "uploads"
    gcs_bucket_name: str = ""
    gcs_upload_prefix: str = "uploads"

    @property
    def database_url(self) -> URL:
        return URL.create(
            "mysql+pymysql",
            username=self.mysql_user,
            password=self.mysql_password,
            database=self.mysql_database,
            host=None if self.mysql_unix_socket else self.mysql_host,
            port=None if self.mysql_unix_socket else self.mysql_port,
            query={
                "charset": "utf8mb4",
                **({"unix_socket": self.mysql_unix_socket} if self.mysql_unix_socket else {}),
            },
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
