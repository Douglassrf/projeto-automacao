"""Domínio: texto-para-voz (ElevenLabs / OpenAI TTS)."""

from pydantic import BaseModel


class TTSVoiceConfig(BaseModel):
    elevenlabs_api_key: str | None = None
    elevenlabs_voice_id: str | None = None
    elevenlabs_model: str = "eleven_multilingual_v2"
    openai_tts_model: str = "gpt-4o-mini-tts"
    openai_tts_voice: str = "alloy"
