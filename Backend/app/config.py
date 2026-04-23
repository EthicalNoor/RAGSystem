import os
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
    host: str = "0.0.0.0"
    port: int = 8000
    environment: str = "production"
    cors_origins: Union[str, List[str]] = ["*"]

    database_url: str 
    
    openai_api_key: str = ""
    gemini_api_key: str = ""
    
    api_provider: str = "gemini"
    embedding_model: str = "models/text-embedding-004"
    llm_model: str = "gemini-1.5-pro"
    chunk_size: int = 1024
    temperature: float = 0.2
    
    # New Field: RAG Architecture
    rag_type: str = "standard" 
    
    upload_dir: str = "./uploads"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @field_validator("cors_origins", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError(v)

    @model_validator(mode='after')
    def check_api_keys(self) -> 'Config':
        if not self.openai_api_key and not self.gemini_api_key:
            raise ValueError("CRITICAL ERROR: Neither OPENAI_API_KEY nor GEMINI_API_KEY is found.")
        return self

@lru_cache()
def get_config() -> Config:
    return Config()

def update_env_file(key: str, value: str):
    """Helper to persist config changes to the .env file so they survive reboots."""
    env_path = ".env"
    if not os.path.exists(env_path):
        return
        
    try:
        with open(env_path, "r") as file:
            lines = file.readlines()
            
        key_found = False
        for i, line in enumerate(lines):
            if line.strip().startswith(f"{key}="):
                lines[i] = f"{key}={value}\n"
                key_found = True
                break
                
        if not key_found:
            if lines and not lines[-1].endswith('\n'):
                lines[-1] = lines[-1] + '\n'
            lines.append(f"{key}={value}\n")
            
        with open(env_path, "w") as file:
            file.writelines(lines)
    except Exception as e:
        get_logger(__name__).error(f"Failed to write to .env file: {str(e)}")