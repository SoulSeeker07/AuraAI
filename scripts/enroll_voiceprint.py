"""
Voiceprint Enrollment CLI Tool (Multi-Register: Low, Medium, High)
==================================================================
Records spoken audio across distinct vocal registers (Low/Quiet, Medium/Normal,
High/Projected) to generate an on-device neural voiceprint embedding.

Ensures Aura recognizes you effortlessly, whether you speak softly, normally,
or loudly, without ever having to strain your voice.
"""

import os
import sys
import time
import argparse
import pyaudio
import numpy as np
from pathlib import Path
from typing import Dict, List, Optional, Tuple

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "src"))
sys.path.insert(1, str(root))

from voice.speaker_verification import SpeakerVerificationEngine, SCHEMA_VERSION

# Register definitions and guided instructions
REGISTER_CONFIGS = {
    "medium": {
        "title": "MEDIUM / CONVERSATIONAL VOICE",
        "description": "Speak in your natural, relaxed, everyday conversational tone at normal desk distance.",
        "min_rms": 0.0040,
        "phrases": [
            "Hey Aura, this is my natural voice.",
            "Hey Aura, check system status and open workspace.",
        ],
    },
    "low": {
        "title": "LOW / SOFT / QUIET VOICE",
        "description": "Speak softly, quietly, or gently (whisper-adjacent or relaxed evening tone).",
        "min_rms": 0.0020,  # Very sensitive gate so quiet speech is accepted easily
        "phrases": [
            "Hey Aura, I am speaking quietly.",
            "Hey Aura, dim the lights and set a reminder.",
        ],
    },
    "high": {
        "title": "HIGH / PROJECTED / LOUD VOICE",
        "description": "Speak clearly, firmly, or projected as if speaking from across the room.",
        "min_rms": 0.0070,
        "phrases": [
            "Hey Aura, turn off music and pause playback!",
            "Hey Aura, what are my upcoming appointments?",
        ],
    },
}


def render_meter(rms: float, max_rms: float = 0.05, width: int = 20) -> str:
    """Render a visual ASCII VU meter."""
    level = min(max(rms / max_rms, 0.0), 1.0)
    filled = int(level * width)
    bar = "█" * filled + "░" * (width - filled)
    return f"[{bar}] RMS: {rms:.4f}"


def record_sample(
    p: pyaudio.PyAudio,
    register_key: str,
    sample_idx: int,
    total_samples: int,
    phrase: str,
    min_rms: float,
    duration_s: float = 3.0,
) -> bytes:
    """Record a single audio sample with visual feedback and sensitivity checking."""
    cfg = REGISTER_CONFIGS.get(register_key, {})
    reg_title = cfg.get("title", register_key.upper())

    while True:
        print(f"\n┌──────────────────────────────────────────────────────────────┐")
        print(f"│ [{sample_idx}/{total_samples}] {reg_title:<54} │")
        print(f"└──────────────────────────────────────────────────────────────┘")
        print(f'   Target phrase : "{phrase}"')
        print(f"   Guidance      : {cfg.get('description', '')}")
        input(f"   👉 Press [Enter] when ready to speak... ")
        print("   🎤 RECORDING NOW... (Speak phrase!)", flush=True)

        try:
            stream = p.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=16000,
                input=True,
                frames_per_buffer=1024,
            )
        except Exception as e:
            print(f"   [!] Failed to open audio input stream: {e}")
            raise

        frames = []
        num_frames = int(16000 / 1024 * duration_s)

        for frame_i in range(num_frames):
            data = stream.read(1024, exception_on_overflow=False)
            frames.append(data)
            # Show live energy level every 3 frames
            if frame_i % 3 == 0:
                chunk_np = np.frombuffer(data, dtype=np.int16).astype(np.float32) / 32768.0
                chunk_rms = float(np.sqrt(np.mean(chunk_np**2)))
                sys.stdout.write(f"\r   Live Meter: {render_meter(chunk_rms)}   ")
                sys.stdout.flush()

        stream.stop_stream()
        stream.close()

        raw_pcm = b"".join(frames)
        audio_np = np.frombuffer(raw_pcm, dtype=np.int16).astype(np.float32) / 32768.0
        overall_rms = float(np.sqrt(np.mean(audio_np**2)))

        # Also find peak frame RMS for quiet speech detection
        frame_len = int(16000 * 0.2)
        hop = int(16000 * 0.1)
        if len(audio_np) >= frame_len:
            peak_rms = max(
                float(np.sqrt(np.mean(audio_np[i : i + frame_len] ** 2)))
                for i in range(0, len(audio_np) - frame_len + 1, hop)
            )
        else:
            peak_rms = overall_rms

        sys.stdout.write(f"\r   Recorded Sample: {render_meter(peak_rms)}              \n")
        sys.stdout.flush()

        if peak_rms < min_rms:
            print(
                f"   [!] Audio energy too faint (Peak RMS: {peak_rms:.4f} < threshold {min_rms:.4f}).\n"
                f"       Let's retry this sample so Aura can learn it clearly...",
                flush=True,
            )
            time.sleep(1.0)
            continue

        print(f"   ✓ Sample accepted! (Peak RMS: {peak_rms:.4f})")
        return raw_pcm


def print_banner():
    print("================================================================================")
    print("           AURA AI — MULTI-REGISTER OWNER VOICEPRINT ENROLLMENT WIZARD          ")
    print("================================================================================")
    print(" This wizard captures your voice across three distinct acoustic registers:       ")
    print("   1. Medium Voice (Everyday conversational tone)                               ")
    print("   2. Low Voice    (Quiet, soft, relaxed — so you never need to speak loudly)   ")
    print("   3. High Voice   (Projected, clear, louder tone across the room)              ")
    print("================================================================================\n")


def show_status(engine: SpeakerVerificationEngine):
    """Display current enrollment status."""
    print("────────────────────────────────────────────────────────────────────────────────")
    print("CURRENT VOICEPRINT PROFILE STATUS:")
    if engine.is_enrolled():
        meta = engine._enrolled_metadata
        regs = meta.get("registers", []) or ["default"]
        print(f"  • Status          : ENROLLED (Schema v{meta.get('version', SCHEMA_VERSION)})")
        print(f"  • Profile Path    : {engine.profile_path}")
        print(f"  • Total Samples   : {meta.get('sample_count', 0)}")
        print(f"  • Enrolled Tones  : {', '.join(regs)}")
        exemplar_cnt = len(engine._enrolled_exemplars) if engine._enrolled_exemplars is not None else 0
        print(f"  • Exemplar Matrix : {exemplar_cnt} prototype vectors")
    else:
        print("  • Status          : NOT ENROLLED (Aura runs in open bypass mode)")
        print(f"  • Profile Path    : {engine.profile_path}")
    print("────────────────────────────────────────────────────────────────────────────────\n")


def main():
    parser = argparse.ArgumentParser(description="Aura AI Owner Voiceprint Enrollment Tool")
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Quick enrollment mode (1 sample per tone: Medium, Low, High = 3 total)",
    )
    parser.add_argument(
        "--register",
        choices=["medium", "low", "high"],
        default=None,
        help="Enroll or update only a specific voice register (e.g. --register low)",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="Display current enrolled profile information and exit",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Purge enrolled profile from disk and reset to bypass mode",
    )
    args = parser.parse_args()

    if not args.list and not args.reset:
        print_banner()

    print("⏳ Initializing neural voiceprint engine and audio devices...\n", flush=True)
    engine = SpeakerVerificationEngine.get_instance()

    if args.list:
        show_status(engine)
        return

    if args.reset:
        confirm = input("⚠️ Are you sure you want to delete your enrolled voiceprint? (y/N): ")
        if confirm.lower().strip() == "y":
            engine.reset_profile()
            print("✓ Voiceprint profile deleted. Aura will now operate in open bypass mode.")
        else:
            print("Operation cancelled.")
        return

    show_status(engine)

    # Determine which registers to capture
    if args.register:
        active_registers = [args.register]
    else:
        # Default order: Medium first to calibrate, then Low (quiet), then High (projected)
        active_registers = ["medium", "low", "high"]

    # Samples per register
    samples_per_reg = 1 if args.quick else 2

    # Calculate total count
    total_samples = len(active_registers) * samples_per_reg
    current_sample_num = 1

    p = pyaudio.PyAudio()
    registered_samples: Dict[str, List[bytes]] = {}

    try:
        for reg_key in active_registers:
            cfg = REGISTER_CONFIGS[reg_key]
            phrases = cfg["phrases"][:samples_per_reg]
            registered_samples[reg_key] = []

            print(f"\n▶ SECTION: {cfg['title']}")
            print(f"  {cfg['description']}\n")

            for phrase in phrases:
                sample_bytes = record_sample(
                    p=p,
                    register_key=reg_key,
                    sample_idx=current_sample_num,
                    total_samples=total_samples,
                    phrase=phrase,
                    min_rms=cfg["min_rms"],
                    duration_s=2.8,
                )
                registered_samples[reg_key].append(sample_bytes)
                current_sample_num += 1

        print("\n" + "=" * 80)
        print(" [Processing] Computing 256-D neural acoustic embeddings (VoxCeleb ResNet-34)...")
        print("              Building multi-register prototype matrix (Low, Medium, High)...")
        print("=" * 80)

        success = engine.enroll(registered_samples)

        if success:
            print("  ✓ SUCCESS: Owner Voiceprint Enrolled Successfully (Multi-Register v2)!")
            print("================================================================================")
            print(f"  • Profile Saved   : {engine.profile_path}")
            print(f"  • Registers Active: {', '.join(registered_samples.keys())}")
            ex_cnt = len(engine._enrolled_exemplars) if engine._enrolled_exemplars is not None else 0
            print(f"  • Prototypes      : {ex_cnt} exemplar vectors stored")
            print("  • Result         : Aura will now effortlessly recognize you in LOW, MEDIUM,")
            print("                     and HIGH voices without having to speak loudly!\n")
        else:
            print("\n[FAIL] Enrollment failed: Audio quality too low or silent.")

    except KeyboardInterrupt:
        print("\n\n[!] Enrollment cancelled by user.")
    except Exception as e:
        print(f"\n[Error] Enrollment encountered an error: {e}")
    finally:
        p.terminate()


if __name__ == "__main__":
    main()
