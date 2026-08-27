"""
Hardware Multi-Turn Audio Stream & Barge-In Live Test
=====================================================
Directly exercises the local sounddevice / PortAudio physical hardware stream
across 5+ simulated conversation cycles, testing software gating and barge-in.
"""

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from voice.audio_manager import AudioManager
from voice.voice_manager import VoiceManager
from voice.models import ConversationState

def main():
    print("=" * 60)
    print(" AURA LIVE HARDWARE MULTI-TURN & BARGE-IN TEST")
    print("=" * 60)

    # 1. Initialize real AudioManager singleton on physical mic
    audio_mgr = AudioManager()
    input_devices = audio_mgr.get_input_devices()
    print(f"[*] Available input devices: {len(input_devices)}")
    for d in input_devices:
        print(f"    - [{d.device_id}] {d.name} ({d.sample_rate}Hz)")

    default_mic = audio_mgr.get_default_input_device()
    if not default_mic:
        print("[!] No physical microphone found.")
        sys.exit(1)

    print(f"[*] Using physical microphone: {default_mic.name} (device {default_mic.device_id})")

    # Track audio frame delivery
    received_frames = []
    def mic_callback(chunk):
        received_frames.append((time.time(), len(chunk)))

    print("\n[Phase 1] Opening real PortAudio InputStream...")
    ok = audio_mgr.start_recording(mic_callback, sample_rate=16000, channels=1, device_id=default_mic.device_id)
    if not ok:
        print("[FAIL] Failed to open physical microphone stream.")
        sys.exit(1)

    print("[PASS] Physical InputStream opened successfully.")

    # 2. Test 5+ consecutive turns with real audio chunks
    for turn in range(1, 6):
        print(f"\n--- Turn #{turn} ---")
        
        # Step A: Active listening (enable capture)
        audio_mgr.enable_capture()
        print(f"[*] [Turn {turn}] Capture ENABLED (Listening for 1.0s)...")
        before_count = len(received_frames)
        time.sleep(1.0)
        after_count = len(received_frames)
        chunks_in_listening = after_count - before_count
        print(f"    -> Received {chunks_in_listening} live mic frames.")
        assert chunks_in_listening > 0, f"Turn {turn}: PortAudio stream stopped delivering frames!"

        # Step B: Software Mute during TTS playback (disable capture)
        audio_mgr.disable_capture()
        print(f"[*] [Turn {turn}] Capture DISABLED (Simulating TTS playback for 0.8s)...")
        before_mute = len(received_frames)
        time.sleep(0.8)
        after_mute = len(received_frames)
        chunks_in_mute = after_mute - before_mute
        print(f"    -> Frames delivered to queue while muted: {chunks_in_mute} (Expected: 0)")
        assert chunks_in_mute == 0, f"Turn {turn}: Audio leaked through software mute!"

        # Step C: On Turn 3 & 4, simulate Barge-in Interruption
        if turn in (3, 4):
            print(f"[*] [Turn {turn}] Simulating Barge-in Interruption (re-enabling mic mid-turn)...")
            audio_mgr.enable_capture()
            b_before = len(received_frames)
            time.sleep(0.6)
            b_after = len(received_frames)
            barge_chunks = b_after - b_before
            print(f"    -> Barge-in live mic frames captured: {barge_chunks}")
            assert barge_chunks > 0, f"Turn {turn}: Barge-in failed to capture audio!"
            audio_mgr.disable_capture()

    print("\n[Phase 2] Verifying physical stream health after 5 turns...")
    audio_mgr.enable_capture()
    t_start = len(received_frames)
    time.sleep(1.0)
    t_end = len(received_frames)
    print(f"[*] Final health check: {t_end - t_start} frames delivered in 1.0s.")
    assert (t_end - t_start) > 0, "Final stream health check failed!"

    # 3. Clean physical shutdown
    print("\n[Phase 3] Shutting down physical stream...")
    audio_mgr.stop_recording()
    print("[PASS] Physical stream closed cleanly.")
    print("\n" + "=" * 60)
    print(f" ALL 5+ MULTI-TURN & BARGE-IN CYCLES PASSED ON PHYSICAL HARDWARE!")
    print(f" Total live audio frames processed: {len(received_frames)}")
    print("=" * 60)

if __name__ == "__main__":
    main()
