import time
import sys
import os
import io
import wave
import asyncio
import numpy as np
from pathlib import Path
from dotenv import load_dotenv

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "src"))
sys.path.insert(1, str(root))

load_dotenv(str(root / ".env"))

print("================================================================", flush=True)
print("      AURA AI — STT HEAD-TO-HEAD BENCHMARK (REAL UTTERANCES)    ", flush=True)
print("================================================================\n", flush=True)

TEST_UTTERANCES = [
    "what time is it right now",
    "open visual studio code",
    "how much memory and gpu is aura using",
    "check the weather in bangalore today",
    "remember that my project uses python three eleven",
    "search google for quantum computing algorithms",
    "show all live system logs in debug mode",
    "close chrome and notepad",
    "explain how the neural notch hud works",
    "what are my pending tasks for this afternoon",
    "set a timer for ten minutes",
    "turn on the study room light",
    "what is the latest status of our deployment",
    "summarize today's conversation history",
    "what is the difference between synchronous and asynchronous python",
]

# 1. Synthesize real audio clips using edge_tts
print(f"[Step 1/3] Synthesizing {len(TEST_UTTERANCES)} real spoken audio samples (en-IN)...", flush=True)
import edge_tts
import soundfile as sf

audio_samples = []

async def _synth_all():
    for text in TEST_UTTERANCES:
        comm = edge_tts.Communicate(text, "en-IN-NeerjaNeural")
        buf = io.BytesIO()
        async for chunk in comm.stream():
            if chunk["type"] == "audio":
                buf.write(chunk["data"])
        buf.seek(0)
        data, sr = sf.read(buf)
        if len(data.shape) > 1:
            data = data.mean(axis=1)
            
        # Linear resample to 16000 if needed
        if sr != 16000:
            target_len = int(len(data) * 16000 / sr)
            x_old = np.linspace(0, 1, len(data))
            x_new = np.linspace(0, 1, target_len)
            data = np.interp(x_new, x_old, data)
            sr = 16000
            
        data_int16 = (np.clip(data, -1.0, 1.0) * 32767).astype(np.int16)
        
        wav_io = io.BytesIO()
        with wave.open(wav_io, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(16000)
            wf.writeframes(data_int16.tobytes())
            
        audio_samples.append({
            "text": text,
            "wav_bytes": wav_io.getvalue(),
            "pcm_int16": data_int16.tobytes(),
            "float_np": data.astype(np.float32),
            "duration_s": len(data_int16) / 16000.0,
        })

asyncio.run(_synth_all())
print(f"  [OK] Generated {len(audio_samples)} realistic audio samples.\n", flush=True)

# 2. Benchmark Local Faster-Whisper on NVIDIA GTX 1650 (CUDA FP16)
print("[Step 2/3] Benchmarking Local Faster-Whisper (CUDA FP16 on GTX 1650)...", flush=True)
from faster_whisper import WhisperModel
t0 = time.perf_counter()
local_model = WhisperModel("base", device="cuda", compute_type="float16")
load_ms = (time.perf_counter() - t0) * 1000
print(f"  [OK] CUDA Model Loaded in {load_ms:.1f} ms\n", flush=True)

local_results = []
for i, sample in enumerate(audio_samples):
    t_start = time.perf_counter()
    segments, info = local_model.transcribe(
        sample["float_np"],
        language="en",
        beam_size=1,
        condition_on_previous_text=False,
        temperature=0.0,
    )
    text_out = " ".join(s.text.strip() for s in segments).strip()
    latency_ms = (time.perf_counter() - t_start) * 1000
    local_results.append({
        "target": sample["text"],
        "transcribed": text_out,
        "latency_ms": latency_ms,
        "duration_s": sample["duration_s"],
    })
    print(f"  #{i+1:02d}: {latency_ms:6.1f}ms | \"{text_out}\"", flush=True)

print("\n", flush=True)

# 3. Benchmark Pooled Groq LPU (whisper-large-v3-turbo)
print("[Step 3/3] Benchmarking Pooled Groq LPU (whisper-large-v3-turbo, Persistent HTTP/2)...", flush=True)
from groq import Groq
import httpx
http_client = httpx.Client(http2=True, timeout=12.0)
groq_client = Groq(api_key=os.environ.get("GROQ_API_KEY"), http_client=http_client)

# Warmup connection
groq_client.audio.transcriptions.create(
    file=("warmup.wav", audio_samples[0]["wav_bytes"]),
    model="whisper-large-v3-turbo",
    language="en",
    temperature=0.0,
)

groq_results = []
for i, sample in enumerate(audio_samples):
    t_start = time.perf_counter()
    resp = groq_client.audio.transcriptions.create(
        file=("audio.wav", sample["wav_bytes"]),
        model="whisper-large-v3-turbo",
        response_format="text",
        prompt="Spoken conversational commands and desktop assistant requests in Indian English.",
        temperature=0.0,
    )
    text_out = str(resp).strip()
    latency_ms = (time.perf_counter() - t_start) * 1000
    groq_results.append({
        "target": sample["text"],
        "transcribed": text_out,
        "latency_ms": latency_ms,
        "duration_s": sample["duration_s"],
    })
    print(f"  #{i+1:02d}: {latency_ms:6.1f}ms | \"{text_out}\"", flush=True)

print("\n", flush=True)

# ── SUMMARY & COMPARISON ──
def calc_stats(res_list):
    lats = [r["latency_ms"] for r in res_list]
    return {
        "mean": float(np.mean(lats)),
        "min": float(np.min(lats)),
        "max": float(np.max(lats)),
        "p50": float(np.percentile(lats, 50)),
        "p95": float(np.percentile(lats, 95)),
        "std": float(np.std(lats)),
    }

loc_stats = calc_stats(local_results)
groq_stats = calc_stats(groq_results)

print("================================================================", flush=True)
print("                   HEAD-TO-HEAD RESULTS SUMMARY                 ", flush=True)
print("================================================================", flush=True)
print(f"| {'Metric':<20} | {'Local CUDA (base)':<18} | {'Groq LPU (large-v3-turbo)':<25} |", flush=True)
print(f"|{'-'*22}|{'-'*20}|{'-'*27}|", flush=True)
print(f"| {'Mean Latency':<20} | {loc_stats['mean']:>14.1f} ms | {groq_stats['mean']:>21.1f} ms |", flush=True)
print(f"| {'Min Latency':<20} | {loc_stats['min']:>14.1f} ms | {groq_stats['min']:>21.1f} ms |", flush=True)
print(f"| {'Max Latency':<20} | {loc_stats['max']:>14.1f} ms | {groq_stats['max']:>21.1f} ms |", flush=True)
print(f"| {'P50 (Median)':<20} | {loc_stats['p50']:>14.1f} ms | {groq_stats['p50']:>21.1f} ms |", flush=True)
print(f"| {'P95 Latency':<20} | {loc_stats['p95']:>14.1f} ms | {groq_stats['p95']:>21.1f} ms |", flush=True)
print(f"| {'Std Dev (Jitter)':<20} | {loc_stats['std']:>14.1f} ms | {groq_stats['std']:>21.1f} ms |", flush=True)
print("================================================================\n", flush=True)
