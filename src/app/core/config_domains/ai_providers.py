"""Domínio: provedores de IA (texto, LLM local/externo)."""

from pydantic import BaseModel


class AIProvidersConfig(BaseModel):
    ai_provider: str = "local_template"
    openai_api_key: str | None = None
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1"
    google_gemini_api_key: str | None = None
    huggingface_token: str | None = None
    huggingface_video_space: str | None = None
