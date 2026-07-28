from pydantic import BaseSettings, Field


class ServiceSettings(BaseSettings):
    host: str = Field("127.0.0.1", env="AURA_HOST")
    port: int = Field(8765, env="AURA_PORT")
    log_level: str = Field("INFO", env="AURA_LOG_LEVEL")
    ws_path: str = Field("/ws", env="AURA_WS_PATH")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = ServiceSettings()
