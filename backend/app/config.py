import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator, model_validator
from typing import List, Union

class Settings(BaseSettings):
    # App Settings
    APP_NAME: str = "Periyar University Entrance Examination Portal API"
    ENVIRONMENT: str = "development"  # Options: development, production
    API_V1_PREFIX: str = "/api/v1"
    SHOW_DOCS: bool = False
    
    # CORS Configuration
    BACKEND_CORS_ORIGINS: Union[str, List[str]] = ["*"]

    # Database Configuration
    DATABASE_URL: str = ""
    DATABASE_HOST: str = "localhost"
    DATABASE_PORT: int = 3306
    DATABASE_NAME: str = "periyar_entrance_exam"
    DATABASE_USER: str = "root"
    DATABASE_PASSWORD: str = ""

    # Security Configurations
    JWT_SECRET_KEY: str = ""
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 1 day
    STUDENT_TOKEN_EXPIRE_MINUTES: int = 240  # 4 hours


    # Seed Admin Settings
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD: str = "admin123"

    @property
    def db_url(self) -> str:
        if self.DATABASE_URL:
            return self.DATABASE_URL
        return f"mysql+pymysql://{self.DATABASE_USER}:{self.DATABASE_PASSWORD}@{self.DATABASE_HOST}:{self.DATABASE_PORT}/{self.DATABASE_NAME}?charset=utf8mb4"

    @property
    def root_db_url(self) -> str:
        return f"mysql+pymysql://{self.DATABASE_USER}:{self.DATABASE_PASSWORD}@{self.DATABASE_HOST}:{self.DATABASE_PORT}/mysql?charset=utf8mb4"

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> Union[List[str], str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",") if i.strip()]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError(v)

    @field_validator("ENVIRONMENT", mode="before")
    @classmethod
    def normalize_environment(cls, v: str) -> str:
        if isinstance(v, str):
            return v.lower().strip()
        return v

    @model_validator(mode="after")
    def validate_secrets(self) -> "Settings":
        secure_envs = ["production", "prod", "staging"]
        if self.ENVIRONMENT in secure_envs:
            # 1. JWT_SECRET_KEY checks
            weak_keys = [
                "periyar_university_entrance_exam_secret_key_2026",
                "periyar_university_entrance_exam_secret_key_2026_hardened",
                "change-this-to-a-long-random-secret",
                "secret",
                "default",
                "change_me",
                ""
            ]
            if not self.JWT_SECRET_KEY or self.JWT_SECRET_KEY.strip() in weak_keys:
                raise ValueError("JWT_SECRET_KEY cannot be empty or a default value in secure environments.")
            if len(self.JWT_SECRET_KEY) < 32:
                raise ValueError("JWT_SECRET_KEY must be at least 32 characters in secure environments.")

            # 2. ADMIN_USERNAME checks
            weak_usernames = ["admin", "change-me-admin", ""]
            if not self.ADMIN_USERNAME or self.ADMIN_USERNAME.strip() in weak_usernames:
                raise ValueError("ADMIN_USERNAME cannot be empty or a default placeholder in secure environments.")

            # 3. ADMIN_PASSWORD checks
            weak_passwords = [
                "admin123",
                "change-this-strong-admin-password",
                "password",
                "admin",
                ""
            ]
            if not self.ADMIN_PASSWORD or self.ADMIN_PASSWORD.strip() in weak_passwords:
                raise ValueError("ADMIN_PASSWORD cannot be empty or a default value in secure environments.")
            if len(self.ADMIN_PASSWORD) < 8:
                raise ValueError("ADMIN_PASSWORD must be at least 8 characters in secure environments.")

            # 4. DATABASE checks (if not using DATABASE_URL directly)
            if not self.DATABASE_URL:
                weak_db_passwords = ["12345678", "password", "root", ""]
                if not self.DATABASE_PASSWORD or self.DATABASE_PASSWORD.strip() in weak_db_passwords:
                    raise ValueError("DATABASE_PASSWORD cannot be empty or a default value in secure environments.")
                
                if not self.DATABASE_USER or not self.DATABASE_USER.strip():
                    raise ValueError("DATABASE_USER cannot be empty in secure environments.")
                
                if not self.DATABASE_NAME or not self.DATABASE_NAME.strip():
                    raise ValueError("DATABASE_NAME cannot be empty in secure environments.")
        return self

    model_config = SettingsConfigDict(
        env_file=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )

settings = Settings()

# Compatibility exports to avoid breaking imports in other files
DATABASE_URL = settings.db_url
ROOT_DATABASE_URL = settings.root_db_url
JWT_SECRET_KEY = settings.JWT_SECRET_KEY
JWT_ALGORITHM = settings.JWT_ALGORITHM
ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES
STUDENT_TOKEN_EXPIRE_MINUTES = settings.STUDENT_TOKEN_EXPIRE_MINUTES
DB_USER = settings.DATABASE_USER
DB_PASSWORD = settings.DATABASE_PASSWORD
DB_HOST = settings.DATABASE_HOST
DB_PORT = settings.DATABASE_PORT
DB_NAME = settings.DATABASE_NAME

