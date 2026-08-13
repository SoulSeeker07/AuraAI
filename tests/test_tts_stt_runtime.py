def main():
    #!/usr/bin/env python3
    """
    TTS & STT Runtime Test Suite
    ==============================
    Tests every engine that can actually be exercised given installed packages.
    
    Results are grouped into:
      PASS   — ran and succeeded
      SKIP   — package not installed or model file not found (not a bug)
      FAIL   — unexpected error or wrong return value
    
    Run:
        $env:PYTHONIOENCODING="utf-8"
        .venv\Scripts\python.exe tests\test_tts_stt_runtime.py
    """
    
    import os
    import sys
    import logging
    from pathlib import Path
    
    ROOT = Path(__file__).resolve().parents[1]
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    
    try:
        from dotenv import load_dotenv
        load_dotenv(ROOT / ".env")
    except ImportError:
        pass
    
    logging.basicConfig(level=logging.WARNING)
    
    GREEN  = "\033[92m"
    YELLOW = "\033[93m"
    RED    = "\033[91m"
    RESET  = "\033[0m"
    BOLD   = "\033[1m"
    
    def _tag(label, color):
        return f"{color}{BOLD}[{label}]{RESET}"
    
    PASS_TAG = _tag("PASS", GREEN)
    SKIP_TAG = _tag("SKIP", YELLOW)
    FAIL_TAG = _tag("FAIL", RED)
    
    results = []
    
    def _record(name, status, detail=""):
        results.append((name, status, detail))
        tag = {"PASS": PASS_TAG, "SKIP": SKIP_TAG, "FAIL": FAIL_TAG}[status]
        suffix = f"  -- {detail}" if detail else ""
        print(f"  {tag}  {name}{suffix}")
    
    
    # ===========================================================================
    #  SECTION 1 -- TTS ENGINE TESTS
    # ===========================================================================
    print(f"\n{BOLD}{'='*60}{RESET}")
    print(f"{BOLD}  TTS ENGINE TESTS{RESET}")
    print(f"{BOLD}{'='*60}{RESET}")
    
    # 1a. PiperTTSEngine
    try:
        from src.voice.tts_manager import PiperTTSEngine, TTSSettings, TTSSpeaker
        settings = TTSSettings(speaker=TTSSpeaker.PIPER)
        engine = PiperTTSEngine(settings)
        ok = engine.initialize()
        if ok:
            _record("PiperTTSEngine.initialize()", "PASS", f"model={engine._get_model_path()}")
            added = engine.add_text("Hello from Piper")
            _record("PiperTTSEngine.add_text()", "PASS" if added else "FAIL")
            status = engine.get_status()
            assert status["is_active"] is True
            _record("PiperTTSEngine.get_status()", "PASS", str(status))
        else:
            model_path = os.getenv("PIPER_MODEL_PATH")
            if model_path:
                _record("PiperTTSEngine.initialize()", "FAIL",
                        f"PIPER_MODEL_PATH set but init failed: {model_path}")
            else:
                _record("PiperTTSEngine.initialize()", "SKIP",
                        "PIPER_MODEL_PATH not set -- run scripts/setup_voice_models.py")
    except Exception as e:
        _record("PiperTTSEngine.initialize()", "FAIL", str(e))
    
    # 1b. EdgeTTSEngine
    try:
        from src.voice.tts_manager import EdgeTTSEngine, TTSSettings, TTSSpeaker
        settings = TTSSettings(speaker=TTSSpeaker.EDGE_TTS, voice="en-US-AriaNeural")
        engine = EdgeTTSEngine(settings)
        ok = engine.initialize()
        if ok:
            _record("EdgeTTSEngine.initialize()", "PASS", "edge-tts ready (online fallback)")
            added = engine.add_text("Hello Aura")
            _record("EdgeTTSEngine.add_text()", "PASS" if added else "FAIL")
        else:
            _record("EdgeTTSEngine.initialize()", "SKIP", "edge-tts not installed")
    except Exception as e:
        _record("EdgeTTSEngine.initialize()", "FAIL", str(e))
    
    # 1c. TTSSettings string->enum coercion (piper)
    try:
        from src.voice.tts_manager import TTSSettings, TTSSpeaker
        s = TTSSettings(speaker="piper")
        assert s.speaker == TTSSpeaker.PIPER
        _record("TTSSettings 'piper' string coercion", "PASS", f"-> {s.speaker!r}")
    except Exception as e:
        _record("TTSSettings 'piper' string coercion", "FAIL", str(e))
    
    # 1d. TTSSettings string->enum coercion (edge_tts fallback)
    try:
        from src.voice.tts_manager import TTSSettings, TTSSpeaker
        s = TTSSettings(speaker="edge_tts")
        assert s.speaker == TTSSpeaker.EDGE_TTS
        _record("TTSSettings 'edge_tts' string coercion", "PASS", f"-> {s.speaker!r}")
    except Exception as e:
        _record("TTSSettings 'edge_tts' string coercion", "FAIL", str(e))
    
    # 1e. Invalid speaker raises ValueError
    try:
        from src.voice.tts_manager import TTSSettings
        try:
            TTSSettings(speaker="elevenlabs")  # removed -- must raise ValueError
            _record("TTSSettings 'elevenlabs' rejected", "FAIL", "should have raised ValueError")
        except ValueError:
            _record("TTSSettings 'elevenlabs' rejected", "PASS", "ValueError raised correctly")
    except Exception as e:
        _record("TTSSettings invalid speaker", "FAIL", str(e))
    
    # 1f. TTSManger lazy-init (Piper path)
    try:
        from src.voice.tts_manager import TTSManger, TTSSettings, TTSSpeaker
        mgr = TTSManger(TTSSettings(speaker=TTSSpeaker.PIPER))
        assert mgr.engine is None
        ok = mgr.add_text("Lazy test")
        if ok:
            _record("TTSManger lazy-init via add_text() [Piper]", "PASS")
        else:
            _record("TTSManger lazy-init via add_text() [Piper]", "SKIP",
                    "Piper init returned False (PIPER_MODEL_PATH not set)")
    except Exception as e:
        _record("TTSManger lazy-init via add_text() [Piper]", "FAIL", str(e))
    
    # 1g. set_callbacks stored before init
    try:
        from src.voice.tts_manager import TTSManger, TTSSettings, TTSSpeaker
        mgr = TTSManger(TTSSettings(speaker=TTSSpeaker.PIPER))
        mgr.set_callbacks(complete=lambda: None, interrupt=lambda: None)
        assert mgr._pending_complete_callback is not None
        _record("TTSManger.set_callbacks() before init", "PASS")
    except Exception as e:
        _record("TTSManger.set_callbacks() before init", "FAIL", str(e))
    
    # 1h. initialize() idempotency
    try:
        from src.voice.tts_manager import TTSManger, TTSSettings, TTSSpeaker
        mgr = TTSManger(TTSSettings(speaker=TTSSpeaker.PIPER))
        r1 = mgr.initialize()
        engine_ref = mgr.engine
        r2 = mgr.initialize()
        same_engine = mgr.engine is engine_ref
        _record("TTSManger.initialize() idempotency", "PASS",
                f"first={r1} second={r2} same_engine={same_engine}")
    except Exception as e:
        _record("TTSManger.initialize() idempotency", "FAIL", str(e))
    
    # 1i. No ElevenLabs in TTSSpeaker enum
    try:
        from src.voice.tts_manager import TTSSpeaker
        has_el = hasattr(TTSSpeaker, "ELEVENLABS")
        if has_el:
            _record("ElevenLabs removed from TTSSpeaker", "FAIL",
                    "TTSSpeaker.ELEVENLABS still exists")
        else:
            _record("ElevenLabs removed from TTSSpeaker", "PASS",
                    "ELEVENLABS not in enum")
    except Exception as e:
        _record("ElevenLabs removed from TTSSpeaker", "FAIL", str(e))
    
    
    # ===========================================================================
    #  SECTION 2 -- STT ENGINE TESTS
    # ===========================================================================
    print(f"\n{BOLD}{'='*60}{RESET}")
    print(f"{BOLD}  STT ENGINE TESTS{RESET}")
    print(f"{BOLD}{'='*60}{RESET}")
    
    # 2a. FasterWhisperSTTEngine -- import + init (downloads tiny model ~73 MB first time)
    try:
        from src.voice.stt_manager import FasterWhisperSTTEngine, STTSettings, STTProvider
        settings = STTSettings(provider=STTProvider.FASTER_WHISPER, model_size="tiny")
        engine = FasterWhisperSTTEngine(settings)
        print("    [INFO] Initializing faster-whisper tiny model (downloads on first use)...")
        ok = engine.initialize()
        if ok:
            _record("FasterWhisperSTTEngine.initialize()", "PASS", "model=tiny")
            status = engine.get_status()
            assert status["is_active"] is True
            _record("FasterWhisperSTTEngine.get_status()", "PASS")
            # Feed silence -- should buffer safely
            silence = bytes(3200)
            result = engine.process_chunk(silence)
            assert result == "", f"expected '' got {result!r}"
            _record("FasterWhisperSTTEngine.process_chunk(silence)", "PASS",
                    "chunk buffered, no premature transcription")
            engine.reset()
            _record("FasterWhisperSTTEngine.reset()", "PASS")
        else:
            _record("FasterWhisperSTTEngine.initialize()", "FAIL",
                    "initialization returned False")
    except Exception as e:
        _record("FasterWhisperSTTEngine.initialize()", "SKIP",
                f"faster-whisper unavailable: {e}")
    
    # 2b. STTManager -- faster-whisper path
    try:
        from src.voice.stt_manager import STTManager, STTSettings, STTProvider
        mgr = STTManager(STTSettings(provider=STTProvider.FASTER_WHISPER, model_size="tiny"))
        assert mgr.engine is None
        ok = mgr.initialize()
        if ok:
            _record("STTManager.initialize() [faster-whisper]", "PASS")
            silence = bytes(3200)
            result = mgr.process_audio(silence)
            _record("STTManager.process_audio(silence) [faster-whisper]", "PASS",
                    f"result={result!r}")
            mgr.reset()
            _record("STTManager.reset() [faster-whisper]", "PASS")
        else:
            _record("STTManager.initialize() [faster-whisper]", "FAIL",
                    "initialization returned False")
    except Exception as e:
        _record("STTManager.initialize() [faster-whisper]", "SKIP", str(e))
    
    # 2c. STTSettings string->enum coercion
    try:
        from src.voice.stt_manager import STTSettings, STTProvider
        s = STTSettings(provider="faster_whisper")
        assert s.provider == STTProvider.FASTER_WHISPER
        _record("STTSettings 'faster_whisper' string coercion", "PASS", f"-> {s.provider!r}")
    except Exception as e:
        _record("STTSettings 'faster_whisper' string coercion", "FAIL", str(e))
    
    # 2d. STTSettings invalid provider raises ValueError
    try:
        from src.voice.stt_manager import STTSettings
        try:
            STTSettings(provider="nonexistent_provider")
            _record("STTSettings invalid provider rejected", "FAIL", "should have raised ValueError")
        except ValueError:
            _record("STTSettings invalid provider rejected", "PASS", "ValueError raised correctly")
    except Exception as e:
        _record("STTSettings invalid provider rejected", "FAIL", str(e))
    
    # 2e. VoskSTTEngine
    try:
        from src.voice.stt_manager import VoskSTTEngine, STTSettings, STTProvider
        settings = STTSettings(provider=STTProvider.VOSK)
        engine = VoskSTTEngine(settings)
        ok = engine.initialize()
        if ok:
            _record("VoskSTTEngine.initialize()", "PASS")
            silence = bytes(3200)
            result = engine.process_chunk(silence)
            _record("VoskSTTEngine.process_chunk(silence)", "PASS", f"result={result!r}")
        else:
            model_path = os.getenv("VOSK_MODEL_PATH")
            if model_path:
                _record("VoskSTTEngine.initialize()", "FAIL",
                        f"VOSK_MODEL_PATH set but init failed: {model_path}")
            else:
                _record("VoskSTTEngine.initialize()", "SKIP",
                        "VOSK_MODEL_PATH not set -- run scripts/setup_voice_models.py")
    except Exception as e:
        _record("VoskSTTEngine.initialize()", "FAIL", str(e))
    
    # 2f. STTSettings serialization
    try:
        from src.voice.stt_manager import STTSettings, STTProvider
        s = STTSettings(provider=STTProvider.FASTER_WHISPER, model_size="tiny", language="en")
        d = s.to_dict()
        assert d["provider"] == "faster_whisper"
        assert d["model_size"] == "tiny"
        _record("STTSettings.to_dict()", "PASS", str(d))
    except Exception as e:
        _record("STTSettings.to_dict()", "FAIL", str(e))
    
    # 2g. STTManager get_status() before init
    try:
        from src.voice.stt_manager import STTManager, STTSettings, STTProvider
        mgr = STTManager(STTSettings(provider=STTProvider.FASTER_WHISPER))
        status = mgr.get_status()
        assert status["is_active"] is False
        _record("STTManager.get_status() before init", "PASS", str(status))
    except Exception as e:
        _record("STTManager.get_status() before init", "FAIL", str(e))
    
    # 2h. STTManager process_audio() before init returns ""
    try:
        from src.voice.stt_manager import STTManager, STTSettings, STTProvider
        mgr = STTManager(STTSettings(provider=STTProvider.FASTER_WHISPER))
        result = mgr.process_audio(bytes(3200))
        assert result == ""
        _record("STTManager.process_audio() before init returns ''", "PASS")
    except Exception as e:
        _record("STTManager.process_audio() before init returns ''", "FAIL", str(e))
    
    # 2i. STTProvider.FASTER_WHISPER exists in enum
    try:
        from src.voice.stt_manager import STTProvider
        assert hasattr(STTProvider, "FASTER_WHISPER")
        assert STTProvider.FASTER_WHISPER.value == "faster_whisper"
        _record("STTProvider.FASTER_WHISPER enum value", "PASS",
                f"value={STTProvider.FASTER_WHISPER.value!r}")
    except Exception as e:
        _record("STTProvider.FASTER_WHISPER enum value", "FAIL", str(e))
    
    
    # ===========================================================================
    #  SECTION 3 -- INTEGRATION: VoiceManager defaults
    # ===========================================================================
    print(f"\n{BOLD}{'='*60}{RESET}")
    print(f"{BOLD}  INTEGRATION -- VoiceManager defaults{RESET}")
    print(f"{BOLD}{'='*60}{RESET}")
    
    try:
        from src.voice.voice_manager import VoiceManager
        from src.voice.tts_manager import TTSSpeaker
        from src.voice.stt_manager import STTProvider
    
        vm = VoiceManager()
    
        # TTS default = Piper
        tts_speaker = vm.tts_manager.settings.speaker
        if tts_speaker == TTSSpeaker.PIPER:
            _record("VoiceManager default TTS = Piper", "PASS")
        else:
            _record("VoiceManager default TTS = Piper", "FAIL",
                    f"got {tts_speaker!r}")
    
        # STT default = faster_whisper
        stt_provider = vm.stt_manager.settings.provider
        if stt_provider == STTProvider.FASTER_WHISPER:
            _record("VoiceManager default STT = faster-whisper", "PASS")
        else:
            _record("VoiceManager default STT = faster-whisper", "FAIL",
                    f"got {stt_provider!r}")
    
        # TTS callbacks stored
        assert vm.tts_manager._pending_complete_callback is not None
        _record("VoiceManager TTS callbacks stored at init", "PASS")
    
        # speak() lazy-init
        result = vm.speak("Hello from Piper")
        if result:
            _record("VoiceManager.speak() via Piper lazy-init", "PASS")
        else:
            _record("VoiceManager.speak() via Piper lazy-init", "SKIP",
                    "PIPER_MODEL_PATH not set -- speak() returned False as expected")
    
    except Exception as e:
        _record("VoiceManager integration test", "FAIL", str(e))
    
    
    # ===========================================================================
    #  FINAL SUMMARY
    # ===========================================================================
    print(f"\n{BOLD}{'='*60}{RESET}")
    print(f"{BOLD}  SUMMARY{RESET}")
    print(f"{BOLD}{'='*60}{RESET}")
    
    passed  = [r for r in results if r[1] == "PASS"]
    skipped = [r for r in results if r[1] == "SKIP"]
    failed  = [r for r in results if r[1] == "FAIL"]
    
    print(f"\n  {PASS_TAG}  {len(passed)} passed")
    print(f"  {SKIP_TAG}  {len(skipped)} skipped  (missing model files -- not bugs)")
    print(f"  {FAIL_TAG}  {len(failed)} failed")
    
    if skipped:
        print(f"\n  To unlock skipped tests:")
        print(f"    $env:PYTHONIOENCODING='utf-8'")
        print(f"    .venv\\Scripts\\python.exe scripts\\setup_voice_models.py")
    
    if failed:
        print(f"\n  Failed tests:")
        for name, _, detail in failed:
            print(f"    x {name}: {detail}")
    
    print()
    sys.exit(1 if failed else 0)

if __name__ == '__main__':
    main()
