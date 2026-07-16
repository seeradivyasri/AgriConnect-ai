from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Literal

class Settings(BaseSettings):
    # Groq LLM / Vision
    GROQ_API_KEY: str
    GROQ_BASE_URL: str
    GROQ_TEXT_MODEL: str
    GROQ_VISION_MODEL: str

    # Databases
    DATABASE_URL: str
    REDIS_URL: str

    # Object Storage (MinIO)
    MINIO_ENDPOINT: str
    MINIO_ACCESS_KEY: str
    MINIO_SECRET_KEY: str
    MINIO_BUCKET: str
    MINIO_SECURE: bool

    # Security
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str
    JWT_EXPIRE_MINUTES: int

    # App Config
    OTP_MODE: Literal["mock", "prod"]
    APP_ENV: Literal["development", "production", "test"]
    LOG_LEVEL: str

    # Tell pydantic-settings to read from the .env file in the root
    model_config = SettingsConfigDict(
        env_file="../.env", # Path relative to the backend/ execution context
        env_file_encoding="utf-8", 
        extra="ignore"
    )

settings = Settings()
