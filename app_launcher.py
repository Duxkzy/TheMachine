"""
Smarter app launcher.

The problem this fixes: asking for "spotify" used to fail if the actual
entry was "Spotify", "spotify-launcher", a Flatpak called
"com.spotify.Client", or a Snap. This builds a real index of what's
installed and fuzzy-matches against it, so near-misses still land.

Works on Linux (.desktop files incl. Flatpak/Snap), Windows (Start Menu
shortcuts), and macOS (.app bundles).
"""
from __future__ import annotations

import difflib
import os
import platform
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

OS_NAME = platform.system()

# Things people say vs. what the app is actually called. Checked before
# fuzzy matching, so these always win.
ALIASES = {
    "vscode": "visual studio code", "vs code": "visual studio code",
    "code": "visual studio code",
    "chrome": "google chrome", "navegador": "firefox",
    "explorador": "files", "explorer": "files",
    "terminal": "terminal", "consola": "terminal", "cmd": "terminal",
    "calc": "calculator", "calculadora": "calculator",
    "musica": "spotify", "música": "spotify",
    "discord": "discord", "disco": "discord",
    "steam": "steam", "juegos": "steam",
    "word": "libreoffice writer", "excel": "libreoffice calc",
    "navegador web": "firefox", "correo": "thunderbird",
    "ajustes": "settings", "configuracion": "settings",
    "configuración": "settings", "settings": "settings",
    "archivos": "files", "fotos": "image viewer",
    "editor": "text editor", "bloc de notas": "text editor",
    "notepad": "text editor",
}

_INDEX: list[dict] = []      # [{name, launch, kind}]
_INDEX_TIME = 0.0
_INDEX_TTL = 300.0           # rebuild at most every 5 min


def _norm(s: str) -> str:
    """Lowercase, strip punctuation/spaces — so 'VS-Code' == 'vs code'."""
    return re.sub(r"[^a-z0-9]", "", s.lower())


# ── indexing ────────────────────────────────────────────────────────────

def _index_linux() -> list[dict]:
    out = []
    dirs = [
        Path("/usr/share/applications"),
        Path("/usr/local/share/applications"),
        Path.home() / ".local/share/applications",
        Path("/var/lib/flatpak/exports/share/applications"),
        Path.home() / ".local/share/flatpak/exports/share/applications",
        Path("/var/lib/snapd/desktop/applications"),
    ]
    for d in dirs:
        if not d.is_dir():
            continue
        for f in d.glob("*.desktop"):
            try:
                text = f.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            if "NoDisplay=true" in text or "Hidden=true" in text:
                continue

            name = exec_line = ""
            for line in text.splitlines():
                if line.startswith("Name=") and not name:
                    name = line[5:].strip()
                elif line.startswith("Exec=") and not exec_line:
                    exec_line = line[5:].strip()
            if not name or not exec_line:
                continue

            # strip the freedesktop field codes (%U, %F, %i, ...)
            cmd = re.sub(r"%[a-zA-Z]", "", exec_line).strip()
            out.append({"name": name, "launch": cmd, "kind": "desktop",
                        "desktop_id": f.stem, "desktop_path": str(f)})
    return out


def _index_windows() -> list[dict]:
    out = []
    roots = []
    for env in ("ProgramData", "AppData"):
        base = os.environ.get(env)
        if base:
            roots.append(Path(base) / "Microsoft/Windows/Start Menu/Programs")
    for root in roots:
        if not root.is_dir():
            continue
        for f in root.rglob("*.lnk"):
            out.append({"name": f.stem, "launch": str(f), "kind": "lnk"})
    return out


def _index_macos() -> list[dict]:
    out = []
    for d in (Path("/Applications"), Path("/System/Applications"),
              Path.home() / "Applications"):
        if not d.is_dir():
            continue
        for f in list(d.glob("*.app")) + list(d.glob("*/*.app")):
            out.append({"name": f.stem, "launch": str(f), "kind": "app"})
    return out


def _index_path_binaries() -> list[dict]:
    """Anything on PATH, as a last resort — catches CLI-ish apps that have
    no launcher entry."""
    out = []
    seen = set()
    for d in os.environ.get("PATH", "").split(os.pathsep):
        p = Path(d)
        if not p.is_dir():
            continue
        try:
            for f in p.iterdir():
                if f.name in seen or not os.access(f, os.X_OK) or f.is_dir():
                    continue
                seen.add(f.name)
                out.append({"name": f.name, "launch": str(f), "kind": "bin"})
        except Exception:
            continue
    return out


def build_index(force: bool = False) -> list[dict]:
    global _INDEX, _INDEX_TIME
    if _INDEX and not force and (time.time() - _INDEX_TIME) < _INDEX_TTL:
        return _INDEX

    if OS_NAME == "Linux":
        apps = _index_linux()
    elif OS_NAME == "Windows":
        apps = _index_windows()
    elif OS_NAME == "Darwin":
        apps = _index_macos()
    else:
        apps = []

    apps += _index_path_binaries()

    # de-dupe by normalized name, keeping the richer entry (desktop/lnk/app
    # beats a bare binary)
    rank = {"desktop": 0, "lnk": 0, "app": 0, "bin": 1}
    best: dict[str, dict] = {}
    for a in apps:
        k = _norm(a["name"])
        if not k:
            continue
        if k not in best or rank[a["kind"]] < rank[best[k]["kind"]]:
            best[k] = a

    _INDEX = list(best.values())
    _INDEX_TIME = time.time()
    return _INDEX


# ── matching ────────────────────────────────────────────────────────────

def find_matches(query: str, limit: int = 5) -> list[tuple[dict, float]]:
    """Returns [(app, score)] best first. Score is 0..1."""
    apps = build_index()
    if not apps:
        return []

    q = _norm(query)
    alias = ALIASES.get(query.strip().lower())
    q_alias = _norm(alias) if alias else None

    scored = []
    for a in apps:
        n = _norm(a["name"])
        if not n:
            continue

        best = 0.0
        for needle in filter(None, (q, q_alias)):
            if n == needle:
                s = 1.0
            elif n.startswith(needle):
                s = 0.93
            elif needle in n:
                s = 0.85
            elif needle and needle in _norm(a.get("desktop_id", "")):
                s = 0.80
            else:
                s = difflib.SequenceMatcher(None, needle, n).ratio() * 0.75
            best = max(best, s)

        # prefer proper launcher entries over raw binaries at equal score
        if a["kind"] == "bin":
            best -= 0.04
        # 0.62 is tuned: a typo like "spotifi"->Spotify still lands (~0.64),
        # but an app that simply isn't installed ("chrome" on a machine
        # without it) no longer drags in junk like "chmem" (~0.51).
        if best > 0.62:
            scored.append((a, best))

    scored.sort(key=lambda t: t[1], reverse=True)
    return scored[:limit]


# ── launching ───────────────────────────────────────────────────────────

def _spawn(app: dict) -> tuple[bool, str]:
    """Launches the app. Returns (ok, error_text).

    The important bit is that it actually CHECKS. Popen only raises when
    the binary itself is missing — if the command starts and then dies
    (bad desktop entry, missing library, wrong args) it exits quietly, so
    without a poll() we'd report success for something that never opened.
    """
    kind, launch = app["kind"], app["launch"]

    if OS_NAME == "Windows":
        try:
            os.startfile(launch)  # type: ignore[attr-defined]
            return True, ""
        except Exception as e:
            return False, str(e)

    if kind == "app":                      # macOS bundle
        cmd = ["open", "-a", launch]
        shell = False
    elif kind == "desktop" and shutil.which("gtk-launch") and app.get("desktop_id"):
        # gtk-launch takes the desktop ID and handles Flatpak/Snap wrappers
        cmd = ["gtk-launch", app["desktop_id"]]
        shell = False
    else:
        cmd = launch                       # the Exec line, or a plain binary
        shell = True

    try:
        proc = subprocess.Popen(
            cmd, shell=shell,
            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
            start_new_session=True,
        )
    except Exception as e:
        return False, str(e)

    # Give it a moment, then see whether it died on the spot. GUI apps that
    # fork off return 0 immediately, which is fine — only a NON-zero exit
    # this early means it actually failed.
    time.sleep(0.6)
    rc = proc.poll()
    if rc is not None and rc != 0:
        err = ""
        try:
            err = (proc.stderr.read() or b"").decode("utf-8", "ignore").strip()
        except Exception:
            pass
        return False, (err.splitlines()[-1] if err else f"exited with code {rc}")

    return True, ""


def open_app_smart(query: str) -> str:
    """Finds and launches the closest matching app. Returns a message
    describing what happened, which is what gets read back to the user."""
    query = (query or "").strip()
    if not query:
        return "No app name given."

    matches = find_matches(query)
    if not matches:
        return (
            f"Couldn't find anything matching '{query}'. "
            "It may not be installed, or it has no launcher entry."
        )

    # Try the best match; if it fails to actually start, fall through to the
    # next candidate rather than claiming success.
    errors = []
    for app, score in matches:
        ok, err = _spawn(app)
        if ok:
            if score >= 0.93:
                return f"Opened {app['name']}."
            others = ", ".join(m["name"] for m, _ in matches[1:3] if m is not app)
            msg = f"Opened {app['name']} (closest match for '{query}')."
            if others:
                msg += f" Other options were: {others}."
            return msg
        errors.append(f"{app['name']}: {err}")

    return (
        f"Found {len(matches)} match(es) for '{query}' but none would start. "
        + " | ".join(errors[:2])
    )


def list_installed(filter_text: str = "", limit: int = 40) -> str:
    apps = build_index()
    names = sorted(a["name"] for a in apps)
    if filter_text:
        f = _norm(filter_text)
        names = [n for n in names if f in _norm(n)]
    if not names:
        return "No matching apps found."
    shown = names[:limit]
    extra = f" (+{len(names) - limit} more)" if len(names) > limit else ""
    return f"{len(names)} apps found: " + ", ".join(shown) + extra


if __name__ == "__main__":
    # quick manual check:  python app_launcher.py spotify
    q = " ".join(sys.argv[1:]) or "spotify"
    print(f"Index size: {len(build_index())}")
    for a, s in find_matches(q):
        print(f"  {s:.2f}  {a['name']}  [{a['kind']}]")
