"""Central configuration. Every setting comes from environment variables / backend/.env.

Why: swapping the model server (Ollama -> vLLM -> OpenAI/Claude) or database is a config
change, never a code change ("provider independence" from the blueprint).
"""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=Path(__file__).resolve().parents[1] / ".env", extra="ignore")

    # LLM + embeddings (OpenAI-compatible endpoint; Ollama on the lab GPU via SSH tunnel)
    llm_base_url: str = "http://localhost:11434/v1"
    llm_api_key: str = "ollama"  # Ollama ignores it; real providers need one
    llm_model: str = "hf.co/Qwen/Qwen3-14B-GGUF:Q4_K_M"
    llm_fallback_model: str = "hf.co/Qwen/Qwen3-8B-GGUF:Q4_K_M"
    embed_base_url: str = ""  # optional separate server for embeddings (empty = same as llm_base_url)
    embed_model: str = "hf.co/gpustack/bge-m3-GGUF:Q8_0"
    embed_dim: int = 1024

    # Storage
    database_url: str = "postgresql+psycopg://bennett:bennett_dev@localhost:5433/bennett_one"
    qdrant_path: str = str(REPO_ROOT / "data" / "qdrant")  # embedded mode: a local folder, no server
    qdrant_collection: str = "bennett_chunks"

    # Data
    raw_dir: str = str(REPO_ROOT / "data" / "raw")
    private_dir: str = str(REPO_ROOT / "data" / "private")
    seed_dir: str = str(REPO_ROOT / "data" / "seed")

    # Auth
    jwt_secret: str = "change-me-in-.env"
    jwt_expire_minutes: int = 60 * 24


@lru_cache
def get_settings() -> Settings:
    return Settings()
