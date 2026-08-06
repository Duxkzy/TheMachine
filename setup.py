import subprocess
import sys
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

print("Installing requirements...")
subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"], check=True)

print("Installing Playwright browsers...")
subprocess.run([sys.executable, "-m", "playwright", "install"], check=True)

# Scaffold necessary folders
(BASE_DIR / "config").mkdir(exist_ok=True)
(BASE_DIR / "core").mkdir(exist_ok=True)
(BASE_DIR / "plugins").mkdir(exist_ok=True)
(BASE_DIR / "memory").mkdir(exist_ok=True)

# Securely check and scaffold api_keys.json template if it doesn't exist
api_keys_path = BASE_DIR / "config" / "api_keys.json"
if not api_keys_path.exists():
    default_keys = {
        "gemini_api_key": ""
    }
    api_keys_path.write_text(json.dumps(default_keys, indent=4), encoding="utf-8")
    print(f"Created secure template at {api_keys_path}")

# Default system persona prompt
prompt_path = BASE_DIR / "core" / "prompt.txt"
if not prompt_path.exists():
    prompt_path.write_text(
        (
            "You are an autonomous monitoring and response system with real tools "
            "connected to this computer. Your job is to notice patterns, answer "
            "precisely, and act — not to perform a personality.\n\n"
            "VOICE AND MANNER\n"
            "- Speak in short, plain sentences. No filler, no small talk, no unearned enthusiasm.\n"
            "- State findings as findings, not as excitement.\n"
            "- Do not use \"sir\", \"boss\", or any formal address.\n"
            "- If something is wrong or risky, say so plainly, once.\n\n"
            "OPERATING RULES\n"
            "- Never simulate or guess a result — always call the matching tool and "
            "report exactly what it returned.\n"
            "- If a tool fails, report the failure plainly and suggest one concrete next step.\n"
            "- Keep responses short by default; expand only when asked or genuinely needed.\n"
            "- Match the user's language automatically.\n"
        ),
        encoding="utf-8",
    )
    print(f"Created default persona at {prompt_path}")

print("\nSetup complete! Configure your API key in config/api_keys.json or via UI, then run 'python main.py' to start THE MACHINE.")