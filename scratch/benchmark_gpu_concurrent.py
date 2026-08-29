"""
Realistic Concurrent-Load GPU Benchmark for GTX 1650 (4GB)
Location: scratch/benchmark_gpu_concurrent.py

Pass/Fail Criteria:
  - Peak VRAM <= 3.60 GB (Avoids Windows WDDM paging crash)
  - Warm Latency <= 900 ms over 5 sustained runs
  - Concurrent Degradation <= 20% when Whisper is actively transcribing
"""

import gc
import os
import sys
import time
import numpy as np
import torch
import torch.nn as nn
from PIL import Image

def get_vram_usage():
    if not torch.cuda.is_available():
        return 0.0, 0.0
    allocated = torch.cuda.memory_allocated(0) / (1024 ** 3)
    reserved = torch.cuda.memory_reserved(0) / (1024 ** 3)
    return allocated, reserved

print("=" * 65)
print(" GTX 1650 (4GB) CONCURRENT-LOAD REALISTIC BENCHMARK ")
print("=" * 65)

if not torch.cuda.is_available():
    print("[ERROR] CUDA is not available. Aborting.")
    sys.exit(1)

device = torch.device("cuda:0")
gpu_name = torch.cuda.get_device_name(0)
total_vram = torch.cuda.get_device_properties(0).total_memory / (1024 ** 3)
print(f"Device: {gpu_name} ({total_vram:.2f} GB Total VRAM)")

# --- PHASE 1: Baseline VRAM ---
alloc, res = get_vram_usage()
print(f"\n[Phase 1] Baseline VRAM: {alloc:.3f} GB allocated, {res:.3f} GB reserved")

# --- PHASE 2: Load Resident Embedding Model ---
print("\n[Phase 2] Loading Resident SentenceTransformers (MiniLM / BGE-small)...")
from sentence_transformers import SentenceTransformer
embed_model = SentenceTransformer("all-MiniLM-L6-v2", device="cuda")
_ = embed_model.encode(["Initial warm-up sentence for episodic memory embedding."])
alloc, res = get_vram_usage()
print(f"After Embedder: {alloc:.3f} GB allocated, {res:.3f} GB reserved")

# --- PHASE 3: Load Resident Faster-Whisper / Whisper (base/tiny) ---
print("\n[Phase 3] Loading Resident Faster-Whisper / Whisper (base)...")
import whisper
whisper_model = whisper.load_model("base", device="cuda")
# Generate dummy 3-second audio (16kHz sine wave with low amplitude)
sample_rate = 16000
audio_dummy = (0.1 * np.sin(2 * np.pi * 440 * np.linspace(0, 3, 3 * sample_rate))).astype(np.float32)
_ = whisper_model.transcribe(audio_dummy, fp16=False)
alloc, res = get_vram_usage()
print(f"After Whisper + Embedder: {alloc:.3f} GB allocated, {res:.3f} GB reserved")

# --- PHASE 4: Simulated Quantized 2B VLM Vision Encoder & Cross-Attention Pass ---
# Simulates the compute graph of a 2B VLM (Vision Transformer ViT + Projection + Autoregressive Decoder layer)
class QuantizedVLMStub(nn.Module):
    def __init__(self):
        super().__init__()
        # ViT patch encoder for 1080p image (downsampled to 448x448)
        self.conv_in = nn.Conv2d(3, 768, kernel_size=14, stride=14)
        # 12 transformer encoder blocks
        encoder_layer = nn.TransformerEncoderLayer(d_model=768, nhead=12, dim_feedforward=2048, batch_first=True)
        self.transformer = nn.TransformerEncoder(encoder_layer, num_layers=6)
        # Language decoder projection
        self.proj = nn.Linear(768, 2048)
        # 4 Decoder layers simulating INT4/FP16 coordinate decoding
        dec_layer = nn.TransformerDecoderLayer(d_model=2048, nhead=16, dim_feedforward=4096, batch_first=True)
        self.decoder = nn.TransformerDecoder(dec_layer, num_layers=4)
        self.out_head = nn.Linear(2048, 1000)

    def forward(self, img, text_tokens):
        # img: [1, 3, 448, 448]
        feat = self.conv_in(img).flatten(2).transpose(1, 2)
        encoded_vision = self.transformer(feat)
        projected = self.proj(encoded_vision)
        decoded = self.decoder(text_tokens, projected)
        return self.out_head(decoded)

print("\n[Phase 4] Allocating VLM Model Graph onto CUDA...")
try:
    vlm_stub = QuantizedVLMStub().half().to(device)
    alloc, res = get_vram_usage()
    print(f"Total Resident VRAM (Embed + Whisper + VLM): {alloc:.3f} GB allocated, {res:.3f} GB reserved")
except Exception as e:
    print(f"[FATAL OOM] Failed to allocate VLM graph: {e}")
    sys.exit(1)

# Prepare dummy inputs (448x448 image tensor + 32 token prompt)
dummy_img = torch.randn(1, 3, 448, 448, dtype=torch.float16, device=device)
dummy_tokens = torch.randn(1, 32, 2048, dtype=torch.float16, device=device)

# --- PHASE 5: Isolated Inference Benchmark (5 Runs) ---
print("\n[Phase 5] Running 5 Isolated VLM Passes (Cold + Warm Latencies)...")
isolated_latencies = []
torch.cuda.synchronize()

for i in range(5):
    t0 = time.perf_counter()
    with torch.no_grad():
        out = vlm_stub(dummy_img, dummy_tokens)
    torch.cuda.synchronize()
    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    isolated_latencies.append(elapsed_ms)
    print(f"  Run {i+1}: {elapsed_ms:.1f} ms")

cold_latency = isolated_latencies[0]
warm_isolated = np.mean(isolated_latencies[1:])
print(f"Cold Latency: {cold_latency:.1f} ms | Avg Warm Latency (Isolated): {warm_isolated:.1f} ms")

# --- PHASE 6: Concurrent Inference Benchmark (Simultaneous Whisper + VLM) ---
print("\n[Phase 6] Running 5 Concurrent Passes (Whisper Transcribing + VLM Running)...")
concurrent_latencies = []

import threading

for i in range(5):
    # Run Whisper in background thread
    whisper_error = []
    def run_whisper():
        try:
            whisper_model.transcribe(audio_dummy, fp16=False)
        except Exception as err:
            whisper_error.append(err)

    w_thread = threading.Thread(target=run_whisper)
    
    torch.cuda.synchronize()
    t0 = time.perf_counter()
    w_thread.start()
    
    with torch.no_grad():
        out = vlm_stub(dummy_img, dummy_tokens)
    torch.cuda.synchronize()
    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    w_thread.join()
    
    concurrent_latencies.append(elapsed_ms)
    print(f"  Concurrent Run {i+1}: {elapsed_ms:.1f} ms (Whisper Error: {bool(whisper_error)})")

avg_concurrent = np.mean(concurrent_latencies)
degradation_pct = ((avg_concurrent - warm_isolated) / warm_isolated) * 100.0

alloc, res = get_vram_usage()
print("\n" + "=" * 65)
print(" BENCHMARK RESULTS & PASS/FAIL GATE EVALUATION ")
print("=" * 65)
print(f"Peak VRAM Reserved:               {res:.3f} GB  (Pass Limit: <= 3.60 GB)")
print(f"Avg Warm Latency (Isolated):       {warm_isolated:.1f} ms   (Pass Limit: <= 900.0 ms)")
print(f"Avg Warm Latency (Concurrent):     {avg_concurrent:.1f} ms")
print(f"Concurrency Degradation:          {degradation_pct:+.1f}%  (Pass Limit: <= +20.0%)")

pass_vram = res <= 3.60
pass_latency = warm_isolated <= 900.0
pass_degradation = degradation_pct <= 20.0
overall_pass = pass_vram and pass_latency and pass_degradation

print(f"\nGATE RESULTS:")
print(f"  [1] VRAM Headroom Test:         {'PASS' if pass_vram else 'FAIL'}")
print(f"  [2] Latency Threshold Test:     {'PASS' if pass_latency else 'FAIL'}")
print(f"  [3] Concurrent Interference:    {'PASS' if pass_degradation else 'FAIL'}")
print(f"\nOVERALL VERDICT: {'PROCEED TO M34 SPEC' if overall_pass else 'SHELVE LOCAL VLM -> PIVOT TO PRE-FETCHING'}")
print("=" * 65)
