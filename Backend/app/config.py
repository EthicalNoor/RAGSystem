import logging
from typing import List, Union
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import model_validator, field_validator
from functools import lru_cache

class StrictLogger:
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)

    def info(self, msg: str, *args, **kwargs):
        self.logger.info(msg, *args, **kwargs)

    def warning(self, msg: str, *args, **kwargs):
        self.logger.warning(msg, *args, **kwargs)

    def error(self, msg: str, *args, **kwargs):
        self.logger.error(msg, *args, **kwargs)

def get_logger(name: str) -> StrictLogger:
    return StrictLogger(name)

class Config(BaseSettings):
    # Server & Deployment Settings
    host: str = "0.0.0.0"
    port: int = 8000
    environment: str = "production"
    cors_origins: Union[str, List[str]] = ["*"]

    # Database
    database_url: str 
    
    # API Keys
    openai_api_key: str = ""
    gemini_api_key: str = ""
    
    # Default RAG Parameters
    api_provider: str = "gemini"
    embedding_model: str = "models/text-embedding-004"
    llm_model: str = "gemini-1.5-pro"
    chunk_size: int = 1024
    temperature: float = 0.2
    upload_dir: str = "./uploads"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @field_validator("cors_origins", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        """Allows CORS origins to be passed as a comma-separated string in the .env"""
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError(v)

    @model_validator(mode='after')
    def check_api_keys(self) -> 'Config':
        """Ensure that at least one API key is present at runtime."""
        if not self.openai_api_key and not self.gemini_api_key:
            raise ValueError(
                "CRITICAL ERROR: Neither OPENAI_API_KEY nor GEMINI_API_KEY is found in the environment. "
                "At least one must be provided to run the RAG system."
            )
        return self

@lru_cache()
def get_config() -> Config:
    return Config()