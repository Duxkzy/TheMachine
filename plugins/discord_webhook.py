"""
Plugin: look up a Roblox username.
No API key needed — uses Roblox's public search endpoint.

This is the simplest possible plugin, good as a template: get_tools()
tells main.py what the tool looks like to Gemini, and the handler function
actually does the work and returns a string.
"""
import requests


def get_tools():
    return [
        {
            "declaration": {
                "name": "roblox_lookup",
                "description": (
                    "Looks up a Roblox user by username: user ID, display "
                    "name, and bio. Use when the user asks about a Roblox "
                    "username or profile."
                ),
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "username": {"type": "STRING", "description": "Exact Roblox username"},
                    },
                    "required": ["username"],
                },
            },
            "handler": roblox_lookup,
        },
    ]


def roblox_lookup(args: dict, player) -> str:
    username = (args.get("username") or "").strip()
    if not username:
        return "No username given."

    try:
        r = requests.get(
            "https://users.roblox.com/v1/users/search",
            params={"keyword": username, "limit": 10},
            timeout=8,
        )
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        return f"Roblox lookup failed: {e}"

    users = data.get("data", [])
    # prefer an exact match, fall back to the first result
    exact = [u for u in users if u.get("name", "").lower() == username.lower()]
    user = exact[0] if exact else (users[0] if users else None)
    if not user:
        return f"No Roblox user found for '{username}'."

    bio = user.get("description") or "(no bio set)"
    return (
        f"{user['name']} — display name '{user.get('displayName', user['name'])}', "
        f"user ID {user['id']}. Bio: {bio}"
    )
