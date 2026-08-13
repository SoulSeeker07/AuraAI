#!/usr/bin/env python3
"""
Aura Voice Model Setup
======================
Downloads required local voice models (Piper TTS + Vosk STT) if they are
missing. Never overwrites an existing valid model.

Usage:
    .venv\Scripts\python.exe scripts\setup_voice_models.py

After running, re-source your shell or restart Aura so the .env values
are picked up.
"""

import hashlib
import io
import os
import sys
import zipfile
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import URLError

# ── project root = parent of this script's directory ─────────────────────────
ROOT = Path(__file__).resolve().parent.parent
MODELS_DIR = ROOT / "models"
ENV_FILE = ROOT / ".env"

# ── model specs ──────────────────────────────────────────────────────────────
PIPER_MODEL_NAME = "en_US-lessac-medium"
PIPER_MODEL_DIR  = MODELS_DIR / "tts" / "piper"
PIPER_ONNX       = PIPER_MODEL_DIR / f"{PIPER_MODEL_NAME}.onnx"
PIPER_JSON       = PIPER_MODEL_DIR / f"{PIPER_MODEL_NAME}.onnx.json"

# Piper releases: https://huggingface.co/rhasspy/piper-voices
_HF_BASE = "https://huggingface.co/rhasspy/piper-voices/resolve/main"
PIPER_ONNX_URL = f"{_HF_BASE}/en/en_US/lessac/medium/{PIPER_MODEL_NAME}.onnx"
PIPER_JSON_URL = f"{_HF_BASE}/en/en_US/lessac/medium/{PIPER_MODEL_NAME}.onnx.json"

VOSK_MODEL_NAME = "vosk-model-small-en-us-0.15"
VOSK_MODEL_DIR  = MODELS_DIR / "stt" / "vosk" / VOSK_MODEL_NAME
VOSK_ZIP_URL    = (
    f"https://alphacephei.com/vosk/models/{VOSK_MODEL_NAME}.zip"
)

# ── helpers ──────────────────────────────────────────────────────────────────

def _print(msg: str, ok: bool | None = None) -> None:
    prefix = {True: "[OK]  ", False: "[FAIL]", None: "[INFO]"}[ok]
    print(f"  {prefix} {msg}")


def _download(url: str, dest: Path, label: str) -> bool:
    """Download url → dest, showing progress. Returns True on success."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".tmp")
    try:
        req = Request(url, headers={"User-Agent": "AuraAI-setup/1.0"})
        with urlopen(req, timeout=60) as resp:
            total = int(resp.headers.get("Content-Length", 0))
            downloaded = 0
            chunk = 65536
            with open(tmp, "wb") as f:
                while True:
                    data = resp.read(chunk)
                    if not data:
                        break
                    f.write(data)
                    downloaded += len(data)
                    if total:
                        pct = downloaded * 100 // total
                        print(f"\r    {label}: {pct}% ({downloaded // 1024} KB)", end="", flush=True)
        print()
        tmp.rename(dest)
        return True
    except URLError as e:
        print()
        _print(f"Download failed for {label}: {e}", ok=False)
        if tmp.exists():
            tmp.unlink()
        return False


def _file_valid(path: Path, min_bytes: int = 1024) -> bool:
    return path.exists() and path.stat().st_size >= min_bytes


def _update_env(key: str, value: str) -> None:
    """Set KEY=value in .env, creating or updating the line."""
    lines: list[str] = []
    found = False
    if ENV_FILE.exists():
        lines = ENV_FILE.read_text(encoding="utf-8").splitlines(keepends=True)
        for i, line in enumerate(lines):
            if line.startswith(f"{key}=") or line.startswith(f"{key} ="):
                lines[i] = f"{key}={value}\n"
                found = True
                break
    if not found:
        lines.append(f"{key}={value}\n")
    ENV_FILE.write_text("".join(lines), encoding="utf-8")


# ── piper model ───────────────────────────────────────────────────────────────

def setup_piper() -> bool:
    print("\n--- Piper TTS model ---")
    PIPER_MODEL_DIR.mkdir(parents=True, exist_ok=True)

    onnx_ok  = _file_valid(PIPER_ONNX,  min_bytes=1_000_000)
    json_ok  = _file_valid(PIPER_JSON,  min_bytes=100)

    if onnx_ok and json_ok:
        _print(f"Model already present: {PIPER_ONNX.relative_to(ROOT)}", ok=True)
    else:
        if not onnx_ok:
            _print(f"Downloading {PIPER_MODEL_NAME}.onnx (~63 MB) ...")
            if not _download(PIPER_ONNX_URL, PIPER_ONNX, "Piper ONNX"):
                return False
        if not json_ok:
            _print(f"Downloading {PIPER_MODEL_NAME}.onnx.json ...")
            if not _download(PIPER_JSON_URL, PIPER_JSON, "Piper JSON"):
                return False
        _print(f"Downloaded: {PIPER_ONNX.relative_to(ROOT)}", ok=True)

    # Verify the model can be loaded by piper-tts
    try:
        from piper.voice import PiperVoice
        voice = PiperVoice.load(str(PIPER_ONNX))
        _print("piper-tts model load: OK", ok=True)
        del voice
    except Exception as e:
        _print(f"piper-tts model load failed: {e}", ok=False)
        return False

    # Write relative path to .env
    rel = PIPER_ONNX.relative_to(ROOT).as_posix()
    _update_env("PIPER_MODEL_PATH", rel)
    _print(f"PIPER_MODEL_PATH={rel}", ok=True)
    return True


# ── vosk model ────────────────────────────────────────────────────────────────

def setup_vosk() -> bool:
    print("\n--- Vosk STT model ---")
    marker = VOSK_MODEL_DIR / "README"

    if VOSK_MODEL_DIR.exists() and any(VOSK_MODEL_DIR.iterdir()):
        _print(f"Model already present: {VOSK_MODEL_DIR.relative_to(ROOT)}", ok=True)
    else:
        zip_dest = MODELS_DIR / "stt" / "vosk" / f"{VOSK_MODEL_NAME}.zip"
        _print(f"Downloading {VOSK_MODEL_NAME}.zip (~40 MB) ...")
        if not _download(VOSK_ZIP_URL, zip_dest, "Vosk model"):
            return False

        _print("Extracting Vosk model ...")
        try:
            with zipfile.ZipFile(zip_dest) as zf:
                zf.extractall(MODELS_DIR / "stt" / "vosk")
            zip_dest.unlink()
            _print(f"Extracted: {VOSK_MODEL_DIR.relative_to(ROOT)}", ok=True)
        except Exception as e:
            _print(f"Extraction failed: {e}", ok=False)
            return False

    # Verify model can be loaded by vosk
    try:
        import vosk
        vosk.SetLogLevel(-1)  # suppress verbose Vosk logs during check
        model = vosk.Model(str(VOSK_MODEL_DIR))
        rec = vosk.KaldiRecognizer(model, 16000)
        # Feed 0.1 s of silence — should not raise
        rec.AcceptWaveform(bytes(3200))
        _print("Vosk model load + recognition: OK", ok=True)
        del model, rec
    except Exception as e:
        _print(f"Vosk model validation failed: {e}", ok=False)
        return False

    rel = VOSK_MODEL_DIR.relative_to(ROOT).as_posix()
    _update_env("VOSK_MODEL_PATH", rel)
    _print(f"VOSK_MODEL_PATH={rel}", ok=True)
    return True


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> int:
    print("=" * 60)
    print("  Aura Voice Model Setup")
    print("=" * 60)
    print(f"  Project root : {ROOT}")
    print(f"  Models dir   : {MODELS_DIR}")

    piper_ok = setup_piper()
    vosk_ok  = setup_vosk()

    print("\n" + "=" * 60)
    print("  Summary")
    print("=" * 60)
    _print("Piper TTS model", ok=piper_ok)
    _print("Vosk STT model",  ok=vosk_ok)

    if piper_ok and vosk_ok:
        print("\n  All models ready. Restart Aura (or re-source .env) to use them.")
        return 0
    else:
        print("\n  Some models failed. Check network connection and try again.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
