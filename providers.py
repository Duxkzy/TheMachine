"""
AI provider registry.

Lets you pick which model runs the assistant instead of it being hardcoded.

An honest note on what's actually possible, because it shapes everything
here: this app's voice mode is built on Gemini's Live API — a websocket
carrying realtime audio in both directions plus tool calls. That protocol
is Google-specific. OpenAI has its own Realtime API (different protocol,
would need a separate client), and Anthropic has no realtime audio API at
all today. So:

    VOICE  works on Gemini Live models only, for now.
    TEXT   works on all three (typed input, no microphone).

Rather than pretend otherwise, each entry below declares what it can do,
and the UI shows it.
"""
from __future__ import annotations

import json
from pathlib import Path

CONFIG_PATH = Path(__file__).resolve().parent / "config" / "api_keys.json"

# capability flags
VOICE = "voice"      # realtime bidirectional audio + tools
TEXT  = "text"       # typed prompt in, text out

PROVIDERS = {
    "gemini": {
        "label": "Google Gemini",
        "key_field": "gemini_api_key",
        "models": [
            {
                "id": "models/gemini-2.5-flash-native-audio-preview-12-2025",
                "label": "Gemini 2.5 Flash — native audio (default)",
                "caps": [VOICE, TEXT],
                "note": "Full voice mode. What the app was built around.",
            },
            {
                "id": "models/gemini-live-2.5-flash-preview",
                "label": "Gemini 2.5 Flash Live",
                "caps": [VOICE, TEXT],
                "note": "Alternative live model — try if the default misbehaves.",
            },
            {
                "id": "gemini-2.5-flash",
                "label": "Gemini 2.5 Flash — text only",
                "caps": [TEXT],
                "note": "Cheaper/faster, but no microphone.",
            },
            {
                "id": "gemini-2.5-pro",
                "label": "Gemini 2.5 Pro — text only",
                "caps": [TEXT],
                "note": "Strongest Gemini for reasoning. No microphone.",
            },
        ],
    },
    "openai": {
        "label": "OpenAI",
        "key_field": "openai_api_key",
        "models": [
            {
                "id": "gpt-4o",
                "label": "GPT-4o",
                "caps": [TEXT],
                "note": "Voice would need OpenAI's Realtime API — not wired up yet.",
            },
            {
                "id": "gpt-4o-mini",
                "label": "GPT-4o mini",
                "caps": [TEXT],
                "note": "Cheaper. Text only here.",
            },
        ],
    },
    "anthropic": {
        "label": "Anthropic Claude",
        "key_field": "anthropic_api_key",
        "models": [
            {
                "id": "claude-sonnet-4-5",
                "label": "Claude Sonnet 4.5",
                "caps": [TEXT],
                "note": "No realtime audio API exists — text only.",
            },
            {
                "id": "claude-opus-4-5",
                "label": "Claude Opus 4.5",
                "caps": [TEXT],
                "note": "Strongest Claude. Text only.",
            },
        ],
    },
}

DEFAULT_PROVIDER = "gemini"
DEFAULT_MODEL = PROVIDERS["gemini"]["models"][0]["id"]


# ── config ──────────────────────────────────────────────────────────────

def _read_config() -> dict:
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def get_selection() -> tuple[str, str]:
    """Returns (provider_id, model_id), falling back to the default if the
    saved one no longer exists in the registry."""
    cfg = _read_config()
    prov = cfg.get("ai_provider", DEFAULT_PROVIDER)
    model = cfg.get("ai_model", DEFAULT_MODEL)
    if prov not in PROVIDERS:
        return DEFAULT_PROVIDER, DEFAULT_MODEL
    if not any(m["id"] == model for m in PROVIDERS[prov]["models"]):
        return prov, PROVIDERS[prov]["models"][0]["id"]
    return prov, model


def save_selection(provider: str, model: str) -> None:
    cfg = _read_config()
    cfg["ai_provider"] = provider
    cfg["ai_model"] = model
    CONFIG_PATH.parent.mkdir(exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(cfg, indent=4), encoding="utf-8")


def get_api_key(provider: str) -> str:
    field = PROVIDERS.get(provider, {}).get("key_field", "")
    return str(_read_config().get(field, "") or "")


def find_model(provider: str, model_id: str) -> dict | None:
    for m in PROVIDERS.get(provider, {}).get("models", []):
        if m["id"] == model_id:
            return m
    return None


def supports_voice(provider: str, model_id: str) -> bool:
    m = find_model(provider, model_id)
    return bool(m and VOICE in m["caps"])


def status_line() -> str:
    """One line describing the current pick — handy for logs."""
    prov, model = get_selection()
    m = find_model(prov, model)
    label = m["label"] if m else model
    mode = "voice + text" if supports_voice(prov, model) else "text only"
    have_key = "key set" if get_api_key(prov) else "NO KEY"
    return f"{PROVIDERS[prov]['label']} · {label} · {mode} · {have_key}"


# ── text calls (all three providers) ────────────────────────────────────

def ask_text(prompt: str, system: str = "", provider: str = "",
             model: str = "", timeout: int = 60) -> str:
    """Sends one text prompt to the chosen provider and returns the reply.

    Used for typed input when the selected model can't do voice. Each
    provider gets its own branch because the request shapes genuinely
    differ — there's no useful common wire format between them.
    """
    if not provider or not model:
        provider, model = get_selection()

    key = get_api_key(provider)
    if not key:
        field = PROVIDERS[provider]["key_field"]
        return f"No API key for {PROVIDERS[provider]['label']} — set '{field}' in API KEYS."

    try:
        import requests
    except ImportError:
        return "The 'requests' package is required for text mode."

    try:
        if provider == "gemini":
            url = (
                "https://generativelanguage.googleapis.com/v1beta/models/"
                f"{model.replace('models/', '')}:generateContent"
            )
            body = {"contents": [{"parts": [{"text": prompt}]}]}
            if system:
                body["systemInstruction"] = {"parts": [{"text": system}]}
            r = requests.post(url, params={"key": key}, json=body, timeout=timeout)
            r.raise_for_status()
            data = r.json()
            return (
                data["candidates"][0]["content"]["parts"][0]["text"].strip()
            )

        if provider == "openai":
            msgs = ([{"role": "system", "content": system}] if system else []) + [
                {"role": "user", "content": prompt}
            ]
            r = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {key}"},
                json={"model": model, "messages": msgs},
                timeout=timeout,
            )
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"].strip()

        if provider == "anthropic":
            body = {
                "model": model,
                "max_tokens": 2048,
                "messages": [{"role": "user", "content": prompt}],
            }
            if system:
                body["system"] = system
            r = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json=body,
                timeout=timeout,
            )
            r.raise_for_status()
            parts = [b.get("text", "") for b in r.json().get("content", [])]
            return "".join(parts).strip()

        return f"Unknown provider: {provider}"

    except Exception as e:
        detail = ""
        resp = getattr(e, "response", None)
        if resp is not None:
            try:
                detail = f" — {resp.json().get('error', {}).get('message', '')}"
            except Exception:
                detail = f" — HTTP {resp.status_code}"
        return f"{PROVIDERS[provider]['label']} request failed: {e}{detail}"


if __name__ == "__main__":
    print(status_line())
    for pid, p in PROVIDERS.items():
        key = "set" if get_api_key(pid) else "missing"
        print(f"\n{p['label']}  (key: {key})")
        for m in p["models"]:
            print(f"   {'V' if VOICE in m['caps'] else ' '}  {m['label']}")
