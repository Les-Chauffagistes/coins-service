from pydantic_settings import BaseSettings
from typing import Literal


class Settings(BaseSettings):
    server_port: int
    database_url: str
    auth_service_url: str
    api_token: str
    jwt_secret: str

    model_config = {"env_file": ".env"}


settings = Settings()  # type: ignore[call-arg]
