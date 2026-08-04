import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

print("Installing requirements...")
subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"], check=True)

print("Installing Playwright browsers...")
subprocess.run([sys.executable, "-m", "playwright", "install"], check=True)

# ── Scaffold folders so the app has somewhere to write its API key, and drop
#    in a default persona if one isn't already sitting in core/prompt.txt ────
(BASE_DIR / "config").mkdir(exist_ok=True)
(BASE_DIR / "core").mkdir(exist_ok=True)

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
    print("(edit that file any time to change how it talks)")

print("\n✅ Setup complete! Add your Gemini API key on first launch, then")
print("   run 'python main.py' to start THE MACHINE.")