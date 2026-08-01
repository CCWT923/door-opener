from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    ALLOWED_ORIGINS: list[str] = ["*"]
    ADMIN_PASSWORD: str
    SECRET_KEY: str
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter=",",
        extra="ignore"
    )
        
settings = Settings()