"""
Plugin: send a message to Discord via webhook.

Setup (2 min, no bot needed):
  1. In Discord: channel settings -> Integrations -> Webhooks -> New Webhook
  2. Copy the webhook URL
  3. Add it to config/api_keys.json:
       "discord_webhook_url": "https://discord.com/api/webhooks/..."

A webhook can only POST messages, it can't read incoming ones. Reading
chat back would need a real bot (discord.py) that stays connected in the
background — ask if you want that version too, it's a bigger piece.
"""
import json
from pathlib import Path

import requests

_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "api_keys.json"


def _get_webhook_url():
    try:
        cfg = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
        return cfg.get("discord_webhook_url") or None
    except Exception:
        return None


def get_tools():
    return [
        {
            "declaration": {
                "name": "discord_send",
                "description": (
                    "Sends a message to the configured Discord channel. "
                    "Use when the user asks to post/send something to Discord."
                ),
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "message": {"type": "STRING", "description": "The message to post"},
                    },
                    "required": ["message"],
                },
            },
            "handler": discord_send,
        },
    ]


def discord_send(args: dict, player) -> str:
    url = _get_webhook_url()
    if not url:
        return (
            'Discord isn\'t set up — add "discord_webhook_url" to '
            "config/api_keys.json. See the docstring at the top of "
            "plugins/discord_webhook.py for the 3 setup steps."
        )

    message = (args.get("message") or "").strip()
    if not message:
        return "No message given."

    try:
        r = requests.post(url, json={"content": message}, timeout=8)
        r.raise_for_status()
    except Exception as e:
        return f"Discord send failed: {e}"

    return "Sent to Discord."