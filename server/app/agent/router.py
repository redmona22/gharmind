from app.config import settings

_HARD_WORDS = ("loan", "emi", "agreement", "rera", "registration", "stamp duty", "possession")


def _models() -> tuple[str, str]:
    """(routine model, complex model) for the chosen provider."""
    if settings.llm_provider == "anthropic":
        return settings.anthropic_model_routine, settings.anthropic_model_complex
    return settings.llm_model_routine, settings.llm_model_complex or settings.llm_model_routine


def pick_model(text: str, inbound_count: int) -> str:
    """Smaller model for routine chat, stronger one for long or technical conversations."""
    routine, hard_model = _models()
    t = (text or "").lower()
    hard = len(t) > 400 or inbound_count > 8 or any(w in t for w in _HARD_WORDS)
    return hard_model if hard else routine
