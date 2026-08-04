"""
Plugin: Spotify playback control (play/pause/skip/search) via spotipy,
which handles the OAuth login flow for you.

Setup:
  pip install spotipy

  1. Create an app at https://developer.spotify.com/dashboard
  2. Add a Redirect URI in the dashboard, e.g. http://localhost:8888/callback
     (use the exact same one in config/api_keys.json below)
  3. Add to config/api_keys.json:
       "spotify": {
         "client_id": "...",
         "client_secret": "...",
         "redirect_uri": "http://localhost:8888/callback"
       }
  4. First time you use it, a browser tab opens once to approve access —
     after that spotipy caches the token in plugins/.spotify_cache and it's
     silent from then on.

Note: playback control (play/pause/skip) needs Spotify Premium. Free
accounts can still use the "search" action.
"""
import json
from pathlib import Path

_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "api_keys.json"
_CACHE_PATH  = Path(__file__).resolve().parent / ".spotify_cache"

_client = None   # cached so we don't re-auth on every call


def _get_client():
    global _client
    if _client is not None:
        return _client

    try:
        import spotipy
        from spotipy.oauth2 import SpotifyOAuth
    except ImportError:
        return None   # spotipy not installed yet

    try:
        cfg = json.loads(_CONFIG_PATH.read_text(encoding="utf-8")).get("spotify", {})
        if not all(cfg.get(k) for k in ("client_id", "client_secret", "redirect_uri")):
            return None   # config not filled in yet

        _client = spotipy.Spotify(auth_manager=SpotifyOAuth(
            client_id=cfg["client_id"],
            client_secret=cfg["client_secret"],
            redirect_uri=cfg["redirect_uri"],
            scope="user-modify-playback-state user-read-playback-state",
            cache_path=str(_CACHE_PATH),
        ))
    except Exception:
        return None

    return _client


def get_tools():
    return [
        {
            "declaration": {
                "name": "spotify_control",
                "description": (
                    "Controls Spotify playback: play, pause, skip forward/back, "
                    "or search + play a track. Needs Spotify Premium for playback control."
                ),
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "action": {"type": "STRING", "description": "play | pause | next | previous | search"},
                        "query":  {"type": "STRING", "description": "Track/artist name (search action only)"},
                    },
                    "required": ["action"],
                },
            },
            "handler": spotify_control,
        },
    ]


def spotify_control(args: dict, player) -> str:
    sp = _get_client()
    if sp is None:
        return (
            "Spotify isn't set up yet — pip install spotipy and fill in "
            'the "spotify" section of config/api_keys.json. '
            "See the docstring at the top of plugins/spotify.py."
        )

    action = (args.get("action") or "").lower()

    try:
        if action == "play":
            sp.start_playback()
            return "Playing."
        if action == "pause":
            sp.pause_playback()
            return "Paused."
        if action == "next":
            sp.next_track()
            return "Skipped."
        if action == "previous":
            sp.previous_track()
            return "Went back a track."
        if action == "search":
            query = args.get("query", "")
            res = sp.search(q=query, type="track", limit=1)
            items = res.get("tracks", {}).get("items", [])
            if not items:
                return f"No track found for '{query}'."
            track = items[0]
            sp.start_playback(uris=[track["uri"]])
            return f"Playing '{track['name']}' by {track['artists'][0]['name']}."
        return f"Unknown Spotify action: {action}"
    except Exception as e:
        return f"Spotify request failed: {e}"
