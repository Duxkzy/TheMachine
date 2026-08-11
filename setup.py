#!/usr/bin/env python3
"""
Setup for THE MACHINE.

Works on Linux (any distro), macOS, and Windows. Handles the annoying
parts: externally-managed environments (PEP 668), missing requirements
file, optional extras that shouldn't kill the install if they fail.

Run:  python setup.py
"""
import json
import platform
import subprocess
import sys
import urllib.request
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
OS_NAME  = platform.system()          # "Linux" | "Darwin" | "Windows"
IN_VENV  = sys.prefix != sys.base_prefix

HAND_MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/hand_landmarker/"
    "hand_landmarker/float16/1/hand_landmarker.task"
)

# Core packages. Pinned loosely so pip can still resolve on older Pythons.
CORE_REQUIREMENTS = [
    "google-genai>=1.0.0",
    "PyQt6>=6.6",
    "sounddevice>=0.4.6",
    "psutil>=5.9",
    "pillow>=10.0",
    "requests>=2.31",
    "numpy>=1.24",
    "opencv-python>=4.8",
    "qrcode[pil]>=7.4",
    "pyautogui>=0.9.54",
    "playwright>=1.40",
]

# Nice-to-have. If any of these fail we warn and move on — the app runs
# without them, just with the matching feature switched off.
OPTIONAL_REQUIREMENTS = [
    ("vosk",              'offline wake word ("The Machine")'),
    ("mediapipe",         "AR hand tracking + orbital core hand steering"),
    ("fastapi",           "phone remote dashboard"),
    ("uvicorn[standard]", "phone remote dashboard"),
    ("cryptography",      "phone remote dashboard"),
    ("spotipy",           "Spotify plugin"),
    ("pynvml",            "GPU usage readout (NVIDIA only)"),
]

# Windows-only extras that make shortcuts + temperature readouts work.
WINDOWS_EXTRAS = [
    ("pywin32", "desktop shortcut creation"),
    ("wmi",     "CPU temperature readout"),
]


def say(msg=""):
    print(msg, flush=True)


def header(msg):
    say()
    say(f"-- {msg} " + "-" * max(0, 62 - len(msg)))


def pip_install(args, label):
    """pip install that copes with PEP 668 externally-managed environments.
    Returns True on success."""
    base = [sys.executable, "-m", "pip", "install"]
    try:
        subprocess.run(base + args, check=True)
        return True
    except subprocess.CalledProcessError:
        if IN_VENV:
            say(f"  ! {label} failed.")
            return False
        # Outside a venv some distros (Debian/Ubuntu/Arch/Fedora) refuse to
        # install. Retry with the escape hatch rather than dead-ending.
        say(f"  ! {label} refused - retrying with --break-system-packages")
        try:
            subprocess.run(base + ["--break-system-packages"] + args, check=True)
            return True
        except subprocess.CalledProcessError:
            say(f"  ! {label} still failed.")
            return False


def check_python():
    header("Checking Python")
    major, minor = sys.version_info[:2]
    say(f"  Python {major}.{minor} on {OS_NAME}")
    if (major, minor) < (3, 11):
        say()
        say("  ERROR: this project needs Python 3.11 or newer.")
        say("  (main.py uses asyncio.TaskGroup, added in 3.11.)")
        sys.exit(1)
    if not IN_VENV:
        say()
        say("  NOTE: you're not in a virtual environment.")
        say("  Recommended, so system packages stay untouched:")
        if OS_NAME == "Windows":
            say("      python -m venv .venv")
            say("      .venv\\Scripts\\activate")
        else:
            say("      python3 -m venv .venv")
            say("      source .venv/bin/activate")
        say("  Continuing anyway - pip will fall back if the OS blocks it.")


def ensure_requirements_file():
    """A missing OR empty requirements.txt silently installs nothing, which
    then shows up much later as a pile of ModuleNotFoundErrors. Write a
    known-good one if it isn't usable."""
    req = BASE_DIR / "requirements.txt"
    usable = req.exists() and any(
        line.strip() and not line.strip().startswith("#")
        for line in req.read_text(encoding="utf-8").splitlines()
    )
    if usable:
        say(f"  Using existing {req.name}")
        return req
    req.write_text("\n".join(CORE_REQUIREMENTS) + "\n", encoding="utf-8")
    say(f"  Wrote {req.name} ({len(CORE_REQUIREMENTS)} packages)")
    return req


def install_core():
    header("Installing core packages")
    req = ensure_requirements_file()
    pip_install(["--upgrade", "pip"], "pip upgrade")
    if not pip_install(["-r", str(req)], "core requirements"):
        say()
        say("  Core install failed. Nothing below will work until this does.")
        sys.exit(1)


def install_optional():
    header("Installing optional extras")
    extras = list(OPTIONAL_REQUIREMENTS)
    if OS_NAME == "Windows":
        extras += WINDOWS_EXTRAS

    skipped = []
    for pkg, why in extras:
        say(f"  -> {pkg}  ({why})")
        if not pip_install([pkg], pkg):
            skipped.append((pkg, why))
    return skipped


def install_playwright():
    header("Installing Playwright browsers")
    try:
        subprocess.run([sys.executable, "-m", "playwright", "install"], check=True)
        say("  Browsers installed.")
    except Exception as e:
        say(f"  ! Skipped ({e}) - browser_control features will be limited.")


def download_hand_model():
    header("Downloading hand-tracking model")
    target = BASE_DIR / "core" / "hand_landmarker.task"
    target.parent.mkdir(exist_ok=True)
    if target.exists():
        say(f"  Already present: core/{target.name}")
        return
    try:
        import mediapipe  # noqa: F401
    except ImportError:
        say("  Skipped - mediapipe isn't installed, so nothing would use it.")
        return
    try:
        say("  Fetching ~7 MB...")
        urllib.request.urlretrieve(HAND_MODEL_URL, target)
        say(f"  Saved to core/{target.name}")
    except Exception as e:
        say(f"  ! Download failed ({e}).")
        say("  Grab it manually later with:")
        say(f"      curl -L -o core/hand_landmarker.task {HAND_MODEL_URL}")


def scaffold():
    header("Creating folders and config")
    for name in ("config", "core", "plugins", "memory", "logs"):
        (BASE_DIR / name).mkdir(exist_ok=True)
    say("  config/ core/ plugins/ memory/ logs/")

    api_keys_path = BASE_DIR / "config" / "api_keys.json"
    if not api_keys_path.exists():
        api_keys_path.write_text(
            json.dumps({"gemini_api_key": ""}, indent=4), encoding="utf-8"
        )
        say("  Created config/api_keys.json (empty - fill it on first launch)")
    else:
        say("  config/api_keys.json already exists - left alone")

    # Keep the key out of git. Appending is safe: we check first.
    gitignore = BASE_DIR / ".gitignore"
    wanted = [
        "config/api_keys.json", "logs/", "__pycache__/", "*.pyc",
        ".venv/", "venv/", "core/*.task", "plugins/.spotify_cache",
    ]
    existing = (
        gitignore.read_text(encoding="utf-8").splitlines()
        if gitignore.exists() else []
    )
    missing = [w for w in wanted if w not in existing]
    if missing:
        with gitignore.open("a", encoding="utf-8") as f:
            if existing and existing[-1].strip():
                f.write("\n")
            f.write("\n".join(missing) + "\n")
        say(f"  Added {len(missing)} entries to .gitignore (API key stays local)")

    prompt_path = BASE_DIR / "core" / "prompt.txt"
    if not prompt_path.exists():
        prompt_path.write_text(
            "You are an autonomous monitoring and response system with real tools "
            "connected to this computer. Your job is to notice patterns, answer "
            "precisely, and act - not to perform a personality.\n\n"
            "VOICE AND MANNER\n"
            "- Speak in short, plain sentences. No filler, no small talk.\n"
            "- State findings as findings, not as excitement.\n"
            '- Do not use "sir", "boss", or any formal address.\n'
            "- If something is wrong or risky, say so plainly, once.\n\n"
            "OPERATING RULES\n"
            "- Never simulate or guess a result - always call the matching tool "
            "and report exactly what it returned.\n"
            "- If a tool fails, report the failure plainly and suggest one next step.\n"
            "- Keep responses short by default.\n"
            "- Match the user's language automatically.\n",
            encoding="utf-8",
        )
        say("  Created core/prompt.txt (edit to change how it talks)")
    else:
        say("  core/prompt.txt already exists - left alone")


def system_notes():
    """Things pip can't fix, that differ per OS."""
    header("System notes")
    if OS_NAME == "Linux":
        say("  Audio needs PortAudio installed system-wide. If the mic or")
        say("  speaker errors out, install it with your package manager:")
        say("     Debian/Ubuntu/Mint:  sudo apt install portaudio19-dev python3-tk")
        say("     Arch/Manjaro:        sudo pacman -S portaudio tk")
        say("     Fedora:              sudo dnf install portaudio-devel python3-tkinter")
        say()
        say("  On Wayland, pyautogui (gesture tab-switching, computer_control)")
        say("  may not work - those need X11 or XWayland.")
    elif OS_NAME == "Darwin":
        say("  macOS will ask permission for Microphone, Camera, Screen")
        say("  Recording, and Accessibility the first time each is used.")
        say("  System Settings -> Privacy & Security if you miss a prompt.")
    else:
        say("  If the mic isn't found, check Settings -> Privacy -> Microphone")
        say("  and allow desktop apps.")


def main():
    say("=" * 68)
    say("  THE MACHINE - setup")
    say("=" * 68)

    check_python()
    install_core()
    skipped = install_optional()
    install_playwright()
    download_hand_model()
    scaffold()
    system_notes()

    header("Done")
    if skipped:
        say("  These optional packages didn't install:")
        for pkg, why in skipped:
            say(f"     - {pkg}  -> {why} will be unavailable")
        say("  The app still runs; those features stay off.")
        say()
    say("  Start it with:   python main.py")
    say("  Add your Gemini API key on the first-launch screepn.")
    say()


if __name__ == "__main__":
    main()