from google.adk.models import Gemini
from google.genai import types

from app.settings import get_settings


def build_model() -> Gemini:
    """Create the configured Vertex AI-backed model without embedding credentials."""

    settings = get_settings()
    return Gemini(
        model=settings.gemini_core_model,
        retry_options=types.HttpRetryOptions(attempts=3),
    )
