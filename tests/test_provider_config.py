from app.services.ai_providers import configured_provider_order

def test_auto_provider_order(monkeypatch):
    monkeypatch.setenv("AI_FALLBACK_ORDER", "gemini,ollama,openai")
    assert configured_provider_order("auto") == ["gemini", "ollama", "openai"]

def test_explicit_provider_skips_fallback(monkeypatch):
    monkeypatch.setenv("AI_FALLBACK_ORDER", "openai,gemini")
    assert configured_provider_order("ollama") == ["ollama"]
